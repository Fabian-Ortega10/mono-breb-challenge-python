"""
Todas las respuestas de error de Bre-B Participant siguen el mismo sobre:
    {
      "code": "400 Bad Request",
      "message": "Malformed request",
      "id": "log_...",
      "errors": [ { "error_code": "...", "message": "...", "path": null, "url": null } ]
    }

Este helper normaliza ese sobre en un objeto simple y le agrega un mensaje
legible en espanol para mostrar en la UI (Requisito 4: manejo de errores).
"""

FRIENDLY_MESSAGES = {
    "missing_authorization_header": (
        "Falta el header Authorization. Verifica que el backend este agregando el Bearer token."
    ),
    "invalid_token": (
        "El token de acceso es invalido o expiro. Se intentara renovar automaticamente."
    ),
    "not_authorized": (
        "El token no tiene el scope necesario para esta operacion. Revisa los scopes solicitados."
    ),
    "tenant_account_not_found": (
        "La cuenta tenant configurada (MONO_TENANT_ACCOUNT_ID) no existe en este ambiente."
    ),
    "collection_not_found": "No existe un recaudo con ese ID.",
    "key_not_found": "No se encontro ninguna llave Bre-B registrada con ese valor.",
    "key_already_registered": "Ya existe un recaudo/llave activa con ese external_id.",
    "amount_exceeds_max_limit": "El monto de la transferencia supera el limite permitido por Bre-B.",
    "service_is_unavailable": "El servicio de Mono no esta disponible en este momento. Intenta de nuevo.",
    "internal_error": "Ocurrio un error inesperado en el servidor de Mono.",
    "unknown": "Ocurrio un error no identificado. Revisa el detalle tecnico.",
}


class MonoAPIError(Exception):
    """Excepcion que envuelve un error normalizado de la API de Mono."""

    def __init__(self, normalized: dict):
        super().__init__(normalized.get("message"))
        self.normalized = normalized


def normalize_mono_error(response=None, exception: Exception = None) -> dict:
    if response is None:
        return {
            "status": 500,
            "code": "network_error",
            "message": "No fue posible comunicarse con la API de Mono.",
            "detail": str(exception) if exception else None,
        }

    status = response.status_code
    try:
        body = response.json()
    except ValueError:
        body = None

    if not body:
        return {
            "status": status,
            "code": "network_error",
            "message": "La API de Mono respondio con un cuerpo no valido.",
            "detail": response.text[:500] if response.text else None,
        }

    errors = body.get("errors") or []
    first_error = errors[0] if errors else {}
    error_code = first_error.get("error_code", "unknown")

    return {
        "status": status,
        "code": error_code,
        "message": FRIENDLY_MESSAGES.get(error_code, body.get("message", "Error desconocido")),
        "technical_message": first_error.get("message") or body.get("message"),
        "log_id": body.get("id"),
        "raw": body,
    }
