"""
Cliente HTTP para la API Bre-B Participant.

Requisito 4 del reto (manejo de errores) implementado aqui de forma
centralizada en lugar de repetir try/except en cada ruta:

 1. Inyecta automaticamente el Bearer token vigente en cada peticion.
 2. Si la API responde 401 (token invalido/expirado -> Caso 3 de la
    Fase 2), invalida el cache de token, pide uno nuevo UNA sola vez
    y reintenta la peticion original antes de rendirse.
 3. Cualquier error (4xx/5xx/red) se normaliza a un formato consistente
    ({status, code, message}) que las rutas devuelven tal cual al
    frontend, evitando exponer stacktraces o formatos inconsistentes.
"""

import requests

from ..config import config
from . import mono_auth
from ..utils.api_error import normalize_mono_error, MonoAPIError


def _request(method: str, path: str, json=None, params=None, retry: bool = True):
    try:
        token = mono_auth.get_access_token()
    except requests.HTTPError as exc:
        raise MonoAPIError(normalize_mono_error(response=exc.response, exception=exc)) from exc
    except requests.RequestException as exc:
        raise MonoAPIError(normalize_mono_error(exception=exc)) from exc

    try:
        response = requests.request(
            method=method,
            url=f"{config.BASE_URL}{path}",
            json=json,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise MonoAPIError(normalize_mono_error(exception=exc)) from exc

    if response.status_code == 401 and retry:
        # Reintento unico ante 401: puede ser un token que expiro justo
        # antes de la llamada (condicion de carrera) o fue revocado
        # externamente.
        mono_auth.invalidate()
        return _request(method, path, json=json, params=params, retry=False)

    if response.status_code >= 400:
        raise MonoAPIError(normalize_mono_error(response=response))

    if not response.content:
        return {}
    return response.json()


def get(path: str, params=None):
    return _request("GET", path, params=params)


def post(path: str, json=None):
    return _request("POST", path, json=json)


def patch(path: str, json=None):
    return _request("PATCH", path, json=json)


def delete(path: str):
    return _request("DELETE", path)
