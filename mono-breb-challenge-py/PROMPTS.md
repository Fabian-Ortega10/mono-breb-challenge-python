# Evidencia de uso de herramientas de IA

Este reto se desarrolló usando **Claude** como apoyo durante todo el proceso,
tal como lo sugiere el enunciado. A continuación documento cómo se usó, no
solo que se usó, incluyendo dónde tuve que corregir o completar lo que la IA
propuso.

## 1. Comprensión de la documentación (antes de escribir código)

Antes de generar cualquier línea de código, le pedí a Claude que leyera la
documentación oficial de Bre-B Participant (`docs.mono.la/docs/api-reference/breb-participant`)
y sus subpáginas: autenticación OAuth, `collections`, `outgoing-transfers`,
`target resolution`, y los webhooks de cada recurso. El objetivo era anclar
la implementación a los contratos reales de la API (nombres de campos,
estados posibles, formato de errores) en lugar de asumirlos por
familiaridad con otras APIs de pagos.

**Prompt usado (resumen):**
> "Lee la documentación de Bre-B Participant de Mono: endpoints de
> autenticación, collections y outgoing transfers. Necesito los estados
> posibles de un `collection` y de un `outgoing_transfer`, y el formato
> exacto de los errores que devuelve la API, antes de escribir el backend."

Esto fue clave para no cometer exactamente los errores que la Fase 2 pide
diagnosticar (por ejemplo, confundir `minimum_paid` con `paid`, o tratar
`processing` como estado final).

## 2. Diseño de la arquitectura

Le pedí a Claude que propusiera una estructura de proyecto simple (sin
framework de frontend) que separara claramente:

- autenticación OAuth con cache/renovación de token,
- el cliente HTTP hacia Mono,
- las rutas de negocio (recaudos, transferencias),
- el manejo de errores centralizado,
- la conversión de montos (pesos ↔ centavos).

**Prompt usado (resumen):**
> "Diseña la estructura de un backend Express que hable con la API de Bre-B
> Participant, separando el manejo de token OAuth, el cliente HTTP y las
> rutas de negocio, de forma que el manejo de errores y la conversión de
> montos estén en un solo lugar cada uno (no repetidos por ruta)."

## 3. Generación de código, iterando contra la documentación real

El código de `monoAuth.js`, `monoClient.js`, `collections.js` y
`transfers.js` se generó con Claude y luego se verificó campo por campo
contra los ejemplos de request/response de la documentación (por ejemplo,
que `POST /api/v1/collections` espera `{ tenant_account_id, collections: [...] }`
y no un objeto plano; que `POST /api/v1/outgoing_transfers` requiere
`target_id` u otro método de query, no la llave directamente).

**Corrección manual que tuve que hacer:** la primera versión que propuso
Claude enviaba el monto de la transferencia directamente en pesos. Lo
corregí explícitamente después de confirmar en la documentación que la API
espera el monto en la unidad menor de la moneda (centavos) — el mismo
problema que se pide diagnosticar en el Caso 4 de la Fase 2. Esa
verificación quedó centralizada en `utils/money.js` con un comentario
explicando por qué existe.

## 4. Manejo de errores

**Prompt usado (resumen):**
> "Todas las respuestas de error de esta API comparten esta forma:
> `{code, message, id, errors: [{error_code, message}]}`. Escribe un
> normalizador que la convierta en algo consistente, con mensajes en
> español para el usuario final, y úsalo en todas las rutas."

## 5. Fase 2 — Análisis de errores

Para cada uno de los 5 casos, usé a Claude para contrastar el síntoma
descrito con:

1. el estado/campo exacto documentado (por ejemplo, la existencia del
   webhook `collection.minimum_paid` como estado distinto de
   `collection.paid`),
2. el comportamiento esperado documentado (por ejemplo, que
   `outgoing_transfer.processing` no es un estado final y que solo
   `successful`/`failed` lo son),
3. el formato de llave Bre-B documentado por el operador del sistema
   (llaves alfanuméricas siempre inician con `@`).

El análisis final en `fase2-analisis-errores.md` se escribió y revisó
manualmente para asegurar que cada causa raíz cita la referencia correcta
de la documentación y no una suposición genérica.

## 6. Conversión de Node.js a Python

La primera versión de la Fase 1 se construyó en Node.js/Express. Se le pidió
a Claude convertirla a Python manteniendo exactamente la misma arquitectura
(gestor de token OAuth, cliente HTTP con reintento ante 401, conversión de
montos centralizada, blueprints equivalentes a las rutas de Express) para
no perder ninguna de las correcciones ya verificadas contra los 5 casos de
la Fase 2.

**Prompt usado (resumen):**
> "Convierte este backend de Node/Express a Python/Flask manteniendo la
> misma estructura de carpetas y la misma lógica de negocio (nada de
> reinterpretar los endpoints o los estados desde cero), y vuelve a probar
> que el servidor levante y responda /api/health."

**Verificación manual:** se reinstalaron las dependencias (`pip install`),
se levantó el servidor Flask localmente y se confirmó que `/api/health`,
`/` (frontend) y una ruta inexistente (404) responden igual que en la
versión Node, antes de dar la conversión por terminada.

## Herramienta y versión

- Modelo: Claude (Anthropic), a través de la interfaz de chat con acceso a
  búsqueda web para leer `docs.mono.la` en tiempo real.
- Todo el código generado fue ejecutado localmente (`npm install`,
  arranque del servidor, prueba de `/api/health`) antes de darlo por
  entregado.
