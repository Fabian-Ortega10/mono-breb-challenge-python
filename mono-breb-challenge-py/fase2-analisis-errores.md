# Fase 2 — Detección y análisis de errores

Para cada caso se documenta: **causa raíz**, **referencia en la documentación**
de Bre-B Participant y **corrección propuesta**. Todas las referencias se
verificaron contra `docs.mono.la/docs/api-reference/breb-participant` el
11 de julio de 2026.

---

## Caso 1 — El recaudo se marcó como pagado, pero el comercio nunca recibió el dinero

**Evidencia:** `GET /api/v1/collections/{id}` devuelve `state: "minimum_paid"`,
con `total_maximum_amount = $50.000`, `total_minimum_amount = $20.000` y
`paid_amount = $20.000`. La lógica de la app es: `state != "created" → mostrar "Pagado"`.

### Causa raíz

La aplicación trata **cualquier estado distinto de `created`** como
"pagado por completo". Pero `minimum_paid` es un estado intermedio: el
recaudo ya recibió al menos el monto mínimo configurado, pero **sigue
abierto** para seguir recibiendo pagos hasta alcanzar el monto máximo. El
comercio esperaba los $50.000 completos y solo se han pagado $20.000 —
exactamente el mínimo, ni un peso más.

### Referencia en la documentación

El webhook `collection.minimum_paid` (Collection Webhooks) lo dice
explícitamente: se dispara cuando `paid_amount` alcanza o supera
`total_minimum_amount`, y aclara que *"the collection can still receive
more payments until it reaches `paid` state"*. Es decir, `minimum_paid` y
`paid` son dos eventos y dos estados distintos en el ciclo de vida del
recaudo (`collection.created` → `collection.ready` → `collection.minimum_paid`
→ `collection.paid`, con `collection.failed`/`collection.discarded` como
salidas de error).

### Corrección propuesta

Reemplazar la condición `state != "created"` por una verificación explícita
de `state === "paid"` (o, de forma más robusta, comparar
`paid_amount.amount >= total_maximum_amount.amount`) antes de mostrar
"Pagado" al comercio. Mientras el estado sea `minimum_paid`, la UI debe
mostrar algo como "Pago parcial — recaudo aún abierto" y la integración
debe seguir escuchando el webhook `collection.paid` (o consultar
periódicamente el recaudo) hasta la confirmación final. Esta corrección ya
está implementada en la Fase 1 (`src/routes/collections.js`, función
`humanCollectionState`).

---

## Caso 2 — Una transferencia aparece como "exitosa" y minutos después figura como fallida

**Evidencia:** `POST /api/v1/outgoing_transfers` responde `202 Accepted`
con `state: "processing"`. La app registra de inmediato "Transferencia
exitosa ✅". Minutos después llega el webhook `outgoing_transfer.failed`
con `state_reason: "provider_unavailable"`.

### Causa raíz

La aplicación interpreta la respuesta síncrona del `POST` (HTTP 202,
`state: "processing"`) como una confirmación final de éxito. Pero un
`202 Accepted` con estado `processing` significa exactamente eso: la
transferencia fue **aceptada para procesar**, no que se completó. El
resultado real (exitoso o fallido) llega después, de forma asíncrona.

### Referencia en la documentación

Los eventos listados en *Outgoing Transfer Webhooks* muestran todo el
ciclo de vida de una transferencia: `outgoing_transfer.created` →
`target_resolved` → `processing` → `held` (opcional) →
`send_to_breb_provider` → y solo entonces `successful` o `failed`. De ese
listado se desprende que `processing` es uno de varios estados
**intermedios**, y que únicamente `successful` y `failed` son estados
**finales/terminales** del ciclo de vida.

### Corrección propuesta

Nunca marcar una transferencia como exitosa a partir de la respuesta del
`POST`. Guardar el registro con un estado "en proceso" y actualizar la UI
solo al recibir el webhook `outgoing_transfer.successful`, o al consultar
`GET /api/v1/outgoing_transfers/{id}` y confirmar `state === "successful"`.
Además, como salvaguarda de contabilidad, implementar una conciliación
periódica (polling de respaldo) para transferencias que permanezcan en
`processing` más tiempo del esperado, por si un webhook se perdiera. Esta
corrección ya está implementada en la Fase 1 (`src/routes/transfers.js`,
constantes `NON_FINAL_STATES` / `FINAL_STATES`).

---

## Caso 3 — Todas las peticiones responden 401

**Evidencia:** `GET /api/v1/collections` (y, según el enunciado, cualquier
otra llamada) devuelve `401 Unauthorized` con `error_code: "invalid_token"`
y mensaje `"Authorization header is missing or invalid."`.

### Causa raíz

Que el fallo sea **simultáneo en todas las peticiones** (no en una
puntual) apunta a un problema con el token de acceso compartido por toda
la integración, no con una petición individual. El `error_code` es
`invalid_token` (no `missing_authorization_header`), lo que indica que sí
se está enviando un header `Authorization`, pero el token que contiene ya
no es válido — la causa más común es que **expiró** y la integración lo
siguió reutilizando sin renovarlo.

### Referencia en la documentación

`POST /api/v1/oauth/token` (Authentication) usa el flujo OAuth 2.0 *Client
Credentials* y su respuesta incluye `expires_in: 3600` (el token vive 1
hora) además de un `refresh_token`. La documentación también expone
`POST /api/v1/oauth/revoke` e `/introspect` para gestionar explícitamente
el ciclo de vida de un token, lo que confirma que los tokens tienen una
vida útil limitada y deben renovarse.

### Corrección propuesta

Implementar un gestor de tokens que:

1. Cachee el `access_token` junto con su tiempo de expiración.
2. Lo renueve **proactivamente** antes de que expire (con un margen de
   seguridad, p. ej. 60 segundos), usando `client_credentials` o
   `refresh_token`.
3. Ante cualquier `401` con `invalid_token`, invalide el token en caché y
   reintente la petición original **una vez** con un token nuevo antes de
   reportar el error al usuario final.

Esta corrección ya está implementada en la Fase 1
(`src/services/monoAuth.js` y `src/services/monoClient.js`).

---

## Caso 4 — Se quería cobrar $50.000, pero al cliente le cobraron $500

**Evidencia:** `POST /api/v1/collections` se configuró con
`"total_maximum_amount": {"amount": 50000, "currency": "COP"}`, pero el
intento exitoso de pago muestra $500,00 COP — exactamente 100 veces menos.

### Causa raíz

La API expresa todos los montos como enteros en la **unidad menor** de la
moneda (centavos para COP), no en pesos. El comercio (o su integración)
envió `50000` pensando que representaba $50.000 pesos, pero la API lo
interpretó como 50.000 centavos, es decir, $500,00 COP. La proporción del
error (exactamente ÷100) es la huella típica de una confusión de unidad
monetaria, no de un error de digitación.

### Referencia en la documentación

Todos los ejemplos de request/response que incluyen montos —
`create_collections`, `get_collection`, `create_outgoing_transfers`,
`resolve_target` — usan consistentemente objetos `{amount, currency}`
donde valores como `"amount": 100000000` representan $1.000.000 COP en los
ejemplos ilustrados junto a la maqueta de "Detalle de recaudo" del reto
(que muestra montos en pesos legibles para el usuario, pero la API los
recibe en centavos).

### Corrección propuesta

Nunca enviar a la API el valor que el usuario escribe en pesos sin
convertirlo. Centralizar la conversión pesos → centavos
(`Math.round(pesos * 100)`) en un único punto del código antes de
cualquier llamada a la API, y la conversión inversa (centavos → pesos,
dividir entre 100) al mostrar cualquier monto que venga de la API.
Adicionalmente, agregar una prueba automatizada que verifique, por
ejemplo, que crear un recaudo de $50.000 genere en el payload
`"amount": 5000000` y no `50000`. Esta corrección ya está implementada en
la Fase 1 (`src/utils/money.js`, usado desde `collections.js` y
`transfers.js`).

---

## Caso 5 — Una transferencia nunca llega a su destino

**Evidencia:**

```
POST /api/v1/targets/resolve   { "creditor_key_value": "MN1234567890" }
--- webhook ---
target_resolution.failed
outgoing_transfer.failed  { "state_reason": "invalid_key_format" }
```

### Causa raíz

Hay dos problemas encadenados:

1. **El payload no sigue el contrato documentado.** `POST /api/v1/targets/resolve`
   espera un cuerpo con `tenant_account_id`, `format` (por ejemplo
   `"plain_key"`) y `value` (el valor de la llave) — no un campo
   `creditor_key_value`. Con ese payload, la API ya recibiría una petición
   mal formada.
2. **El valor de la llave no corresponde a ningún formato válido de Bre-B.**
   `"MN1234567890"` no es un celular, un correo, ni un número de
   identificación puro. Si la intención era usar una llave alfanumérica,
   le falta el prefijo obligatorio `@` con el que **siempre** inician esas
   llaves en el sistema Bre-B.

### Referencia en la documentación

`POST /api/v1/targets/resolve` (Resolve target) documenta explícitamente
el esquema del body (`format` + `value`, con `format` en
`"plain_key"`/`"image"`/`"emvco"`/`"emvco_b64"`). El ejemplo de
`create_collections` muestra el formato real de una llave alfanumérica
generada por Bre-B: `"value": "@MONO1A2B3C4D5E"`, siempre con `@` al
inicio — consistente con el estándar público del sistema Bre-B, donde toda
llave alfanumérica (Tag Aval, Llave Nu, llave Bancolombia, etc.) comienza
con `@`.

### Corrección propuesta

1. Corregir la integración para enviar el body según el contrato
   documentado: `{ tenant_account_id, format: "plain_key", value: "<llave>" }`.
2. Agregar validación del lado del cliente **antes** de llamar a la API:
   verificar que el valor ingresado corresponda a alguno de los formatos
   válidos de llave Bre-B (celular, correo electrónico, número de
   documento, o alfanumérica que inicia con `@`), y mostrar un error claro
   de inmediato si no cumple el patrón, en lugar de dejar que la
   resolución del target y la transferencia fallen más adelante en un flujo
   asíncrono, sin que el usuario sepa por qué. En la Fase 1
   (`src/routes/transfers.js`) el flujo ya resuelve el target de forma
   explícita antes de crear la transferencia, precisamente para detectar
   este tipo de error en el primer paso y no después de haber "enviado" el
   dinero.
