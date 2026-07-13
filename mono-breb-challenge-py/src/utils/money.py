"""
La API de Bre-B Participant expresa todos los montos como enteros en la
UNIDAD MENOR de la moneda (centavos para COP), tal como se ve en los
ejemplos de la documentacion:
    {"amount": 100000000, "currency": "COP"}  ->  $1.000.000,00 COP

El Caso 4 de la Fase 2 ("se queria cobrar $50.000 pero cobraron $500")
ocurre cuando la integracion envia el valor en pesos (50000) creyendo que
la API lo interpreta como pesos, cuando en realidad la API lo interpreta
como centavos (50000 centavos = $500,00 COP).

Estas funciones centralizan la conversion en un solo lugar para que ese
error de "unidad" no pueda colarse de nuevo en el resto del codigo.
"""


def pesos_to_minor_units(pesos) -> int:
    """Convierte pesos (lo que el usuario escribe en el formulario) a centavos (lo que espera la API)."""
    try:
        value = float(pesos)
    except (TypeError, ValueError):
        raise ValueError("Monto invalido: debe ser un numero positivo en pesos")
    if value < 0:
        raise ValueError("Monto invalido: debe ser un numero positivo en pesos")
    return round(value * 100)


def minor_units_to_pesos(minor_units):
    """Convierte centavos (lo que devuelve la API) a pesos (para mostrar en la UI)."""
    if minor_units is None:
        return None
    try:
        return float(minor_units) / 100
    except (TypeError, ValueError):
        return None


def format_amount(amount_object) -> str:
    """Formatea un objeto amount de la API ({amount, currency}) como texto legible en COP."""
    if not amount_object:
        return "-"
    pesos = minor_units_to_pesos(amount_object.get("amount"))
    if pesos is None:
        return "-"
    currency = amount_object.get("currency", "COP")
    formatted = f"{pesos:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    symbol = "$" if currency == "COP" else f"{currency} "
    return f"{symbol}{formatted}"
