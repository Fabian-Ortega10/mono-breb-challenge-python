from flask import Blueprint, request, jsonify

from ..services import mono_client
from ..config import config
from ..utils.money import pesos_to_minor_units, format_amount
from ..utils.api_error import MonoAPIError

bp = Blueprint("collections", __name__, url_prefix="/api/recaudos")


# Traduce el "state" real de la API a una etiqueta clara para el usuario.
#
# Logica que el Caso 1 de la Fase 2 describe
# como incorrecta ("state != created -> mostrar Pagado"). Aqui se corrige
# distinguiendo explicitamente "minimum_paid" (pago parcial que ya supero
# el minimo, pero el recaudo sigue abierto) de "paid" (pago completo).
_STATE_MAP = {
    "created": {"label": "Creado (esperando registro de llave)", "tone": "neutral"},
    "ready": {"label": "Listo para recibir pagos", "tone": "info"},
    "minimum_paid": {"label": "Pago parcial (minimo alcanzado, aun abierto)", "tone": "warning"},
    "paid": {"label": "Pagado en su totalidad", "tone": "success"},
    "failed": {"label": "Fallido", "tone": "error"},
    "discarded": {"label": "Descartado", "tone": "error"},
}


def _human_state(state):
    return _STATE_MAP.get(state, {"label": state, "tone": "neutral"})


def _present_collection(c: dict) -> dict:
    human = _human_state(c.get("state"))
    paid_amount = c.get("paid_amount")
    total_maximum_amount = c.get("total_maximum_amount")
    fully_settled = None
    if paid_amount and total_maximum_amount:
        fully_settled = paid_amount.get("amount", 0) >= total_maximum_amount.get("amount", 0)

    return {
        "id": c.get("id"),
        "external_id": c.get("external_id"),
        "state": c.get("state"),
        "state_label": human["label"],
        "state_tone": human["tone"],
        "state_reason": c.get("state_reason"),
        "usage_mode": c.get("usage_mode"),
        "nickname": c.get("nickname"),
        "reference": c.get("reference"),
        "keys": c.get("keys"),
        "total_minimum_amount": format_amount(c.get("total_minimum_amount")),
        "total_maximum_amount": format_amount(c.get("total_maximum_amount")),
        "paid_amount": format_amount(c.get("paid_amount")),
        # Muestra explicitamente si lo pagado alcanza lo maximo esperado,
        # en vez de inferirlo solo del nombre del estado.
        "fully_settled": fully_settled,
        "expires_at": c.get("expires_at"),
        "inserted_at": c.get("inserted_at"),
        "updated_at": c.get("updated_at"),
    }


def _error_response(exc: MonoAPIError):
    return jsonify({"error": exc.normalized}), exc.normalized.get("status", 500)


@bp.post("")
def crear_recaudo():
    body = request.get_json(force=True, silent=True) or {}
    usage_mode = body.get("usage_mode")

    if usage_mode not in ("single_use", "multiple_use"):
        return (
            jsonify({"error": {"message": "usage_mode es requerido y debe ser 'single_use' o 'multiple_use'"}}),
            400,
        )

    import time

    collection_payload = {
        "external_id": body.get("external_id") or f"demo-{int(time.time() * 1000)}",
        "usage_mode": usage_mode,
    }
    if body.get("nickname"):
        collection_payload["nickname"] = body["nickname"]
    if body.get("reference"):
        collection_payload["reference"] = body["reference"]
    if body.get("custom_key_value"):
        collection_payload["custom_key_value"] = body["custom_key_value"]

    amount_pesos = body.get("amount_pesos")
    # El monto es opcional en Bre-B (recaudos de "monto abierto"). Si el
    # usuario indica un valor en pesos, se convierte a centavos aqui mismo
    # (unica fuente de conversion -> ver utils/money.py, previene el Caso 4).
    if amount_pesos not in (None, ""):
        try:
            minor_units = pesos_to_minor_units(amount_pesos)
        except ValueError as exc:
            return jsonify({"error": {"message": str(exc)}}), 400
        collection_payload["total_minimum_amount"] = {"amount": minor_units, "currency": "COP"}
        collection_payload["total_maximum_amount"] = {"amount": minor_units, "currency": "COP"}

    try:
        data = mono_client.post(
            "/api/v1/collections",
            json={
                "tenant_account_id": config.TENANT_ACCOUNT_ID,
                "collections": [collection_payload],
            },
        )
    except MonoAPIError as exc:
        return _error_response(exc)

    return (
        jsonify(
            {
                "created": [_present_collection(c) for c in data.get("created", [])],
                "duplicated": [_present_collection(c) for c in data.get("duplicated", [])],
                "rejected": data.get("rejected", []),
            }
        ),
        201,
    )


@bp.get("")
def listar_recaudos():
    try:
        data = mono_client.get(
            "/api/v1/collections",
            params={
                "tenant_account_id": config.TENANT_ACCOUNT_ID,
                "limit": request.args.get("limit", 25),
            },
        )
    except MonoAPIError as exc:
        return _error_response(exc)

    items = data.get("collections") or data.get("data") or []
    items = items if isinstance(items, list) else []
    return jsonify({"items": [_present_collection(c) for c in items], "raw": data})


@bp.get("/<collection_id>")
def detalle_recaudo(collection_id):
    try:
        data = mono_client.get(f"/api/v1/collections/{collection_id}")
    except MonoAPIError as exc:
        return _error_response(exc)

    return jsonify(_present_collection(data))
