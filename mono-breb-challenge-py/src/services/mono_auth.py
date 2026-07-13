"""
Gestor de tokens OAuth 2.0 (Client Credentials) para la API Bre-B Participant.

Por que existe este modulo y no simplemente "pedir un token y usarlo":
En la Fase 2 del reto (Caso 3) se describe un escenario donde, de un momento
a otro, TODAS las peticiones a la API devuelven 401 con error_code
"invalid_token". La causa raiz mas comun de ese sintoma es que el
access_token tiene una vida util corta (expires_in = 3600s segun la
documentacion de /api/v1/oauth/token) y la integracion lo estaba
reutilizando indefinidamente sin renovarlo.

Este modulo previene ese bug de raiz:
 - Cachea el token en memoria junto con su tiempo de expiracion.
 - Renueva el token automaticamente ANTES de que expire (con margen de
   seguridad de 60s) usando nuevamente client_credentials.
 - Si una peticion falla igualmente con 401, invalida el cache y fuerza
   un solo reintento con un token nuevo (ver mono_client.py).
"""

import time
import threading
import requests

from ..config import config

_SAFETY_MARGIN_SECONDS = 60

_lock = threading.Lock()
_cached_token = None
_expires_at = 0.0


def _request_new_token() -> str:
    global _cached_token, _expires_at

    response = requests.post(
        f"{config.BASE_URL}/api/v1/oauth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "scope": config.SCOPES,
        },
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    _cached_token = data["access_token"]
    _expires_at = time.time() + data.get("expires_in", 3600)
    return _cached_token


def get_access_token(force_refresh: bool = False) -> str:
    """Devuelve un access_token valido, renovando si hace falta."""
    with _lock:
        is_expired_or_missing = (
            _cached_token is None or time.time() >= _expires_at - _SAFETY_MARGIN_SECONDS
        )
        if force_refresh or is_expired_or_missing:
            return _request_new_token()
        return _cached_token


def invalidate() -> None:
    global _cached_token, _expires_at
    with _lock:
        _cached_token = None
        _expires_at = 0.0
