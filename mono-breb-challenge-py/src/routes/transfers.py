import time

from flask import Blueprint, request, jsonify

from ..services import mono_client
from ..services import store
from ..config import config
from ..utils.money import pesos_to_minor_units, format_amount
from ..utils.api_error import MonoAPIError

bp = Blueprint("transfers", __name__, url_prefix="/api/transferencias")

# Estados NO finales del ciclo de vida de una transferencia saliente, segun
# los webhooks documentados (outgoing_transfer.*): created, target_resolved,
# processing, held, send_to_breb_provider. Solo "successful" y "failed" son
# finales.
#
# El Caso 2 de la Fase 2 ("una transferencia aparece como exitosa y minutos
# despues figura como fallida") ocurre cuando la integracion trata el 202
# Accepted / state=processing de la respuesta de creacion como si fuera la
# confirmacion final. Aqui se corrige explicitamente: la UI nunca debe
# mostrar "Transferencia exitosa" hasta ver state == "successful".
_FINAL_STATES = {"successful", "failed"}

_STATE_MAP = {
    "created": {"label": "Creada", "tone": "neutral"},
    "target_resolved": {"label": "Destinatario resuelto", "tone": "info"},
    "processing": {"label": "En procesamiento (no confirmar aun)", "tone": "warning"},
    "held": {"label": "Retenida para revision", "tone": "warning"},
    "send_to_breb_provider": {"label": "Enviada al proveedor Bre-B", "tone": "info"},
    "successful": {"label": "Exitosa (confirmada)", "tone": "success"},
    "failed": {"label": "Fallida", "tone": "error"},
}


def _human_state(state):
    return _STATE_MAP.get(state, {"label": state, "tone": "neutral"})


def _present_transfer(t: dict) -> dict:
    state = t.get("state")
    human = _human_state(state)
    target = t.get("target") or {}
    creditor = target.get("creditor") or {}

    return {
        "id": t.get("id"),
        "external_id": t.get("external_id"),
        "state": state,
        "state_label": human["label"],
        "state_tone": human["tone"],
        "is_final": state in _FINAL_STATES,
        "state_reason": t.get("state_reason"),
        "amount": format_amount(t.get("amount")),
        "description": t.get("description"),
        "target": {
            "key_value": target.get("key_value"),
            "key_type": target.get("key_type"),
            "creditor_name": creditor.get("full_name"),
            "creditor_document": creditor.get("document_number"),
        }
        if t.get("target")
        else None,
        "inserted_at": t.get("inserted_at"),
        "updated_at": t.get("updated_at"),
    }


def _error_response(exc: MonoAPIError):
    return jsonify({"error": exc.normalized}), exc.normalized.get("status", 500)


@bp.post("")
def enviar_transferencia():
    body = request.get_json(force=True, silent=True) or {}
    key_value = body.get("key_value")
    amount_pesos = body.get("amount_pesos")

    if not key_value:
        return jsonify({"error": {"message": "key_value (llave Bre-B destino) es requerido"}}), 400
    if not amount_pesos:
        return jsonify({"error": {"message": "amount_pesos es requerido"}}), 400

    try:
        # 1) Resolver el target antes de transferir. Esto es lo que el Caso 5
        # ejercita: si la llave no tiene un formato valido, este paso falla
        # aqui mismo con un mensaje claro, en vez de dejar que la
        # transferencia se cree y falle silenciosamente mas adelante.
        resolution = mono_client.post(
            "/api/v1/targets/resolve",
            json={
                "tenant_account_id": config.TENANT_ACCOUNT_ID,
                "format": "plain_key",
                "value": key_value,
            },
        )
    except MonoAPIError as exc:
        return _error_response(exc)

    if resolution.get("state") != "resolved":
        return (
            jsonify(
                {
                    "error": {
                        "message": "No fue posible resolver la llave Bre-B indicada.",
                        "state": resolution.get("state"),
                        "state_reason": resolution.get("state_reason"),
                    }
                }
            ),
            422,
        )

    try:
        minor_units = pesos_to_minor_units(amount_pesos)
    except ValueError as exc:
        return jsonify({"error": {"message": str(exc)}}), 400

    try:
        # 2) Crear la transferencia contra el target ya resuelto.
        batch = mono_client.post(
            "/api/v1/outgoing_transfers",
            json={
                "tenant_account_id": config.TENANT_ACCOUNT_ID,
                "description": body.get("description") or "Transferencia Bre-B",
                "transfers": [
                    {
                        "external_id": body.get("external_id") or f"demo-transfer-{int(time.time() * 1000)}",
                        "target_id": resolution["target"]["id"],
                        "amount": {"amount": minor_units, "currency": "COP"},
                    }
                ],
            },
        )
    except MonoAPIError as exc:
        return _error_response(exc)

    # 202 y no 201: comunicamos explicitamente al frontend que esto es
    # "aceptado para procesar", no "confirmado". El frontend debe seguir
    # consultando /api/transferencias/:id o los webhooks hasta ver un
    # estado final.
    return (
        jsonify(
            {
                "batch_id": batch.get("id"),
                "accepted": [_present_transfer(t) for t in batch.get("accepted_transfers", [])],
                "duplicated": [_present_transfer(t) for t in batch.get("duplicated_transfers", [])],
                "rejected": batch.get("rejected_transfers", []),
            }
        ),
        202,
    )


@bp.get("")
def listar_transferencias():
    try:
        data = mono_client.get(
            "/api/v1/outgoing_transfers",
            params={
                "tenant_account_id": config.TENANT_ACCOUNT_ID,
                "limit": request.args.get("limit", 25),
            },
        )
    except MonoAPIError as exc:
        return _error_response(exc)

    items = data.get("outgoing_transfers") or data.get("transfers") or data.get("data") or []
    items = items if isinstance(items, list) else []
    return jsonify({"items": [_present_transfer(t) for t in items], "raw": data})


@bp.get("/<transfer_id>")
def detalle_transferencia(transfer_id):
    try:
        data = mono_client.get(f"/api/v1/outgoing_transfers/{transfer_id}")
    except MonoAPIError as exc:
        return _error_response(exc)

    presented = _present_transfer(data)
    presented["webhook_events"] = store.get_events(resource_id=transfer_id)
    return jsonify(presented)
