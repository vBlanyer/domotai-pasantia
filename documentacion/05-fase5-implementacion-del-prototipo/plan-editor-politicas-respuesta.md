# Editor de políticas de respuesta — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer editable la vista «Políticas» del visor para configurar, por tipo de ataque y por zona/dispositivo, qué se contiene en automático y qué exige humano, sin poder debilitar nunca los frenos de seguridad ni mover las cifras canónicas.

**Architecture:** Dos compuertas nuevas y aditivas en `motor/perfil.filtrar` que **solo degradan** a humano (familia y zona/dispositivo), compuestas por «gana la más restrictiva» con las compuertas actuales. Persistencia en una **copia operativa** (overlay YAML) que se fusiona solo al arrancar el daemon; el canónico no se toca. Backend reestructura `GET /api/politica` a objeto y añade un `POST /api/politica` fail-closed con auditoría. El visor convierte la vista a editable con dos pestañas y una nota de interferencia.

**Tech Stack:** Python 3 (stdlib + PyYAML), `unittest`. Visor React/TS/Vite/Zod/shadcn, `vitest`.

**Spec:** `documentacion/04-fase4-diseno-de-arquitectura/editor-de-politicas-respuesta.md`

## Global Constraints

- Python: **solo stdlib + PyYAML**. Visor: **sin dependencias nuevas**. Offline, sin egreso (RNF-01).
- **Aditivo:** con las claves nuevas ausentes, `filtrar` y la evaluación dan resultados **idénticos** a hoy.
- Las compuertas nuevas **solo pueden degradar auto→humano**, nunca subir a auto; los frenos duros (`nunca_automatica` `perfil.py:271`, `no_cortar_gestion`, reversibilidad, actores, umbral) mandan **después**.
- El perfil canónico `prototipo/perfiles/bancario.yml` **no se escribe** desde el visor. La copia operativa se fusiona **solo** en el arranque del daemon (`stream.main`), nunca dentro de `perfilm.cargar`.
- Vocabulario de posturas = enum del motor: `automatica_si_confianza` | `humano_siempre`.
- Trabajar en rama `feat/editor-politicas-respuesta`. **No hacer push** salvo que el usuario lo pida.
- Los mensajes de commit terminan con: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Review Focus

- **Familia destructiva puesta en AUTO:** `POST` con `dimension=familia`, familia cuya acción es `nunca_automatica` (p. ej. `malware`), `automatizacion=automatica_si_confianza` → debe responder **400**, no aceptarse en silencio. (Task 6)
- **Activo fuera de `red.zonas`:** un activo sin zona (p. ej. `objetivo-vuln` de los tests) con `politicas_por_zona` definido para otras zonas → **no recibe compuerta de zona**, se comporta como hoy. (Task 1)
- **POST sin identidad:** sin mapa `operadores` ni token configurado → **403** fail-closed, el cambio no se aplica. (Task 6)
- **Overlay que deja el perfil inválido:** un cambio que al fusionar no pasa `perfil.validar` → **400**, el perfil vivo y el fichero overlay **no** cambian. (Task 6)
- **Camino de evaluación:** `perfilm.cargar` (que usa `triaje_lote`) **nunca** ve el overlay aunque el fichero exista → conteos canónicos intactos. (Task 7)

---

### Task 1: Compuertas de postura en `motor/perfil.filtrar`

**Files:**
- Modify: `prototipo/motor/perfil.py` (añadir `familia=None` a `filtrar`; helpers de postura y zona; post-paso que degrada, al estilo de `_aplicar_actor`)
- Test: `prototipo/tests/test_politicas_editor.py` (nuevo)

**Interfaces:**
- Produces: `filtrar(perfil, accion_id, params, catalogo, activo, servicio, confianza, hallazgos=None, familia=None)`; `zona_de(perfil, activo) -> str | None`; `postura_efectiva(perfil, familia, activo) -> str | None` (devuelve `"humano_siempre"` si alguna dimensión lo exige, si no `None`; override de activo gana sobre la zona).

- [ ] **Step 1: Escribir los tests que fallan** en `test_politicas_editor.py`:
```python
def test_familia_humano_degrada_auto_a_humano():
    # perfil base donde BLOQUEAR_IP localizado saldría auto; con la familia en humano_siempre, no.
    p = {**base, "automatizacion_por_familia": {"reconocimiento": {"automatizacion": "humano_siempre"}}}
    r = perfil.filtrar(p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, catalogo, "web-banking", None, 0.99, familia="reconocimiento")
    assert r["requiere_humano"] is True and r["accion_final"] == "BLOQUEAR_IP"

def test_zona_humano_degrada():
    p = {**base, "politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}}}
    r = perfil.filtrar(p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, catalogo, "middleware", None, 0.99, familia="reconocimiento")
    assert r["requiere_humano"] is True

def test_override_activo_gana_sobre_zona():
    p = {**base, "overrides_por_activo": {"web-banking": {"automatizacion": "humano_siempre"}}}
    r = perfil.filtrar(p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, catalogo, "web-banking", None, 0.99, familia="reconocimiento")
    assert r["requiere_humano"] is True

def test_activo_sin_zona_no_recibe_gate():
    p = {**base, "politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}}}
    r = perfil.filtrar(p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, catalogo, "objetivo-vuln", None, 0.99, familia="reconocimiento")
    assert r["requiere_humano"] is False   # 'objetivo-vuln' no está en red.zonas

def test_posturas_ausentes_sin_efecto():
    # sin claves nuevas, el resultado es idéntico al baseline (auto sigue auto)
    r = perfil.filtrar(base, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, catalogo, "web-banking", None, 0.99, familia="reconocimiento")
    assert r["requiere_humano"] is False

def test_gate_no_sube_a_auto():
    # una familia destructiva puesta en auto NO se automatiza (freno duro manda)
    p = {**base, "automatizacion_por_familia": {"malware": {"automatizacion": "automatica_si_confianza"}}}
    r = perfil.filtrar(p, "AISLAR_NODO", {}, catalogo, "web-banking", None, 0.99, familia="malware")
    assert r["requiere_humano"] is True
```

- [ ] **Step 2: Ejecutar y ver fallar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politicas_editor -v` · Expected: FAIL (`filtrar() got unexpected keyword 'familia'`).

- [ ] **Step 3: Implementar.** Añadir `familia=None` a `filtrar`. Añadir `zona_de(perfil, activo)` (busca en `perfil["red"]["zonas"]`). Añadir `postura_efectiva(perfil, familia, activo)` (override de activo → zona → familia; devuelve `"humano_siempre"` si alguna lo exige). Al final de `filtrar`, **antes de devolver**, replicar el patrón de `_aplicar_actor`: si el resultado es auto (`accion_final` y no `requiere_humano`) y `postura_efectiva(...) == "humano_siempre"`, forzar `requiere_humano=True` conservando `accion_final`. No tocar nada más del flujo.

- [ ] **Step 4: Ejecutar y ver pasar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politicas_editor -v` · Expected: PASS.

- [ ] **Step 5: No-regresión del motor.** Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -p "test_*.py"` · Expected: PASS (conteo canónico sin cambios).

- [ ] **Step 6: Commit** — `feat(motor): compuertas de postura por familia y zona/dispositivo en filtrar (solo degradan)`.

---

### Task 2: Enhebrar la familia desde `triaje.procesar`

**Files:**
- Modify: `prototipo/motor/triaje.py` (la llamada a `perfilm.filtrar`, ~`:22`)
- Test: `prototipo/tests/test_politicas_editor.py`

**Interfaces:**
- Consumes: `filtrar(..., familia=...)` de Task 1.

- [ ] **Step 1: Test que falla:** `test_triaje_pasa_familia_a_filtrar` — procesar una alerta `reconocimiento` con el perfil que tiene `automatizacion_por_familia: {reconocimiento: humano_siempre}` y confianza alta debe dar un registro con `requiere_humano True` (hoy saldría auto).
- [ ] **Step 2: Ver fallar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politicas_editor -v` · Expected: FAIL.
- [ ] **Step 3: Implementar** — pasar `familia=alerta.get("familia")` en la llamada a `perfilm.filtrar` de `triaje.procesar`.
- [ ] **Step 4: Ver pasar** + `test_triaje` completo verde. Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_triaje prototipo.tests.test_politicas_editor -v`.
- [ ] **Step 5: Commit** — `feat(motor): triaje pasa la familia de la alerta a filtrar`.

---

### Task 3: Fusión del overlay + validación de posturas

**Files:**
- Modify: `prototipo/motor/perfil.py` (`fusionar_politicas`; avisos en `validar`)
- Test: `prototipo/tests/test_politicas_editor.py`

**Interfaces:**
- Produces: `fusionar_politicas(perfil, overlay) -> dict` (nuevo dict; no muta; el overlay reemplaza por clave en `automatizacion_por_familia`/`politicas_por_zona`/`overrides_por_activo`). `validar(perfil)` añade avisos.

- [ ] **Step 1: Tests que fallan:**
```python
def test_fusionar_no_muta_y_aplica_overlay():
    out = perfil.fusionar_politicas(base, {"politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}}})
    assert out["politicas_por_zona"]["Core"]["automatizacion"] == "humano_siempre"
    assert "politicas_por_zona" not in base   # no mutó

def test_validar_avisa_postura_invalida():
    p = {**base, "automatizacion_por_familia": {"reconocimiento": {"automatizacion": "siempre_si"}}}
    assert any("automatizacion" in a for a in perfil.validar(p))
```
- [ ] **Step 2: Ver fallar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politicas_editor -v`.
- [ ] **Step 3: Implementar** `fusionar_politicas` (copia superficial + merge por dimensión) y, en `validar`, avisar si un valor de `automatizacion` no está en `{automatica_si_confianza, humano_siempre}` o si una `clave` de zona/activo/familia es desconocida.
- [ ] **Step 4: Ver pasar.** Run igual que Step 2 · Expected: PASS.
- [ ] **Step 5: Commit** — `feat(motor): fusionar_politicas (overlay) + validación de posturas`.

---

### Task 4: Almacén de la copia operativa y auditoría

**Files:**
- Create: `prototipo/servicio/politica_store.py`
- Test: `prototipo/tests/test_politica_store.py` (nuevo)

**Interfaces:**
- Produces: `cargar_overlay(ruta) -> dict` ({} si no existe); `aplicar_cambio(overlay, dimension, clave, valor) -> dict` (puro; `valor=None` borra la clave); `guardar_overlay(ruta, overlay)` (escritura atómica tmp+rename); `registrar_auditoria(ruta_log, operador, dimension, clave, antes, despues)` (añade una línea JSONL con `timestamp` UTC ISO).

- [ ] **Step 1: Tests que fallan** en `test_politica_store.py`:
```python
def test_aplicar_cambio_add_y_borra():
    ov = politica_store.aplicar_cambio({}, "politicas_por_zona", "Core", "humano_siempre")
    assert ov["politicas_por_zona"]["Core"]["automatizacion"] == "humano_siempre"
    ov2 = politica_store.aplicar_cambio(ov, "politicas_por_zona", "Core", None)
    assert "Core" not in ov2.get("politicas_por_zona", {})

def test_guardar_y_cargar_roundtrip(tmp_path): ...   # guardar luego cargar devuelve el mismo overlay
def test_auditoria_append_parseable(tmp_path): ...    # registrar_auditoria añade una línea JSON con operador/dimension/clave/antes/despues/timestamp
```
- [ ] **Step 2: Ver fallar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politica_store -v`.
- [ ] **Step 3: Implementar** el módulo (solo stdlib + PyYAML; escritura atómica con `os.replace`).
- [ ] **Step 4: Ver pasar.** Run igual · Expected: PASS.
- [ ] **Step 5: Commit** — `feat(servicio): politica_store (overlay operativo + auditoría append-only)`.

---

### Task 5: `GET /api/politica` reestructurado a objeto

**Files:**
- Modify: `prototipo/servicio/tablero.py` (`politica_estado(catalogo, perfil)` + rama GET)
- Test: `prototipo/tests/test_tablero.py`

**Interfaces:**
- Produces: `politica_estado(catalogo, perfil) -> {"familias": [...], "zonas": [...]}`. Cada familia: los campos actuales de `politica_resumen` + `postura_familia` + `automatizacion_efectiva`. Cada zona: `{zona, automatizacion, protegida, dispositivos: [{activo, criticidad, override, postura_efectiva, cascada, radio, cascada_posiblemente_incompleta}]}`. `cascada` reusa `impacto.afectados_en_cascada`; `cascada_posiblemente_incompleta = (sin depende_de y sin dependientes)`.

- [ ] **Step 1: Tests que fallan** en `test_tablero.py`:
```python
def test_get_politica_devuelve_objeto_con_familias_y_zonas(): ...   # GET /api/politica -> dict con 'familias' y 'zonas'
def test_zona_core_humano_marca_postura_efectiva(): ...             # con politicas_por_zona Core humano, middleware.postura_efectiva == 'humano_siempre'
def test_cascada_hsm_lista_cuatro(): ...                            # hsm.radio == 4
def test_atm_cascada_posiblemente_incompleta(): ...                 # atm.cascada_posiblemente_incompleta is True
```
- [ ] **Step 2: Ver fallar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`.
- [ ] **Step 3: Implementar** `politica_estado` (reusa el cuerpo de `politica_resumen` para `familias`) y cambiar la rama `GET /api/politica` para devolver el objeto. Nota: cambia el contrato (de array a objeto) — Task 8 ajusta el cliente.
- [ ] **Step 4: Ver pasar.** Run igual · Expected: PASS.
- [ ] **Step 5: Commit** — `feat(tablero): GET /api/politica como objeto (familias + zonas con cascada)`.

---

### Task 6: `POST /api/politica` (fail-closed + validación + aplicar + auditoría)

**Files:**
- Modify: `prototipo/servicio/tablero.py` (allow-list POST `:970`; handler **antes** de la caída genérica `:1064-1071`)
- Test: `prototipo/tests/test_tablero.py`

**Interfaces:**
- Consumes: `fusionar_politicas`/`validar` (Task 1/3), `politica_store` (Task 4), el `actualizador` de política inyectado por `crear_servidor` (Task 7).
- Produces: `POST /api/politica` body `{dimension: "familia"|"zona"|"activo", clave: str, automatizacion: "automatica_si_confianza"|"humano_siempre"|null}`.

- [ ] **Step 1: Tests que fallan** en `test_tablero.py`:
```python
def test_post_sin_operador_es_403(): ...        # sin mapa operadores ni opt-in -> 403, no aplica
def test_post_familia_destructiva_auto_400(): ... # dimension=familia, clave=malware, auto -> 400
def test_post_clave_desconocida_400(): ...       # clave inexistente -> 400
def test_post_aplica_y_get_lo_refleja(): ...      # con operador válido: 200; GET posterior muestra la efectiva ya cambiada (en vivo)
def test_post_overlay_invalido_no_aplica(): ...   # si validar falla tras fusionar -> 400 y el perfil vivo no cambia
```
- [ ] **Step 2: Ver fallar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`.
- [ ] **Step 3: Implementar.** Añadir `/api/politica` a la allow-list POST y su `if` antes de la caída genérica. Fail-closed: exigir `resolver_operador` con mapa `operadores` configurado (si no, 403; opt-in de laboratorio `TRIAJE_POLITICA_ABIERTA=1`). Validar dimensión/clave; **rechazar** `automatica_si_confianza` si la acción de esa familia es `nunca_automatica`. Luego delegar en el `actualizador` inyectado (Task 7), que fusiona → `validar` (400 si inválido) → swap en vivo → `guardar_overlay` → `registrar_auditoria`.
- [ ] **Step 4: Ver pasar.** Run igual · Expected: PASS.
- [ ] **Step 5: Commit** — `feat(tablero): POST /api/politica fail-closed con validación y auditoría`.

---

### Task 7: Arranque del daemon — overlay + swap en vivo

**Files:**
- Modify: `prototipo/servicio/stream.py` (`main`, ~`:1083`,`:1161`)
- Test: `prototipo/tests/test_politicas_editor.py`

**Interfaces:**
- Consumes: `cargar_overlay`/`guardar_overlay`/`registrar_auditoria` (Task 4), `fusionar_politicas`/`validar` (Task 1/3).
- Produces: un **contenedor compartido** del perfil que lazo y servidor leen (lectura siempre del último); un `actualizador` que fusiona el cambio, valida, **reemplaza atómicamente** el perfil del contenedor, persiste el overlay y audita. Ruta del overlay y del log: `run/politica-operativa.yml` y `run/politica-auditoria.jsonl` (o `perfiles/<cliente>.operativo.yml`; decisión del implementador).

- [ ] **Step 1: Tests que fallan:**
```python
def test_arranque_fusiona_overlay(tmp_path): ...       # con un overlay en disco, el perfil que ve el servidor trae la clave; con cargar() directo NO
def test_evaluacion_no_ve_overlay(tmp_path): ...        # perfilm.cargar(canonico) NO contiene las claves del overlay aunque el fichero exista
```
- [ ] **Step 2: Ver fallar.** Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politicas_editor -v`.
- [ ] **Step 3: Implementar.** En `stream.main`, tras `perfilm.cargar`, leer el overlay (si existe) y `fusionar_politicas`. Introducir el contenedor compartido y pasarlo a `crear_servidor` y al lazo (lecturas siempre del contenedor). Cablear el `actualizador` que usa Task 6. **No** tocar `perfilm.cargar` (así `triaje_lote`/evaluación no ven el overlay).
- [ ] **Step 4: Ver pasar** + suite motor completa verde. Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -p "test_*.py"`.
- [ ] **Step 5: Humo (manual).** Levantar el daemon `--web`, cambiar una postura con token, ver la efectiva al instante, reiniciar y confirmar persistencia + auditoría; confirmar que `bancario.yml` no cambió.
- [ ] **Step 6: Commit** — `feat(stream): carga de overlay operativo + swap en vivo del perfil`.

---

### Task 8: Cliente — schema objeto + `actualizarPolitica`

**Files:**
- Modify: `visor/src/api.ts`
- Test: `visor/src/api.test.ts` (o el que cubra schemas)

**Interfaces:**
- Produces: `PoliticaEstado` (Zod: `{familias: PoliticaFamilia[], zonas: ZonaPolitica[]}`, cada campo declarado — el schema no tiene `.passthrough()`); `getPolitica(): Promise<PoliticaEstado>`; `actualizarPolitica({dimension, clave, automatizacion}, token): Promise<void>` (POST con cabecera de token).

- [ ] **Step 1: Tests que fallan:** `parse` de un objeto `{familias, zonas}` válido; `actualizarPolitica` hace `POST` a `/api/politica` con el cuerpo correcto.
- [ ] **Step 2: Ver fallar.** Run: `cd visor && npx vitest run src/api.test.ts`.
- [ ] **Step 3: Implementar** los schemas y funciones.
- [ ] **Step 4: Ver pasar** + typecheck. Run: `cd visor && npm run typecheck && npx vitest run src/api.test.ts`.
- [ ] **Step 5: Commit** — `feat(visor): api de políticas (estado objeto + actualizarPolitica)`.

---

### Task 9: Cliente — vista «Políticas» editable

**Files:**
- Modify: `visor/src/components/Politicas.tsx`
- Test: `visor/src/components/Politicas.test.tsx`

**Interfaces:**
- Consumes: `getPolitica`/`actualizarPolitica` (Task 8); `useSondeo`, `bits.tsx`, `ClaseBadge`/`etiquetaClase`.

- [ ] **Step 1: Tests que fallan** (mock de `getPolitica`/`actualizarPolitica`): pestaña «Por tipo de ataque» con toggles AUTO/HUMANO; pestaña «Por zona y dispositivo» con postura por zona y override por dispositivo; **acción destructiva con el toggle bloqueado**; **nota de interferencia** presente en cada pestaña; al cambiar un toggle se llama a `actualizarPolitica`.
- [ ] **Step 2: Ver fallar.** Run: `cd visor && npx vitest run src/components/Politicas.test.tsx`.
- [ ] **Step 3: Implementar** la vista editable (dos pestañas + nota; segmentos AUTO/HUMANO; destructivas bloqueadas con razón; panel de detalle con acción, dónde se ejecuta, reversibilidad, cascada y, en joyas, escalada al borde). Reusar lo existente; navegación por el `useState<Vista>` actual.
- [ ] **Step 4: Ver pasar** + gate completo. Run: `cd visor && npm run typecheck && npx vitest run && npm run build`.
- [ ] **Step 5: Commit** — `feat(visor): vista Políticas editable (familia + zona/dispositivo + nota)`.

---

## Verificación final (antes de dar por hecho)

- `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -p "test_*.py"` verde; **conteos canónicos sin regresión**.
- `cd visor && npm run typecheck && npx vitest run && npm run build` verde.
- Humo de Task 7 reproducido. `evaluacion/` sin cambios de cifras.
- `code-review` sobre el diff de la rama antes de integrar a `main` (merge `--no-ff`, sin push).
