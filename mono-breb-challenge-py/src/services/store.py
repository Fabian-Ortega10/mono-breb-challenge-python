"""
Almacen en memoria muy simple para los eventos de webhook recibidos.
Suficiente para el alcance de este reto (demostrar el flujo end-to-end);
en produccion esto se reemplazaria por una tabla en base de datos y se
usaria el "id" del evento para deduplicar entregas repetidas del webhook.
"""

import threading
from datetime import datetime, timezone
import json as _json

_MAX_EVENTS = 200
_lock = threading.Lock()
_events = []


def add_event(event: dict) -> None:
    with _lock:
        _events.insert(0, {"receivedAt": datetime.now(timezone.utc).isoformat(), **event})
        del _events[_MAX_EVENTS:]


def get_events(resource_id: str = None):
    with _lock:
        snapshot = list(_events)
    if not resource_id:
        return snapshot
    return [e for e in snapshot if resource_id in _json.dumps(e.get("payload") or {})]
