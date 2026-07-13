from flask import Blueprint, request, jsonify

from ..services import store

bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")


@bp.post("")
def recibir_webhook():
    """
    Endpoint generico para recibir los webhooks de Bre-B Participant:
    collection.*, outgoing_transfer.*, outgoing_transfer_batch.*,
    target_resolution.*

    En sandbox, expon este endpoint con una URL publica (ngrok, cloudflared,
    etc.) y registrala en el dashboard de Mono. Cada evento recibido queda
    disponible en GET /api/webhooks/events para que el frontend muestre el
    estado real (y final) de recaudos y transferencias, en vez de asumirlo
    a partir de la respuesta sincrona del POST inicial.
    """
    event = request.get_json(force=True, silent=True) or {}
    event_type = (event.get("event") or {}).get("type") or event.get("type") or "unknown"
    store.add_event({"type": event_type, "payload": event})

    # Responder 200 rapido: Mono reintenta el webhook si no recibe 2xx.
    return jsonify({"received": True}), 200


@bp.get("/events")
def listar_eventos():
    resource_id = request.args.get("resource_id")
    return jsonify({"events": store.get_events(resource_id=resource_id)})
