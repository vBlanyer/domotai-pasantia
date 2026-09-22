# Tablero web de observabilidad y aprobación — diseño

**Fecha:** 22/09/2026 · **Estado:** diseño aprobado en brainstorming; pendiente de revisión antes del plan.

**Contexto.** Hoy toda la observabilidad e interacción del prototipo es por **terminal o ficheros**:
el panel de salud `lab/banco/panel.py` (TUI), el monitor que escribe `salud.jsonl`, el feed de
decisiones que imprime `stream.py`, las trazas encadenadas por hash y los `informe.md`. No existe
ninguna interfaz web (confirmado: no hay Flask/FastAPI ni `http.server` sirviendo UI en el repo; la
única marca es D11 en `documentacion/00-general/estado-y-riesgos.md`: «la interacción es por terminal;
una UI gráfica queda como trabajo futuro»). La aprobación humana de una contención se pide por `[s/N]`
en la terminal.

**Objetivo.** Una **consola web local** que reúna lo que hoy está disperso —estado de servicios/equipos,
feed de decisiones en vivo, cola de aprobaciones y explorador de trazas— y que **permita aprobar o
rechazar una contención desde el navegador**, reutilizando la costura de aprobación que ya existe en el
lazo. Es la primera versión («etapa inicial»): simple, sin autenticación, solo `127.0.0.1`.

## 1. Alcance

**Dentro (v1):**
- Cuatro paneles: **Salud** (nodos verde/rojo + dependencias + línea de tiempo), **Decisiones** (feed en
  vivo del daemon), **Aprobaciones** (cola de decisiones que esperan humano, con aprobar/rechazar) y
  **Trazas** (lista → detalle + verificación de la cadena).
- Servidor **stdlib** (`http.server`), front **HTML/CSS/JS vanilla** sin build.
- Aprobación desde la web integrada en el daemon reutilizando la costura `leer=`.

**Fuera (v1), anotado:**
- Autenticación/login y TLS (se eligió sin auth, solo localhost).
- *Push*/websockets (se usa sondeo).
- Persistencia histórica más allá de los ficheros existentes.
- Control del laboratorio desde la web (levantar/bajar/atacar).
- Multi-cliente.
- Etiquetas ricas del menú de reclasificación (si el contexto capturado no basta, se degrada a mostrar
  el prompt crudo con un campo de texto).

## 2. Decisiones fijadas (del brainstorming)

- **Pila:** Python 3 stdlib + PyYAML, sin pip/venv/pytest. `http.server` + HTML/JS a mano.
- **Seguridad:** el servidor liga solo a `127.0.0.1`; **sin autenticación** en la v1. El `id` de una
  pendiente evita aprobar una decisión caduca, pero **no es un control de seguridad**.
- **Acoplamiento:** Enfoque 1 — **servidor embebido en el daemon** (`stream.py --web`). Un solo proceso;
  las aprobaciones se resuelven por memoria compartida (sin IPC). El módulo puede además arrancarse
  **suelto en modo solo-lectura** (salud + trazas) cuando no hay daemon.
- **Paneles v1:** los cuatro.

## 3. Arquitectura y componentes

Un módulo nuevo, **`prototipo/tablero.py`**, que levanta un `ThreadingHTTPServer` en `127.0.0.1:<puerto>`
(por defecto 8787) y sirve una página estática más una **API JSON**. `lab/banco/panel.py` (terminal) se
deja intacto.

| Pieza | Responsabilidad | Depende de |
|---|---|---|
| `prototipo/tablero.py` | El servidor: rutas, endpoints JSON y el estado compartido. | stdlib `http.server`; reúsa `traza.py` y `lab/banco/panel.py` |
| `EstadoTablero` (clase en `tablero.py`) | Estado en memoria, con `Lock`: buffer circular de decisiones recientes (feed), registro de pendientes (cada una con su `Event`, sus líneas capturadas y su hueco de respuesta) y el buffer de líneas del incidente en curso. | `threading` |
| `LectorWeb` (clase en `tablero.py`) | La costura de aprobación: un callable `leer(prompt) -> str` que registra una pendiente y bloquea en su `Event` hasta que la web responde. Espeja a `Lector`/`LectorContador` del banco de pruebas. | `EstadoTablero` |
| `escribir_web` (función/clausura en `tablero.py`) | Envuelve el `escribir` del daemon: imprime como siempre **y** registra la línea en `EstadoTablero` (buffer del incidente en curso + feed). | `EstadoTablero` |
| `prototipo/tablero/` (estáticos) | `index.html`, `tablero.js`, `tablero.css`, servidos tal cual. | — |
| `prototipo/stream.py` (modificado) | Bandera `--web [puerto]`: arma `EstadoTablero`, `LectorWeb` y `escribir_web`, arranca el servidor en un hilo y los inyecta en `ejecutar(...)`. | `tablero.py` |

**Cómo corre.** Con el banco levantado y el monitor escribiendo `salud.jsonl`:
`python3 -m prototipo.stream <fuente> ... --web`. El daemon procesa como siempre; el hilo del servidor
expone salud (lee `salud.jsonl`), el feed (del estado compartido), las pendientes y las trazas (leen el
fichero de traza). Sin daemon, `prototipo/tablero.py` puede arrancarse suelto para los paneles de solo
lectura.

## 4. El puente de aprobación

Hoy `_procesar_incidente` (`stream.py:57-69`) llama a `lazo.procesar_lazo(rep, ..., leer=leer)`; el dict
final `d` de la decisión **solo existe cuando `procesar_lazo` retorna**, es decir, **después** de que el
humano responde. Por eso la tarjeta de aprobación no puede mostrar `d`: se arma de lo que el operador
**ve impreso** justo antes del prompt (resumen del incidente, clase, acción propuesta, impacto y, si lo
hay, el menú), que se captura envolviendo el `escribir`.

**Mecánica:**
1. Para `--web`, `stream.py` inyecta un `escribir_web` que imprime y **acumula las líneas del incidente
   en curso** en `EstadoTablero`, y las empuja también al feed.
2. Cuando el lazo llama a `leer(prompt)`, `LectorWeb`:
   - clasifica el prompt **con la misma regla que `Lector`**: `tipo = "escalada"` si `"[s/N]"` está en el
     prompt, si no `"menu"`;
   - registra una pendiente `{id, lineas_capturadas, tipo, prompt, Event, respuesta}` en `EstadoTablero`;
   - **bloquea en el `Event`**.
3. La web muestra la pendiente (las líneas capturadas + el control adecuado). Al pulsar,
   `POST /api/aprobar {id, respuesta}` deja la respuesta y libera el `Event`; `LectorWeb` devuelve esa
   cadena al lazo — `"s"` para escalada, el índice del menú para reclasificar/aprobar — **exactamente lo
   que el lazo espera de la terminal**.
4. Al retornar `procesar_lazo`, `_linea_decision(d)` se emite por `escribir_web` y `d` se registra en el
   feed y en la traza (comportamiento actual, sin cambios).

**Detalles honestos:**
- **Sin respuesta = bloquea**, igual que la terminal (el lazo es secuencial). Un `timeout` opcional en
  `LectorWeb`, **apagado por defecto**, devuelve la respuesta segura (rechazar / `""`) si vence, para no
  cambiar el comportamiento actual salvo que se pida.
- `EstadoTablero` protege con un `Lock` el buffer de decisiones, el dict de pendientes y el buffer del
  incidente en curso. El daemon bloquea en su hilo; el manejador HTTP libera el `Event` desde el hilo del
  servidor.
- No se cambia ninguna firma dentro de `lazo.py`/`validacion.py`: solo se envuelven el `escribir` y el
  `leer` que `stream.py` ya inyecta. Es el mismo patrón de inyección que usó el banco de pruebas.

## 5. API JSON

Todo bajo `127.0.0.1:<puerto>`. Cuerpos y respuestas en JSON (`Content-Type: application/json`), salvo
los estáticos.

| Método · ruta | Devuelve | Fuente |
|---|---|---|
| `GET /` · `GET /static/<f>` | La página y sus `tablero.js`/`tablero.css`. | `prototipo/tablero/` |
| `GET /api/salud` | `{t, servicios:[{nombre,estado,desde,depende_de,no_declarada}], caidos, total}` o `{sin_datos:true}`. | `panel.leer_ultima` + `red.py` |
| `GET /api/decisiones` | Feed reciente: `[{id_decision,timestamp,activo,clase,confianza,accion_final,requiere_humano,impacto}]`. | `EstadoTablero` |
| `GET /api/pendientes` | `[{id, lineas, tipo, prompt}]`. | `EstadoTablero` |
| `POST /api/aprobar` | Cuerpo `{id, respuesta}` → `{ok:true}`; `409` si el id ya no existe o ya se resolvió. | libera el `Event` |
| `GET /api/trazas` | Lista de decisiones de la traza (resúmenes, mismo shape que el feed). | fichero de traza |
| `GET /api/traza/<id>` | El registro completo (justificación, RAG, orden, ejecución, hashes); `404` si no está. | fichero de traza |
| `GET /api/verificar` | `{ok:bool, roto_en?:<id>}`. | `traza.verificar` |

Rutas configurables por bandera con valores por defecto (puerto 8787; fichero de traza = la
`salida_traza` del daemon; salud = el `salud.jsonl` del banco vía `docker exec`, como `panel.py`).

## 6. Frontend

Una `index.html` con **4 pestañas** (Salud · Decisiones · Aprobaciones · Trazas) y `tablero.js` **vanilla**
que **sondea** cada ~2 s (como el refresco de `panel.py`; sin websockets, que la stdlib no trae cómodo):
- **Salud:** tabla verde/rojo de los nodos con dependencias y «desde hace», más los últimos cambios
  (mismos datos y colores que el panel de terminal).
- **Decisiones:** el feed, una fila por incidente resuelto.
- **Aprobaciones:** una tarjeta por pendiente con las líneas capturadas y los botones **Aprobar/Rechazar**
  (tipo escalada) o las opciones numeradas (tipo menú), que hacen `POST /api/aprobar`.
- **Trazas:** lista → detalle (el registro completo) + botón «verificar cadena» (`GET /api/verificar`).

`tablero.css` mínimo; sin dependencias de front.

## 7. Errores (degradar, no romper)

- Sin `salud.jsonl` (banco no levantado) → el panel de salud muestra «sin datos».
- Sin daemon → feed y pendientes vacíos, pero la página y los paneles de salud/trazas funcionan.
- Sin fichero de traza → lista vacía; `GET /api/traza/<id>` desconocido → `404`.
- `POST /api/aprobar` con id caduco/desconocido o ya resuelto → `409`.
- Cualquier excepción en un handler → `500` con cuerpo JSON `{error}`; nunca tumba el servidor.

## 8. Pruebas (unittest, stdlib)

Mismo patrón que `lab/banco/tests/test_servicio.py`: arrancar el servidor en un puerto efímero y golpearlo
con `http.client`.
- Cada `GET` devuelve el JSON esperado alimentando un `EstadoTablero` sembrado, un fichero de traza
  temporal y una **fuente de salud falsa inyectada** (sin docker).
- `POST /api/aprobar` libera el `Event` de una pendiente y `LectorWeb` devuelve la respuesta; id
  desconocido/resuelto → `409`.
- `LectorWeb` clasifica escalada vs menú **igual que `Lector`**; con `timeout` activo y vencido devuelve la
  respuesta segura (`""`).
- `escribir_web` imprime **y** acumula la línea en el incidente en curso y en el feed.
- El servidor liga solo a `127.0.0.1`.
- Verificación de traza: cadena íntegra → `{ok:true}`; cadena alterada → `{ok:false, roto_en}` (reusando
  `traza.verificar`).

## 9. Ficheros

- **Crear:** `prototipo/tablero.py` (servidor + `EstadoTablero` + `LectorWeb` + `escribir_web`).
- **Crear:** `prototipo/tablero/index.html`, `prototipo/tablero/tablero.js`, `prototipo/tablero/tablero.css`.
- **Crear:** `prototipo/tests/test_tablero.py`.
- **Modificar:** `prototipo/stream.py` — `parsear_args` (`--web [puerto]`), `main` (arma el estado, el
  lector y el `escribir` web, arranca el hilo del servidor y los inyecta en `ejecutar`).
- **Reúsa (sin duplicar):** `lab/banco/panel.py` (`leer_ultima`, dependencias vía `red.py`),
  `prototipo/traza.py` (lectura y `verificar`), el patrón `Lector`/`LectorContador` de
  `lab/banco/pruebas.py`.

## 10. Riesgos y notas honestas

- **R1 · La aprobación dispara `iptables` real desde un clic sin auth.** Mitigación v1: liga solo a
  `127.0.0.1`; la traza registra la aprobación (auditable). Se asume máquina del operador (RNF-01). La
  autenticación queda para una v2.
- **R2 · El daemon bloquea mientras espera aprobación.** Es el comportamiento actual (secuencial); la web
  sigue respondiendo porque el servidor está en otro hilo. El `timeout` opcional es la válvula.
- **R3 · La salud es específica del banco** (`salud.jsonl` vía `docker exec` a `clab-banco-mdr-siem`). En
  la red pequeña ese panel diría «sin datos». Se acepta para la v1 (el banco es el escenario insignia); la
  ruta/fuente de salud queda configurable para generalizar después.
- **R4 · Sondeo, no *push*.** ~2 s de latencia en los paneles; suficiente para observación, coherente con
  el refresco del panel de terminal.
- **R5 · Reclasificación por menú.** Si las líneas capturadas no bastan para etiquetar las opciones, se
  degrada a mostrar el prompt crudo con un campo de texto (la respuesta sigue siendo la cadena que el lazo
  espera).

## 11. Criterios de éxito

- `python3 -m prototipo.stream <fuente> ... --web` levanta la consola en `127.0.0.1:8787` con los cuatro
  paneles; un incidente que requiere humano aparece en Aprobaciones y, al pulsar Aprobar, la contención se
  ejecuta y la decisión pasa al feed y a la traza.
- Los paneles de salud y trazas funcionan también sin daemon (modo solo lectura).
- `prototipo/tests` en verde, incluidos los nuevos de `test_tablero.py`; sin regresión en el resto de
  suites.
- Sin dependencias nuevas (stdlib + PyYAML).
