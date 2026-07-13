# Mono — Tech Support Internship Challenge (versión Python)

Misma solución del reto (Bre-B Participant API) que la versión Node.js,
reescrita en **Python (Flask)** manteniendo exactamente la misma
arquitectura, lógica de negocio y correcciones frente a los 5 casos de la
Fase 2.

- **Fase 1 — Integración:** backend Flask + el mismo frontend estático
  (HTML/CSS/JS) de la versión original, sin cambios, porque solo consume la
  API vía `fetch` y no depende del lenguaje del backend.
- **Fase 2 — Detección y análisis de errores:** ver
  [`fase2-analisis-errores.md`](./fase2-analisis-errores.md) (idéntico al
  análisis de la versión Node, ya que es independiente del lenguaje de
  implementación).
- **Evidencia de uso de IA:** ver [`PROMPTS.md`](./PROMPTS.md).

## Stack

- Python 3.10+ / Flask
- `requests` para las peticiones HTTP a Mono
- `python-dotenv` para variables de entorno
- Frontend estático sin framework (HTML + CSS + JS plano)

## Estructura del proyecto

```
mono-breb-challenge-py/
├── src/
│   ├── server.py              # entrypoint Flask (create_app + blueprints)
│   ├── config.py              # carga de variables de entorno
│   ├── services/
│   │   ├── mono_auth.py       # OAuth 2.0 client_credentials, cache y renovación de token
│   │   ├── mono_client.py     # cliente HTTP: inyecta Bearer token, reintenta 1 vez ante 401
│   │   └── store.py           # almacén en memoria de eventos de webhook (demo)
│   ├── routes/
│   │   ├── collections.py     # Blueprint: recaudos (crear, listar, detalle)
│   │   ├── transfers.py       # Blueprint: transferencias salientes (resolver llave + enviar)
│   │   └── webhooks.py        # Blueprint: receptor de webhooks + endpoint de consulta
│   └── utils/
│       ├── money.py           # conversión pesos <-> centavos (única fuente de verdad)
│       └── api_error.py       # normalización de errores de la API a mensajes claros
├── public/                    # frontend (index.html, app.js, styles.css) — reutilizado tal cual
├── requirements.txt
├── .env.example
├── PROMPTS.md
└── fase2-analisis-errores.md
```

## Cómo ejecutar el proyecto

### 1. Requisitos

- Python 3.10 o superior
- Las credenciales del ambiente Sandbox de Mono (entregadas en la sección
  "Recursos" del reto, vía el link de Bitwarden)

### 2. Instalación

```bash
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Completa `.env` con los valores reales del Sandbox:

```
MONO_BASE_URL=https://breb-participant.sandbox.mono.la
MONO_CLIENT_ID=<client_id entregado por Mono>
MONO_CLIENT_SECRET=<client_secret entregado por Mono>
MONO_TENANT_ACCOUNT_ID=<bbtacc_... entregado por Mono>
```

### 3. Levantar el servidor

```bash
python3 -m src.server
```

El servidor queda escuchando en `http://localhost:3000` y sirve tanto la
API (`/api/...`) como el frontend estático (`/`).

Abre `http://localhost:3000` en el navegador para usar la consola de
pruebas.

### 4. (Opcional) Recibir webhooks reales

Para ver el estado final de una transferencia o recaudo reflejado en tiempo
real, expón tu servidor local con un túnel (por ejemplo `ngrok http 3000`)
y registra `https://<tu-túnel>/api/webhooks` como URL de notificaciones en
el dashboard de Mono. Los eventos recibidos se listan en la sección
"Eventos de webhook" de la consola.

## Flujos implementados

### Gestión de recaudos (`/api/recaudos`)

| Acción | Endpoint local | Endpoint de Mono |
|---|---|---|
| Crear recaudo | `POST /api/recaudos` | `POST /api/v1/collections` |
| Listar recaudos | `GET /api/recaudos` | `GET /api/v1/collections` |
| Detalle de un recaudo | `GET /api/recaudos/:id` | `GET /api/v1/collections/:id` |

El monto se ingresa en la UI **en pesos**; el backend lo convierte a
centavos en un único lugar (`utils/money.py`) antes de enviarlo a la API.
Esto previene directamente el error descrito en el Caso 4 de la Fase 2.

El estado del recaudo se traduce explícitamente distinguiendo
`minimum_paid` (pago parcial que ya superó el mínimo, pero el recaudo
sigue abierto) de `paid` (pagado en su totalidad) — la corrección al bug
del Caso 1 de la Fase 2.

### Transferencias salientes (`/api/transferencias`)

| Acción | Endpoint local | Endpoint de Mono |
|---|---|---|
| Enviar transferencia | `POST /api/transferencias` | `POST /api/v1/targets/resolve` + `POST /api/v1/outgoing_transfers` |
| Listar transferencias | `GET /api/transferencias` | `GET /api/v1/outgoing_transfers` |
| Detalle de una transferencia | `GET /api/transferencias/:id` | `GET /api/v1/outgoing_transfers/:id` |

El flujo primero resuelve la llave Bre-B destino (`/targets/resolve`) y
solo si esa resolución queda en estado `resolved` procede a crear la
transferencia. La respuesta se comunica siempre como "aceptada para
procesar" (HTTP 202), nunca como confirmación final: el frontend marca
`processing`, `held`, `send_to_breb_provider`, etc. como estados no
finales, y solo `successful` / `failed` cierran el ciclo — la corrección al
bug del Caso 2 de la Fase 2.

### Manejo de errores (Requisito 4)

Centralizado en `services/mono_client.py` y `utils/api_error.py`:

- Cada respuesta de error de la API (`{code, message, errors: [...]}`) se
  normaliza a un objeto `{status, code, message, technical_message, log_id}`
  y se traduce a un mensaje legible en español para el usuario.
- Ante un `401` con `invalid_token`, el cliente invalida el token en caché,
  pide uno nuevo y reintenta la petición original **una sola vez** antes de
  propagar el error — corrección proactiva al bug del Caso 3 de la Fase 2.
- Errores de red (timeout, sin conexión) se distinguen de errores de la API
  y se reportan con un mensaje distinto (`MonoAPIError` con
  `code: "network_error"`).
