# Runner en streaming (daemon / listener MDR) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un runner ligero en streaming (`prototipo/stream.py`, invocable como `python3 -m prototipo.stream`) que se queda escuchando alertas entrantes de Wazuh sin cerrarse, y las pasa por el pipeline existente (ingesta → agrupación → triaje → explicabilidad → validación humana → mitigación → traza) en tiempo real.

**Architecture:** El runner es una **capa de orquestación de streaming**, no lógica nueva. Tiene tres piezas separables y testeables: (1) una **fuente de líneas inyectable** — seguir un fichero del host estilo `tail -f`, o `stdin` — que rinde líneas crudas y *ticks* de reposo; (2) un **bucle** que parsea, **acumula por ventana** y agrupa con `agrupacion.agrupar` (RF-11), y procesa el **representante** de cada incidente con `lazo.procesar_lazo` (que ya encadena triaje → validación → conector → verificación → traza); (3) una **CLI/UX de demo** con banner, estado en reposo, resumen de incidente, prompt interactivo y cierre limpio en `SIGINT`. El único cambio a código existente es **añadir el parámetro `justificar_fn` a `lazo.procesar_lazo`** para poder inyectar el justificador LLM/RAG en el lazo en vivo.

**Tech Stack:** Python 3 (probado en 3.14) **solo stdlib** (`json`, `os`, `sys`, `time`, `signal`, `unittest`) + PyYAML (ya usado por `perfil`/`catalogo`). Sin `pip`, `venv` ni `pytest`. Tests con `python3 -m unittest`.

**Spec:** Mensaje del usuario (2026-09-07) que pide el runner en streaming: modo *follow* tolerante a que el fichero no exista aún; reutilizar estrictamente `ingesta`, `agrupacion` (RF-11), `triaje`/`perfil`, `justificar_fn_rag`/justificador base, `validacion` (TUI), conector SSH o subprocess, y `traza` línea a línea; UX de demo (banner, reposo, resumen de ráfaga, prompt [Aprobar/Rechazar/Reclasificar], vuelta al stream); `SIGINT` limpio con resumen; CLI `python3 -m prototipo.stream <ruta_alerts.json> [perfil.yml] [hallazgos.json] [--con-llm | --sin-llm] [--ventana-agrupacion N]`; TDD estricto en `prototipo/tests/test_stream.py` mockeando el generador de líneas; cero regresión en las tres suites.

## Global Constraints

- **Solo biblioteca estándar de Python + PyYAML.** Nada de `pip`/`venv`/`pytest`. Tests: `python3 -m unittest`.
- **No duplicar lógica.** Reutilizar `ingesta.normalizar`, `adaptador_wazuh.adaptador`, `agrupacion.agrupar`/`representante`, `lazo.procesar_lazo`, `triaje.procesar`, `validacion.pedir`, `conector.ejecutor_ssh_lab`, `traza.construir` (vía las anteriores), `justificador_llm.justificar_fn_rag`, `rag.*`, `catalogo.cargar_catalogo`, `perfil.cargar`.
- **Todo local (RNF-01):** ninguna alerta sale a servicios externos; el LLM corre por subprocess a un binario local.
- **RNF-07 (no inventar lo ausente):** parseo tolerante — líneas vacías/corruptas se saltan sin romper el stream; campos ausentes no se rellenan.
- **Cero regresión:** `python3 -m unittest discover -s prototipo/tests` (116+), `-s lab/dataset/tests` (33), `-s evaluacion/tests` (22) deben seguir en verde.
- **Ejecución dentro de la ventana de agrupación es serial y bloqueante** (un incidente a la vez, incluida la validación humana): es un prototipo de un solo hilo; se declara, no se oculta.
- **Atribución de commits:** terminar los mensajes con `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

- **Create `prototipo/stream.py`** — el runner. Responsabilidades: fuentes de líneas (`leer_lineas_fichero`, `leer_lineas_stdin`), bucle (`ejecutar`), selección de justificador (`construir_justificar_fn`), UX (`banner`, `_resumen_incidente`, `_linea_decision`, `_resumen_final`) y CLI (`main`). Sin lógica de decisión propia.
- **Create `prototipo/tests/test_stream.py`** — TDD del bucle con fuente mockeada (lista de líneas / ticks), `leer`/`escribir` inyectados, ejecutor falso, `justificar_fn` falso, fichero de traza temporal, reloj (`reloj`) y `dormir` inyectados.
- **Modify `prototipo/lazo.py`** — `procesar_lazo` gana el parámetro `justificar_fn` y lo reenvía a `triaje.procesar` (habilita LLM/RAG en el lazo en vivo). Cambio mínimo, retrocompatible.
- **Modify `prototipo/tests/test_lazo.py`** — un test que fija que `justificar_fn` inyectado se propaga a la traza (`version_justificador`).
- **Modify `COMO-PROBAR.md`** — nueva sección "Modo tiempo real (daemon)" con los dos modos de fuente (host file / stdin desde el lab).
- **Modify `prototipo/README.md`** — una nota del runner en la sección del motor.
- **Modify `documentacion/02-fase2-estado-del-arte/requisitos.md`** — nota en RF-13 / operación en vivo apuntando al runner.

---

## Task 1: `lazo.procesar_lazo` acepta `justificar_fn` inyectable

Habilita que el lazo en vivo justifique con LLM/RAG (hoy usa siempre la plantilla). Es el prerequisito para que el runner registre el justificador real en la traza.

**Files:**
- Modify: `prototipo/lazo.py:1-24`
- Test: `prototipo/tests/test_lazo.py`

**Interfaces:**
- Consumes: `triaje.procesar(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp, justificar_fn=...)` (ya soporta `justificar_fn`).
- Produces: `lazo.procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp, leer=input, justificar_fn=analisis.justificar) -> dict` (decisión + `veredicto_humano`, `clase_reclasificada`, `orden`, `ejecucion`, `verificacion`).

- [ ] **Step 1: Write the failing test**

En `prototipo/tests/test_lazo.py`, añade:

```python
def test_procesar_lazo_propaga_justificar_fn_a_la_traza(self):
    def just_dict(a, c, cl):
        return {"texto": "TEXTO-LLM", "version_justificador": "llm-1b-0:m.gguf", "pasajes_usados": ["p1"]}
    r = lazo.procesar_lazo(
        j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
        ejecutor=lazo._EjecutorAuto(), id_decision="d1", timestamp="t",
        leer=lambda *_: "rechazar", justificar_fn=just_dict)
    self.assertEqual(r["justificacion"], "TEXTO-LLM")
    self.assertEqual(r["version_justificador"], "llm-1b-0:m.gguf")
    self.assertEqual(r["pasajes_usados"], ["p1"])
```

(Reutiliza los helpers `j`, `y`, `CAT` ya presentes en `test_lazo.py`; si el fichero no los tiene, cópialos del patrón de `test_triaje.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_lazo -v`
Expected: FAIL — `procesar_lazo() got an unexpected keyword argument 'justificar_fn'`.

- [ ] **Step 3: Write minimal implementation**

En `prototipo/lazo.py`, añade el import y reenvía el parámetro:

```python
from prototipo import triaje, orden as ordenm, conector, validacion, verificacion, perfil as perfilm, catalogo as catm, analisis
```

```python
def procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp,
                  leer=input, justificar_fn=analisis.justificar):
    decision = triaje.procesar(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp,
                               justificar_fn=justificar_fn)
```

(El resto de `procesar_lazo` no cambia.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_lazo -v`
Expected: PASS (todos, incluido el nuevo).

- [ ] **Step 5: Commit**

```bash
git add prototipo/lazo.py prototipo/tests/test_lazo.py
git commit -m "feat(lazo): justificar_fn inyectable en procesar_lazo para LLM/RAG en vivo"
```

---

## Task 2: núcleo del bucle en modo inmediato (`ventana=0`)

El corazón del runner: consumir líneas crudas, normalizar, y procesar cada alerta como un incidente por `lazo.procesar_lazo`, escribiendo la traza línea a línea y contando el resumen. Sin ventana todavía (cada alerta = un incidente).

**Files:**
- Create: `prototipo/stream.py`
- Test: `prototipo/tests/test_stream.py`

**Interfaces:**
- Consumes: `ingesta.normalizar`, `adaptador_wazuh.adaptador`, `agrupacion.agrupar`, `lazo.procesar_lazo` (Task 1), `traza`-dict que devuelve `procesar_lazo`.
- Produces:
  - `ejecutar(fuente_lineas, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn=None, ventana_agrupacion=0, salida_traza=None, escribir=print, leer=input, reloj=time.monotonic) -> dict` resumen `{"alertas": int, "incidentes": int, "aprobadas": int, "rechazadas": int, "reclasificadas": int, "ejecutadas": int}`. `fuente_lineas` es un **iterable** de `str` (línea cruda JSON) o `None` (tick de reposo). `justificar_fn=None` ⇒ plantilla (default de `procesar_lazo`). `salida_traza` es un *file object* abierto en modo texto (o `None` para no persistir).
  - `_procesar_incidente(inc, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn, id_decision, salida_traza, escribir, leer) -> dict` (la decisión).

- [ ] **Step 1: Write the failing test**

Crea `prototipo/tests/test_stream.py`:

```python
import io, json, os, unittest, yaml
from prototipo import stream, catalogo, lazo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))

def _txt(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return f.read().strip()
def j(n): return json.loads(_txt(n))
def y(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return yaml.safe_load(f)

def _linea_wazuh(srcip="192.168.1.10", rule_id="5760"):
    # una alerta CRUDA de Wazuh (la que el adaptador normaliza), no la ya normalizada
    return json.dumps({
        "id": "a1", "rule": {"id": rule_id, "level": 10, "description": "sshd brute force",
                             "mitre": {"id": ["T1110.001"]}},
        "agent": {"name": "objetivo-vuln", "ip": "192.168.1.30"},
        "data": {"srcip": srcip}, "timestamp": "2026-08-31T00:00:00Z",
        "full_log": "Failed password for msfadmin from %s" % srcip})

class TestBucleInmediato(unittest.TestCase):
    def test_una_alerta_produce_un_incidente_y_traza(self):
        buf = io.StringIO()
        salidas = []
        resumen = stream.ejecutar(
            [_linea_wazuh(), "", "no-es-json", None],
            hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"), perfil_nombre="prueba",
            catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None,
            ventana_agrupacion=0, salida_traza=buf,
            escribir=lambda *a, **k: salidas.append(" ".join(str(x) for x in a)), leer=lambda *_: "rechazar")
        self.assertEqual(resumen["alertas"], 1)      # la vacía y la corrupta se saltan (RNF-07)
        self.assertEqual(resumen["incidentes"], 1)
        lineas = [l for l in buf.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(lineas), 1)
        traza = json.loads(lineas[0])
        self.assertEqual(traza["clase"], "vp_intento_acceso")
        self.assertIn("192.168.1.10", traza["justificacion"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_stream -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prototipo.stream'`.

- [ ] **Step 3: Write minimal implementation**

Crea `prototipo/stream.py`:

```python
"""Runner en streaming (daemon / listener MDR): escucha alertas de Wazuh sin cerrarse y las pasa
por el pipeline existente (ingesta -> agrupacion -> triaje -> explicabilidad -> validacion ->
mitigacion -> traza) en tiempo real. Capa de orquestacion: no reimplementa logica del motor.
"""
import json, os, sys, time
from prototipo import ingesta, adaptador_wazuh, agrupacion, lazo

_ADAPTADOR = adaptador_wazuh.adaptador("tiempo-real")

def _parsear(linea):
    """Linea cruda JSON -> alerta normalizada, o None si vacia/corrupta (RNF-07)."""
    linea = (linea or "").strip()
    if not linea:
        return None
    try:
        cruda = json.loads(linea)
    except json.JSONDecodeError:
        return None
    return ingesta.normalizar(cruda, _ADAPTADOR)

def _resumen_incidente(inc):
    c = inc["clave"]
    reglas = ", ".join(f"{k}x{v}" for k, v in inc["reglas"].items())
    return (f"⚠ Incidente: {inc['conteo']} alerta(s) · {c['origen_ip']} -> {c['activo']} "
            f"({c['servicio']}) · reglas [{reglas}]")

def _linea_decision(d):
    return (f"  Clase: {d['clase']} · Prioridad: {d['prioridad']} · Confianza: {d['confianza']} · "
            f"accion {d['accion_propuesta']} -> {d['accion_final']} (filtro {d['resultado_filtro']}) · "
            f"justificador {d.get('version_justificador')}")

def _procesar_incidente(inc, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn,
                        id_decision, salida_traza, escribir, leer):
    rep = inc["representante"]
    escribir(_resumen_incidente(inc))
    kw = {} if justificar_fn is None else {"justificar_fn": justificar_fn}
    d = lazo.procesar_lazo(rep, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                           id_decision, rep.get("timestamp", ""), leer=leer, **kw)
    escribir(_linea_decision(d))
    if salida_traza is not None:
        salida_traza.write(json.dumps(d, ensure_ascii=False) + "\n")
        salida_traza.flush()
    return d

def _contar(resumen, d):
    resumen["incidentes"] += 1
    v = d.get("veredicto_humano")
    if v == "aprobar": resumen["aprobadas"] += 1
    elif v == "reclasificar": resumen["reclasificadas"] += 1
    elif v == "rechazar": resumen["rechazadas"] += 1
    if (d.get("ejecucion") or {}).get("exito"):
        resumen["ejecutadas"] += 1

def ejecutar(fuente_lineas, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
             justificar_fn=None, ventana_agrupacion=0, salida_traza=None,
             escribir=print, leer=input, reloj=time.monotonic):
    resumen = {"alertas": 0, "incidentes": 0, "aprobadas": 0, "rechazadas": 0,
               "reclasificadas": 0, "ejecutadas": 0}
    seq = [0]
    def _procesa_lote(lote):
        for inc in agrupacion.agrupar(lote, ventana_seg=max(ventana_agrupacion, 1)):
            seq[0] += 1
            _contar(resumen, _procesar_incidente(
                inc, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn,
                f"s{seq[0]}", salida_traza, escribir, leer))
    for linea in fuente_lineas:
        if linea is None:                      # tick de reposo (sin ventana no hace nada aun)
            continue
        alerta = _parsear(linea)
        if alerta is None:
            continue
        resumen["alertas"] += 1
        _procesa_lote([alerta])                # modo inmediato: cada alerta = un lote
    return resumen
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_stream -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/stream.py prototipo/tests/test_stream.py
git commit -m "feat(stream): nucleo del bucle en streaming (modo inmediato) sobre lazo.procesar_lazo"
```

---

## Task 3: acumulación por ventana (RF-11 en streaming)

Acumular alertas durante `ventana_agrupacion` segundos (reloj de pared) y agruparlas con `agrupacion.agrupar` antes de emitir los incidentes, para colapsar ráfagas. Los *ticks* de reposo (`None`) permiten vencer la ventana aunque no lleguen más líneas.

**Files:**
- Modify: `prototipo/stream.py` (la función `ejecutar`)
- Test: `prototipo/tests/test_stream.py`

**Interfaces:**
- Consumes: `reloj()` inyectable (monotónico), `agrupacion.agrupar(lote, ventana_seg)`.
- Produces: misma firma de `ejecutar`; con `ventana_agrupacion > 0` acumula y descarga por ventana o al agotarse la fuente.

- [ ] **Step 1: Write the failing test**

Añade a `prototipo/tests/test_stream.py`:

```python
class TestVentana(unittest.TestCase):
    def test_rafaga_se_colapsa_en_un_incidente(self):
        # 3 alertas de la misma clave llegan "dentro" de la ventana; luego un tick vence la ventana.
        reloj = iter([0, 0, 1, 2, 100, 100, 100]).__next__   # el 5º valor (100) vence ventana=10
        fuente = [_linea_wazuh(), _linea_wazuh(), _linea_wazuh(), None]
        buf = io.StringIO()
        resumen = stream.ejecutar(
            fuente, hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"), perfil_nombre="prueba",
            catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None,
            ventana_agrupacion=10, salida_traza=buf,
            escribir=lambda *a, **k: None, leer=lambda *_: "rechazar", reloj=reloj)
        self.assertEqual(resumen["alertas"], 3)
        self.assertEqual(resumen["incidentes"], 1)          # las 3 -> un incidente (misma clave)
        self.assertEqual(len([l for l in buf.getvalue().splitlines() if l.strip()]), 1)

    def test_fuente_agotada_descarga_lo_pendiente(self):
        reloj = iter([0, 0, 0]).__next__
        resumen = stream.ejecutar(
            [_linea_wazuh(), _linea_wazuh()], hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
            perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(),
            ventana_agrupacion=10, salida_traza=None,
            escribir=lambda *a, **k: None, leer=lambda *_: "rechazar", reloj=reloj)
        self.assertEqual(resumen["incidentes"], 1)          # se descarga al agotar la fuente
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_stream.TestVentana -v`
Expected: FAIL — con ventana>0 el modo inmediato de Task 2 da 3 incidentes (o no descarga), no 1.

- [ ] **Step 3: Write minimal implementation**

Reemplaza el cuerpo del bucle de `ejecutar` (de `for linea in fuente_lineas:` al `return`) por la versión con buffer:

```python
    buffer, t0 = [], None
    def _vencio():
        return t0 is not None and (reloj() - t0) >= ventana_agrupacion
    def _descargar():
        nonlocal buffer, t0
        if buffer:
            _procesa_lote(buffer)
            buffer, t0 = [], None
    for linea in fuente_lineas:
        if ventana_agrupacion <= 0:
            if linea is None:
                continue
            alerta = _parsear(linea)
            if alerta is None:
                continue
            resumen["alertas"] += 1
            _procesa_lote([alerta])
            continue
        # modo con ventana
        if linea is not None:
            alerta = _parsear(linea)
            if alerta is not None:
                resumen["alertas"] += 1
                if t0 is None:
                    t0 = reloj()
                buffer.append(alerta)
        if _vencio():
            _descargar()
    _descargar()                               # fuente agotada: descarga lo pendiente
    return resumen
```

(Elimina el `for linea in fuente_lineas:` … `_procesa_lote([alerta])` del modo inmediato anterior — queda subsumido en la rama `ventana_agrupacion <= 0`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_stream -v`
Expected: PASS (Task 2 y Task 3).

- [ ] **Step 5: Commit**

```bash
git add prototipo/stream.py prototipo/tests/test_stream.py
git commit -m "feat(stream): acumulacion por ventana (RF-11) con reloj inyectable"
```

---

## Task 4: fuentes de líneas reales (follow de fichero + stdin)

La fuente real: seguir un fichero del host estilo `tail -f` (tolerando que no exista aún, y rotación/truncado), y leer de `stdin`. Ambas rinden `None` en reposo para que la ventana pueda vencer.

**Files:**
- Modify: `prototipo/stream.py`
- Test: `prototipo/tests/test_stream.py`

**Interfaces:**
- Produces:
  - `leer_lineas_fichero(ruta, intervalo=0.5, desde_inicio=False, detener=None, dormir=time.sleep)` — generador de `str`/`None`. Tolera que `ruta` no exista (rinde `None` y espera). `desde_inicio=False` arranca al final (solo lo nuevo, semántica `tail -f`). `detener()` → `True` termina.
  - `leer_lineas_stdin(stream=sys.stdin)` — generador que rinde cada línea de `stdin`.

- [ ] **Step 1: Write the failing test**

Añade a `prototipo/tests/test_stream.py`:

```python
import tempfile

class TestFuentes(unittest.TestCase):
    def test_fichero_inexistente_rinde_tick_y_no_rompe(self):
        gen = stream.leer_lineas_fichero("/no/existe/aqui.json", intervalo=0,
                                         detener=iter([False, True]).__next__, dormir=lambda s: None)
        self.assertIsNone(next(gen))           # primer yield: tick de reposo, sin excepcion

    def test_fichero_desde_inicio_lee_lineas_existentes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write('{"a":1}\n{"a":2}\n'); ruta = f.name
        try:
            stop = iter([False, False, False, True]).__next__
            got = list(stream.leer_lineas_fichero(ruta, intervalo=0, desde_inicio=True,
                                                  detener=stop, dormir=lambda s: None))
        finally:
            os.unlink(ruta)
        self.assertEqual([g for g in got if g is not None][:2], ['{"a":1}\n', '{"a":2}\n'])

    def test_stdin_rinde_cada_linea(self):
        got = list(stream.leer_lineas_stdin(io.StringIO("l1\nl2\n")))
        self.assertEqual(got, ["l1\n", "l2\n"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_stream.TestFuentes -v`
Expected: FAIL — `module 'prototipo.stream' has no attribute 'leer_lineas_fichero'`.

- [ ] **Step 3: Write minimal implementation**

Añade a `prototipo/stream.py`:

```python
def leer_lineas_stdin(stream=sys.stdin):
    for linea in stream:
        yield linea

def leer_lineas_fichero(ruta, intervalo=0.5, desde_inicio=False, detener=None, dormir=time.sleep):
    """Sigue un fichero como `tail -f`. Tolera que no exista aun (espera activa). Reabre en
    rotacion/truncado. Rinde None en reposo para que la ventana pueda vencer sin lineas nuevas."""
    f, pos = None, 0
    try:
        while detener is None or not detener():
            if f is None:
                if not os.path.exists(ruta):
                    yield None
                    dormir(intervalo)
                    continue
                f = open(ruta, encoding="utf-8", errors="replace")
                if not desde_inicio:
                    f.seek(0, os.SEEK_END)      # tail -f: solo lo nuevo
                pos = f.tell()
            try:
                if os.path.getsize(ruta) < pos:   # truncado/rotacion -> reabrir desde 0
                    f.close(); f, pos = None, 0
                    continue
            except OSError:
                f.close(); f = None
                continue
            linea = f.readline()
            if linea:
                pos = f.tell()
                yield linea
            else:
                yield None
                dormir(intervalo)
    finally:
        if f is not None:
            f.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_stream -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/stream.py prototipo/tests/test_stream.py
git commit -m "feat(stream): fuentes reales de lineas (follow de fichero tolerante + stdin)"
```

---

## Task 5: CLI, banner/UX, selección de justificador y cierre en SIGINT

Ata todo: parseo de argumentos, elección de fuente (fichero/`-`), perfil/hallazgos/catálogo, justificador (`--con-llm`/`--sin-llm`), ejecutor (SSH del lab o simulado), banner, y resumen final en `Ctrl+C`.

**Files:**
- Modify: `prototipo/stream.py`
- Test: `prototipo/tests/test_stream.py`

**Interfaces:**
- Produces:
  - `parsear_args(argv) -> dict` con `{"ruta", "perfil", "hallazgos", "con_llm", "ventana", "salida", "sin_lab"}`.
  - `construir_justificar_fn(con_llm, escribir=print)` → callable para `procesar_lazo` o `None` (plantilla). Con RAG si índice+modelo están disponibles; si no, avisa y degrada a `None`.
  - `banner(cfg) -> str`.
  - `_resumen_final(resumen) -> str`.
  - `main(argv) -> int` — arranca el runner; captura `KeyboardInterrupt` e imprime el resumen.

- [ ] **Step 1: Write the failing test**

Añade a `prototipo/tests/test_stream.py`:

```python
class TestCLI(unittest.TestCase):
    def test_parsear_args_defaults_y_flags(self):
        cfg = stream.parsear_args(["alerts.json"])
        self.assertEqual(cfg["ruta"], "alerts.json")
        self.assertFalse(cfg["con_llm"])
        self.assertEqual(cfg["ventana"], 5)
        cfg2 = stream.parsear_args(["-", "prototipo/perfiles/residencial.yml", "--con-llm",
                                    "--ventana-agrupacion", "20", "--sin-lab"])
        self.assertEqual(cfg2["ruta"], "-")
        self.assertTrue(cfg2["con_llm"])
        self.assertTrue(cfg2["sin_lab"])
        self.assertEqual(cfg2["ventana"], 20)
        self.assertTrue(cfg2["perfil"].endswith("residencial.yml"))

    def test_sin_llm_no_construye_justificador(self):
        self.assertIsNone(stream.construir_justificar_fn(False))

    def test_banner_menciona_perfil_y_ruta(self):
        b = stream.banner({"perfil": "empresarial.yml", "ruta": "alerts.json", "con_llm": False,
                           "ventana": 5, "sin_lab": True})
        self.assertIn("empresarial", b)
        self.assertIn("alerts.json", b)
        self.assertIn("MDR", b)

    def test_resumen_final_cuenta(self):
        s = stream._resumen_final({"alertas": 4, "incidentes": 2, "aprobadas": 1, "rechazadas": 1,
                                   "reclasificadas": 0, "ejecutadas": 1})
        self.assertIn("2", s); self.assertIn("incidentes", s)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_stream.TestCLI -v`
Expected: FAIL — `parsear_args`/`construir_justificar_fn`/`banner`/`_resumen_final` no existen.

- [ ] **Step 3: Write minimal implementation**

Añade a `prototipo/stream.py`:

```python
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PERFIL_DEF = os.path.join(_RAIZ, "prototipo", "perfiles", "empresarial.yml")
_HALLAZGOS_DEF = os.path.join(_RAIZ, "lab", "campañas", "2026-08-31-evaluacion", "hallazgos.json")

def parsear_args(argv):
    pos, con_llm, ventana, salida, sin_lab = [], False, 5, "trazas-stream.jsonl", False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--con-llm": con_llm = True
        elif a == "--sin-llm": con_llm = False
        elif a == "--sin-lab": sin_lab = True
        elif a == "--ventana-agrupacion": i += 1; ventana = int(argv[i])
        elif a == "--salida": i += 1; salida = argv[i]
        else: pos.append(a)
        i += 1
    return {"ruta": pos[0] if pos else "-",
            "perfil": pos[1] if len(pos) > 1 else _PERFIL_DEF,
            "hallazgos": pos[2] if len(pos) > 2 else _HALLAZGOS_DEF,
            "con_llm": con_llm, "ventana": ventana, "salida": salida, "sin_lab": sin_lab}

def construir_justificar_fn(con_llm, escribir=print):
    if not con_llm:
        return None
    try:
        from prototipo import justificador_llm, rag
        indice = rag.cargar_indice()
        recuperar_fn = lambda a: rag.recuperar(rag.construir_consulta(a), indice, rag.embedder_llama, k=3)
        return justificador_llm.justificar_fn_rag(justificador_llm.generador_llama, recuperar_fn)
    except Exception as e:                      # sin indice/modelo -> degradar a plantilla (RNF-09)
        escribir(f"[aviso] justificador LLM/RAG no disponible ({e}); se usara la plantilla.")
        return None

def banner(cfg):
    fuente = "stdin (canalizado)" if cfg["ruta"] == "-" else cfg["ruta"]
    just = "LLM+RAG" if cfg["con_llm"] else "plantilla"
    lab = "simulado (--sin-lab)" if cfg["sin_lab"] else "conector SSH (lab)"
    return ("\n" + "=" * 72 +
            "\n  Monitor MDR en tiempo real — ACTIVO"
            f"\n  Perfil: {os.path.basename(cfg['perfil'])} · Justificador: {just} · Ejecutor: {lab}"
            f"\n  Escuchando: {fuente} · ventana de agrupacion: {cfg['ventana']}s"
            "\n  (Ctrl+C para detener)\n" + "=" * 72)

def _resumen_final(r):
    return ("\n── Resumen de la sesion ──\n"
            f"  Alertas vistas: {r['alertas']} · Incidentes: {r['incidentes']}\n"
            f"  Aprobadas: {r['aprobadas']} · Rechazadas: {r['rechazadas']} · "
            f"Reclasificadas: {r['reclasificadas']} · Ejecutadas: {r['ejecutadas']}")

def main(argv):
    from prototipo import perfil as perfilm, catalogo as catm, conector
    cfg = parsear_args(argv)
    perfil = perfilm.cargar(cfg["perfil"])
    perfil_nombre = os.path.basename(cfg["perfil"]).replace(".yml", "")
    with open(cfg["hallazgos"], encoding="utf-8") as f:
        hallazgos = json.load(f)
    catalogo = catm.cargar_catalogo(os.path.join(_RAIZ, "prototipo", "catalogo.yml"))
    justificar_fn = construir_justificar_fn(cfg["con_llm"])
    ejecutor = lazo._EjecutorAuto() if cfg["sin_lab"] else conector.ejecutor_ssh_lab
    fuente = leer_lineas_stdin() if cfg["ruta"] == "-" else leer_lineas_fichero(cfg["ruta"])
    print(banner(cfg))
    resumen = {"alertas": 0, "incidentes": 0, "aprobadas": 0, "rechazadas": 0,
               "reclasificadas": 0, "ejecutadas": 0}
    try:
        with open(cfg["salida"], "a", encoding="utf-8") as traza_f:
            resumen = ejecutar(fuente, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                               justificar_fn=justificar_fn, ventana_agrupacion=cfg["ventana"],
                               salida_traza=traza_f)
    except KeyboardInterrupt:
        pass
    print(_resumen_final(resumen))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

> Nota: la fuente `leer_lineas_fichero(cfg["ruta"])` corre sin `detener` (bucle infinito real); `KeyboardInterrupt` (Ctrl+C / SIGINT por defecto de Python) rompe el `for` en `ejecutar`, se captura en `main`, y se imprime el resumen — cierre limpio sin `signal` explícito.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_stream -v`
Expected: PASS (toda la suite de stream).

- [ ] **Step 5: Commit**

```bash
git add prototipo/stream.py prototipo/tests/test_stream.py
git commit -m "feat(stream): CLI, banner MDR, seleccion de justificador y cierre limpio en SIGINT"
```

---

## Task 6: documentación (cómo probar el modo tiempo real)

Documentar el runner: los dos modos de fuente (fichero del host en producción; `stdin` desde el lab vía `docker exec … tail -F`), los flags, y el cierre limpio. Sin tocar el plan de trabajo ni el roadmap (documentos de coordinación).

**Files:**
- Modify: `COMO-PROBAR.md`
- Modify: `prototipo/README.md`
- Modify: `documentacion/02-fase2-estado-del-arte/requisitos.md`

- [ ] **Step 1: `COMO-PROBAR.md` — nueva sección "Modo tiempo real (daemon)"**

Inserta tras el Nivel 3 una sección que explique:

```markdown
## Nivel 3.bis · Modo tiempo real continuo (daemon / listener MDR)

A diferencia de las demos de un solo tiro, el runner se **queda escuchando** alertas sin cerrarse
(como en producción). CLI:

    python3 -m prototipo.stream <ruta_alerts.json> [perfil.yml] [hallazgos.json] \
        [--con-llm | --sin-llm] [--ventana-agrupacion N] [--sin-lab] [--salida trazas.jsonl]

**En producción** (Wazuh escribe a un fichero del host, montado): apúntalo al fichero y lo sigue
estilo `tail -f`, tolerando que aún no exista:

    python3 -m prototipo.stream /var/ossec/logs/alerts/alerts.json prototipo/perfiles/empresarial.yml

**En el laboratorio** (el `alerts.json` vive dentro del contenedor de Wazuh): canaliza el `tail -F`
del contenedor a la entrada estándar del runner (fuente `-`):

    docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
        | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --con-llm --ventana-agrupacion 10

Lanza en otra terminal la fuerza bruta (o `python3 lab/scripts/demo-lazo-vivo.py`'s `preparar_ataque`)
y observa cómo el runner colapsa la ráfaga en un incidente, lo clasifica, lo justifica (con RAG si
`--con-llm`), abre el prompt **[Aprobar/Rechazar/Reclasificar]**, ejecuta el bloqueo por SSH al aprobar,
y vuelve a escuchar. `Ctrl+C` cierra e imprime el resumen de incidentes. La traza se escribe línea a
línea en `--salida` (por defecto `trazas-stream.jsonl`). Con `--sin-lab` usa un ejecutor simulado (sin
Containerlab), útil para ensayar la UX.
```

- [ ] **Step 2: `prototipo/README.md` — nota del runner**

En la sección del motor, añade una línea: `prototipo/stream.py` es el runner en streaming (daemon MDR) que reutiliza el lazo (`lazo.procesar_lazo`) sobre una fuente de alertas en vivo; ver `COMO-PROBAR.md` (Nivel 3.bis).

- [ ] **Step 3: `documentacion/02-fase2-estado-del-arte/requisitos.md` — nota de operación en vivo**

En la fila de RF-13 (o donde esté la nota de operación/entrega de la traza), añade: la operación en vivo continua está cubierta por `prototipo/stream.py` (listener que sigue el `alerts.json` de Wazuh y procesa incidentes en tiempo real); el *push* al sistema del cliente sigue siendo trabajo de producción.

- [ ] **Step 4: Commit**

```bash
git add COMO-PROBAR.md prototipo/README.md documentacion/02-fase2-estado-del-arte/requisitos.md
git commit -m "docs(stream): documentar el modo tiempo real (daemon MDR) y sus dos fuentes"
```

---

## Verificación (de punta a punta)

1. **Baterías completas** (cero regresión):
   ```bash
   python3 -m unittest discover -s prototipo/tests
   python3 -m unittest discover -s lab/dataset/tests
   python3 -m unittest discover -s evaluacion/tests
   ```
   Verde en las tres, con los tests nuevos de `test_stream` y `test_lazo`.
2. **Humo sin lab** (fuente por stdin, plantilla, ventana 0):
   ```bash
   printf '%s\n' '<una alerta cruda de Wazuh en JSON>' \
     | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
   ```
   Espera: banner MDR, un incidente clasificado, prompt de validación (responde `rechazar`), resumen final, y una línea en `trazas-stream.jsonl`.
3. **En vivo (opcional, con lab + modelo):**
   ```bash
   sh lab/lab.sh up
   docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -F /var/ossec/logs/alerts/alerts.json' \
     | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --con-llm --ventana-agrupacion 10
   # en otra terminal: lanzar la fuerza bruta (ver demo-lazo-vivo.py)
   ```
   Espera: al llegar la ráfaga, el runner emite el incidente, justifica con RAG, pide validación, bloquea por SSH al aprobar, y sigue escuchando. `Ctrl+C` → resumen limpio.

---

## Self-Review (hecho)

- **Cobertura de la spec:** Follow tolerante a inexistencia → Task 4 (`leer_lineas_fichero`, test de fichero inexistente). Lectura línea a línea conforme escribe Wazuh → Task 4 (semántica `tail -f` + `desde_inicio`). Reutilización estricta de `ingesta`/`agrupacion`/`triaje`/`perfil`/`justificar_fn_rag`/`validacion`/conector/`traza` → Tasks 1–2 (vía `lazo.procesar_lazo`) + 5 (`construir_justificar_fn`). UX (banner, resumen de ráfaga, prompt, vuelta al stream) → Tasks 2 y 5. `SIGINT` limpio con resumen → Task 5. CLI con los flags pedidos → Task 5. TDD con generador mockeado → todas las tasks. Solo stdlib+PyYAML y cero regresión → Global Constraints + Verificación.
- **Sin placeholders:** cada step trae el código real.
- **Consistencia de tipos:** `ejecutar(...)` devuelve el dict-resumen en Tasks 2/3/5; `leer_lineas_*` rinden `str`/`None` consumidos por `ejecutar`; `justificar_fn` (dict-returning) fluye Task 5 → Task 1 → `triaje.procesar`. `_EjecutorAuto` se toma de `lazo` (ya existe) en tests y en `--sin-lab`.
- **Desvío consciente de la spec (mencionado al usuario):** la fuente es inyectable con **stdin** además del fichero, porque en el lab el `alerts.json` está dentro del contenedor de Wazuh; y la agrupación en streaming es un **debounce por ventana de pared** sobre `agrupacion.agrupar`, no timers por-clave.
```
