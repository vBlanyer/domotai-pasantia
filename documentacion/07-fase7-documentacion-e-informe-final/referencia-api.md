# Referencia de la API HTTP del daemon

La API que sirve el daemon en vivo (`prototipo/servicio/tablero.py`, lanzado por `stream.py --web`). La
consume el **visor** (consola web) y puede consumirla cualquier cliente local. **No** es la interfaz
de salida canónica hacia el cliente (esa es la **traza JSONL**, RF-13); es la interfaz de
lectura/aprobación de la consola.

- **Dirección:** `http://127.0.0.1:<puerto>` (por defecto `8787`). **Liga solo a loopback**: no es
  accesible desde la red. Exponerla a otros es trabajo de un proxy del cliente (ver la guía de integración).
- **Formato:** JSON en cuerpo y respuesta. Los errores son `{"error": "<texto>"}` con el código HTTP.
- Los esquemas autoritativos de respuesta viven, validados con Zod, en `visor/src/api.ts`; los
  construye `prototipo/servicio/tablero.py`.

## Modelo de seguridad

| Control | Qué hace | Si falla |
|---------|----------|----------|
| **Host** | La cabecera `Host` debe ser localhost (anti DNS-rebinding) | `403 host no permitido` |
| **Token** (opcional, #6) | Si el daemon arrancó con `TRIAJE_CONSOLA_TOKEN` (o tokens de operador), `/api/*` exige `Authorization: Bearer <token>` | `401 no autorizado` |
| **Origin** (solo POST, anti-CSRF) | Un POST con `Origin` de un sitio ajeno se rechaza; sin `Origin` (curl) se permite | `403` |
| **CORS** | Se refleja el `Origin` solo si es localhost (nunca `*`): una web de terceros no puede leer la API | — |
| **Tope de cuerpo** (POST) | `Content-Length` acotado; uno negativo se rechaza | `413` |

Los **estáticos** (el visor) no exigen token, para que la SPA cargue y pida el token al operador. El
**operador** de un POST sale del token (autoritativo, no repudio) o, en su defecto, del campo
`operador` del cuerpo.

## Endpoints de lectura (GET)

| Ruta | Parámetros | Devuelve |
|------|-----------|----------|
| `GET /healthz` | — | Salud del **propio MDR**: `{ok, alertas, lazo_quietud_s, ingesta_silencio_s}`. `ok=false` si el lazo lleva demasiado tiempo sin iterar (colgado). Distinto de `/api/salud`. |
| `GET /api/salud` | — | Salud de los **servicios del cliente** (por servicio + dependencias). |
| `GET /api/red` | — | Mapa de la red con la actividad por equipo (`{nodos, zonas, enlaces}`). |
| `GET /api/decisiones` | — | Las últimas 50 decisiones (resumen por fila). |
| `GET /api/pendientes` | — | La **cola de aprobación** (array), ordenada por severidad. Cada ítem: `{id, tipo, prompt, lineas, severidad, suprimidas, paso, accion_final, activo, origen_ip, encolado_en}`. |
| `GET /api/trazas` | `limite` (opc.) | La cola de la traza encadenada (últimos N registros, decisiones + reversiones + actualizaciones de caso…). |
| `GET /api/traza/<id>` | `indice` (opc.) | El **detalle completo** de una decisión (justificación, ejecución, verificación, escalada, pasajes del RAG, impacto determinado). `404` si no existe. |
| `GET /api/caso/<id>` | — | El **ciclo de caso** de una decisión, plegado sobre el fichero completo: `{estado, asignado, notas[], actualizado_en?}`. Sin actualizaciones: `{estado:"nuevo", asignado:null, notas:[]}` (el caso no «rejuvenece» al salir de la ventana de `/api/trazas`). |
| `GET /api/verificar` | — | Integridad de la cadena de hashes: `{ok, roto_en?, motivo?}`. |
| `GET /api/contenciones` | — | Las contenciones **activas** ahora mismo (array). |
| `GET /api/pausa` | — | Estado del *kill switch*: `{pausada: bool}`. |
| `GET /api/metricas` | `desde`, `hasta` (YYYY-MM-DD, opc.) | Métricas: `{total, fp, tasa_fp, auto, escalado_humano, tasa_override, mttr_seg, por_clase, veredictos, por_dia, top_activos, mitre, desde, hasta}`. Con periodo agrega **todo** el histórico (para el informe); sin él, la ejecución actual. |

## Endpoints de acción (POST)

Requieren `Origin` localhost (si viene de navegador) y token si está configurado. Cuerpo JSON.

| Ruta | Cuerpo | Devuelve |
|------|--------|----------|
| `POST /api/aprobar` | `{id, respuesta, paso?, operador?}` | `{ok:true}` · `409` si la decisión ya no está vigente (la resolvió otro o cambió el menú). `respuesta` = la opción del menú (`"s"`/`""` en escaladas; nº de opción / clase al reclasificar). |
| `POST /api/caso` | `{id, estado?, asignado?, nota?, operador?}` | `{ok:true}` · `400` si `estado` no es válido o la actualización está vacía · `409` en modo bloqueante. `estado` ∈ `{nuevo, en_revision, resuelto}`. Añade un registro `actualizacion_caso` **encadenado** (no muta la decisión). |
| `POST /api/pausa` | `{pausar: bool}` | `{pausada: bool}`. *Kill switch*: con `true`, toda contención automática pasa a esperar humano. |
| `POST /api/revertir-todo` | `{confirmar: true, operador?}` | Resultado del **des-bloqueo en masa** (revierte todas las contenciones activas). Sin `confirmar: true` → `400` (gesto explícito: levanta todos los bloqueos del atacante); si ya hay uno en curso → `409` (exclusión mutua). |

## Códigos de estado

`200` OK · `400` cuerpo/parámetro inválido · `401` falta token · `403` Host/Origin no permitido ·
`404` ruta o recurso no encontrado · `409` acción no vigente / no disponible en este modo ·
`413` cuerpo demasiado grande · `500` error del handler (nunca tumba el servidor).

## Ejemplos

```sh
# Salud del propio daemon (monitor local)
curl -fsS http://127.0.0.1:8787/healthz
# {"ok": true, "alertas": 142, "lazo_quietud_s": 0.3, "ingesta_silencio_s": 12.0}

# Cola de aprobación (con token, si la consola lo exige)
curl -fsS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8787/api/pendientes

# Aprobar una decisión pendiente
curl -fsS -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"id":"7","respuesta":"1","operador":"ana"}' http://127.0.0.1:8787/api/aprobar

# Anotar el caso de una decisión (estado + nota)
curl -fsS -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"id":"s12","estado":"resuelto","nota":"C2 confirmado y bloqueado"}' http://127.0.0.1:8787/api/caso

# Informe del mes (métricas agregadas del periodo)
curl -fsS "http://127.0.0.1:8787/api/metricas?desde=2026-10-01&hasta=2026-10-31"
```

> Nota: las acciones (`/api/aprobar`, `/api/caso`, `/api/revertir-todo`, `/api/pausa`) ejecutan o
> cambian estado real y quedan en la traza con el operador (no repudio). Trátalas con el mismo cuidado
> que una contención manual.
