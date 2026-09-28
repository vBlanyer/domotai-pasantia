# Tablero web de observabilidad y aprobación — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una consola web local (solo stdlib) que muestre salud de servicios, feed de decisiones, cola de aprobaciones y trazas, y permita aprobar/rechazar una contención desde el navegador.

**Architecture:** Un módulo nuevo `prototipo/tablero.py` levanta un `ThreadingHTTPServer` en `127.0.0.1` con una API JSON y sirve una página estática. El daemon (`stream.py --web`) embebe el servidor en un hilo y sustituye su `leer`/`escribir` por versiones web (`LectorWeb`/`escribir_web`) que reutilizan la costura de aprobación existente; las aprobaciones se resuelven por memoria compartida (`EstadoTablero` + `threading.Event`). El feed y las trazas se leen del fichero de traza; la salud, de `salud.jsonl` como JSONL genérico.

**Tech Stack:** Python 3 stdlib (`http.server`, `threading`, `json`), HTML/CSS/JS vanilla sin build, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-22-tablero-web-observabilidad-design.md`

## Global Constraints

- Python 3 con biblioteca estándar y PyYAML; tests con `unittest`: `PYTHONPATH=. python3 -m unittest discover -s <dir> -t .`. **Sin pip, venv ni pytest. Sin dependencias nuevas.**
- Suites que siempre deben seguir en verde: `prototipo/tests`, `evaluacion/tests`, `lab/dataset/tests`, `lab/banco/tests`.
- **`prototipo/tablero.py` NO importa `lab/`** (preserva la independencia `prototipo`↔`lab`): la salud se lee como JSONL genérico y las dependencias se toman del perfil.
- El servidor liga **solo a `127.0.0.1`**; **sin autenticación** en la v1.
- Commits que terminan exactamente en `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Rama `feature/tablero-web` (ya creada). **Nunca push.**
- No se modifican el plan de trabajo, el roadmap, el informe `.tex`, los documentos de las Fases 1–4 ni `informe-evaluacion.md`.
- Clasificación de prompt idéntica a `Lector` (en `lab/banco/pruebas.py`): `tipo = "escalada"` si `"[s/N]"` está en el prompt, si no `"menu"`.

---

### Task 1: Estado compartido y puente de aprobación (`EstadoTablero`, `LectorWeb`, `escribir_web`)

Lógica pura de hilos, sin HTTP. Es el corazón: registro de pendientes con `Event`, el lector web que bloquea, y el envoltorio de `escribir` que captura las líneas del incidente en curso.

**Files:**
- Create: `prototipo/tablero.py`
- Test: `prototipo/tests/test_tablero.py`

**Interfaces:**
- Produces:
  - `EstadoTablero()` con: `anotar_linea(linea)`, `registrar_pendiente(tipo, prompt) -> (pid:str, ev:threading.Event)`, `pendientes() -> list[dict]` (sin claves `_`), `resolver(pid, respuesta) -> bool`, `respuesta_de(pid) -> str|None`, `quitar(pid)`.
  - `LectorWeb(estado, timeout=None)`, callable `__call__(prompt="") -> str`.
  - `escribir_web(estado, escribir=print) -> callable(texto)`.

- [ ] **Step 1: Write the failing tests**

```python
# prototipo/tests/test_tablero.py
import threading
import time
import unittest
from prototipo import tablero


class TestEstadoYLector(unittest.TestCase):
    def test_registrar_pendiente_y_resolver_devuelve_la_respuesta(self):
        estado = tablero.EstadoTablero()
        lector = tablero.LectorWeb(estado)
        salida = {}
        hilo = threading.Thread(target=lambda: salida.setdefault("r", lector("Elige [1-3]: ")))
        hilo.start()
        pid = None
        for _ in range(200):                       # esperar a que el lector registre la pendiente
            p = estado.pendientes()
            if p:
                pid = p[0]["id"]; break
            time.sleep(0.005)
        self.assertIsNotNone(pid)
        self.assertTrue(estado.resolver(pid, "1"))
        hilo.join(timeout=2)
        self.assertEqual(salida["r"], "1")
        self.assertEqual(estado.pendientes(), [])  # se quita al resolverse

    def test_clasifica_escalada_y_menu_como_lector(self):
        estado = tablero.EstadoTablero()
        estado.registrar_pendiente(*("escalada", "¿aprobar? [s/N] "))
        # el tipo lo pone LectorWeb; aqui comprobamos la regla directamente
        self.assertEqual(tablero.LectorWeb(estado)._tipo("¿aprobar? [s/N] "), "escalada")
        self.assertEqual(tablero.LectorWeb(estado)._tipo("Elige [1-3]: "), "menu")

    def test_resolver_id_desconocido_es_falso(self):
        self.assertFalse(tablero.EstadoTablero().resolver("999", "1"))

    def test_timeout_devuelve_respuesta_segura_vacia(self):
        estado = tablero.EstadoTablero()
        r = tablero.LectorWeb(estado, timeout=0.05)("Elige [1-3]: ")
        self.assertEqual(r, "")

    def test_anotar_linea_reinicia_en_cada_incidente(self):
        estado = tablero.EstadoTablero()
        estado.anotar_linea("⚠ Incidente A"); estado.anotar_linea("  detalle")
        pid, _ = estado.registrar_pendiente("menu", "x")
        self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ Incidente A", "  detalle"])
        estado.anotar_linea("⚠ Incidente B")   # nueva marca -> reinicia
        pid2, _ = estado.registrar_pendiente("menu", "y")
        self.assertEqual([p["lineas"] for p in estado.pendientes() if p["id"] == pid2][0],
                         ["⚠ Incidente B"])

    def test_escribir_web_imprime_y_acumula(self):
        estado = tablero.EstadoTablero()
        vistas = []
        esc = tablero.escribir_web(estado, escribir=vistas.append)
        esc("⚠ Incidente"); esc("linea 2")
        self.assertEqual(vistas, ["⚠ Incidente", "linea 2"])
        pid, _ = estado.registrar_pendiente("menu", "x")
        self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ Incidente", "linea 2"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`
Expected: FAIL (módulo `tablero` no existe).

- [ ] **Step 3: Write the minimal implementation**

```python
# prototipo/tablero.py
"""Tablero web de observabilidad y aprobacion del prototipo (solo biblioteca estandar).

Este fichero NO importa nada de lab/: la salud se lee como JSONL generico y las dependencias
llegan desde el perfil. Contiene el estado compartido y la costura de aprobacion (Task 1), los
lectores de datos (Task 2) y el servidor HTTP (Task 3).
"""
import itertools
import threading

_MARCA_INCIDENTE = "⚠"   # el resumen de incidente de stream empieza por esta marca


class EstadoTablero:
    """Estado en memoria del tablero, seguro entre hilos: pendientes de aprobacion y las lineas del
    incidente en curso. El feed de decisiones resueltas NO vive aqui (sale de la traza)."""
    def __init__(self):
        self._lock = threading.Lock()
        self._pendientes = {}
        self._lineas = []
        self._seq = itertools.count(1)

    def anotar_linea(self, linea):
        with self._lock:
            if linea.startswith(_MARCA_INCIDENTE):
                self._lineas = []
            self._lineas.append(linea)

    def registrar_pendiente(self, tipo, prompt):
        ev = threading.Event()
        with self._lock:
            pid = str(next(self._seq))
            self._pendientes[pid] = {"id": pid, "tipo": tipo, "prompt": prompt,
                                     "lineas": list(self._lineas), "respuesta": None, "_event": ev}
        return pid, ev

    def pendientes(self):
        with self._lock:
            return [{k: v for k, v in p.items() if not k.startswith("_")}
                    for p in self._pendientes.values()]

    def resolver(self, pid, respuesta):
        with self._lock:
            p = self._pendientes.get(pid)
            if p is None or p["respuesta"] is not None:
                return False
            p["respuesta"] = respuesta
            p["_event"].set()
            return True

    def respuesta_de(self, pid):
        with self._lock:
            p = self._pendientes.get(pid)
            return p["respuesta"] if p else None

    def quitar(self, pid):
        with self._lock:
            self._pendientes.pop(pid, None)


class LectorWeb:
    """leer(prompt)->str respaldado por la web: registra una pendiente y bloquea hasta que la web
    responde. Clasifica el prompt igual que Lector (escalada si contiene '[s/N]', si no menu)."""
    def __init__(self, estado, timeout=None):
        self.estado = estado
        self.timeout = timeout

    @staticmethod
    def _tipo(prompt):
        return "escalada" if "[s/N]" in prompt else "menu"

    def __call__(self, prompt=""):
        pid, ev = self.estado.registrar_pendiente(self._tipo(prompt), prompt)
        respondio = ev.wait(self.timeout)
        respuesta = self.estado.respuesta_de(pid) if respondio else ""
        self.estado.quitar(pid)
        return respuesta if respuesta is not None else ""


def escribir_web(estado, escribir=print):
    """Envuelve un `escribir`: imprime y acumula la linea en el incidente en curso (para la tarjeta)."""
    def _f(texto):
        escribir(texto)
        estado.anotar_linea(texto)
    return _f
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add prototipo/tablero.py prototipo/tests/test_tablero.py
git commit -m "feat(tablero): estado compartido y puente de aprobacion web

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Lectores de datos (salud genérica + trazas)

Funciones puras (más una de E/S para la salud) que producen el JSON de los paneles. Reutilizan `prototipo/traza.py`; **no importan `lab/`**.

**Files:**
- Modify: `prototipo/tablero.py` (añadir funciones al final, antes del servidor)
- Test: `prototipo/tests/test_tablero.py` (añadir clase)

**Interfaces:**
- Consumes: `prototipo.traza.leer_registros(ruta)`, `prototipo.traza.verificar(registros) -> {valida, n, primer_fallo, motivo}`, `prototipo.traza.encadenar(reg, hash_previo)` (para los tests).
- Produces:
  - `leer_salud(ruta=None, contenedor=None, fichero_en_contenedor=None, ejecutar=subprocess.run) -> dict|None` (última muestra `{t, estados}`).
  - `estado_salud(muestra, dependencias=None) -> dict` (`{sin_datos:True}` o `{t, servicios, caidos, total}`).
  - `lista_trazas(ruta, n=None) -> list[dict]` (resúmenes).
  - `traza_detalle(ruta, id_decision) -> dict|None`.
  - `verificar_traza(ruta) -> {ok, roto_en, motivo, n}`.

- [ ] **Step 1: Write the failing tests**

```python
# añadir a prototipo/tests/test_tablero.py
import json
import os
import subprocess
import tempfile
from prototipo import traza


class TestLectoresDeDatos(unittest.TestCase):
    def _traza_tmp(self, registros):
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_estado_salud_convierte_y_decora_dependencias(self):
        muestra = {"t": "2026-09-22T10:00:00Z", "estados": {"core-db": "ok", "middleware": "caido"}}
        r = tablero.estado_salud(muestra, {"middleware": ["core-db"]})
        self.assertEqual(r["caidos"], 1)
        self.assertEqual(r["total"], 2)
        mid = [s for s in r["servicios"] if s["nombre"] == "middleware"][0]
        self.assertEqual(mid["estado"], "caido")
        self.assertEqual(mid["depende_de"], ["core-db"])

    def test_estado_salud_sin_muestra(self):
        self.assertEqual(tablero.estado_salud(None), {"sin_datos": True})

    def test_leer_salud_de_fichero_toma_la_ultima_linea(self):
        ruta = self._traza_tmp([{"t": "1", "estados": {}}, {"t": "2", "estados": {"a": "ok"}}])
        self.assertEqual(tablero.leer_salud(ruta=ruta)["t"], "2")

    def test_leer_salud_por_docker_exec(self):
        linea = json.dumps({"t": "9", "estados": {"a": "ok"}})
        def ejec(args, **kw):
            self.assertEqual(args[:3], ["docker", "exec", "cont"])
            return subprocess.CompletedProcess(args, 0, linea + "\n", "")
        r = tablero.leer_salud(contenedor="cont", fichero_en_contenedor="/x", ejecutar=ejec)
        self.assertEqual(r["t"], "9")

    def test_leer_salud_fichero_ausente_es_none(self):
        self.assertIsNone(tablero.leer_salud(ruta="/no/existe.jsonl"))

    def test_lista_y_detalle_de_trazas(self):
        ruta = self._traza_tmp([
            {"id_decision": "s1", "timestamp": "t1", "activo": "web", "clase": "vp_intento_acceso",
             "confianza": 1.0, "accion_final": "BLOQUEAR_IP", "requiere_humano": False},
            {"id_decision": "s2", "timestamp": "t2", "activo": "core-db", "clase": "no_soportada"}])
        lst = tablero.lista_trazas(ruta)
        self.assertEqual([d["id_decision"] for d in lst], ["s1", "s2"])
        self.assertEqual(tablero.lista_trazas(ruta, n=1)[0]["id_decision"], "s2")
        self.assertEqual(tablero.traza_detalle(ruta, "s1")["accion_final"], "BLOQUEAR_IP")
        self.assertIsNone(tablero.traza_detalle(ruta, "zzz"))

    def test_lista_trazas_fichero_ausente_es_vacia(self):
        self.assertEqual(tablero.lista_trazas("/no/existe.jsonl"), [])

    def test_verificar_traza_cadena_integra_y_rota(self):
        r1 = traza.encadenar({"id_decision": "s1", "x": 1}, traza.GENESIS)
        r2 = traza.encadenar({"id_decision": "s2", "x": 2}, r1["hash"])
        buena = self._traza_tmp([r1, r2])
        self.assertTrue(tablero.verificar_traza(buena)["ok"])
        r2_malo = dict(r2, x=999)                      # contenido alterado, hash ya no cuadra
        rota = self._traza_tmp([r1, r2_malo])
        v = tablero.verificar_traza(rota)
        self.assertFalse(v["ok"])
        self.assertEqual(v["roto_en"], 1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero.TestLectoresDeDatos -v`
Expected: FAIL (funciones no definidas).

- [ ] **Step 3: Write the minimal implementation**

Añadir a `prototipo/tablero.py` (tras `escribir_web`, con los imports `json`, `subprocess` y `from prototipo import traza` al principio del fichero):

```python
import json
import subprocess

from prototipo import traza


def leer_salud(ruta=None, contenedor=None, fichero_en_contenedor=None, ejecutar=subprocess.run):
    """Ultima muestra {t, estados} del monitor: de un fichero local (ruta) o via docker exec a un
    contenedor. Devuelve None si no hay datos o no se puede leer. No conoce nada del banco."""
    linea = None
    if ruta is not None:
        try:
            with open(ruta, encoding="utf-8") as f:
                lineas = [l for l in f if l.strip()]
        except OSError:
            return None
        linea = lineas[-1] if lineas else None
    elif contenedor is not None:
        try:
            r = ejecutar(["docker", "exec", contenedor, "tail", "-n1", fichero_en_contenedor],
                         capture_output=True, text=True)
        except OSError:
            return None
        if r.returncode != 0 or not r.stdout.strip():
            return None
        linea = r.stdout.strip().splitlines()[-1]
    if not linea:
        return None
    try:
        return json.loads(linea)
    except json.JSONDecodeError:
        return None


def estado_salud(muestra, dependencias=None):
    """Convierte una muestra {t, estados} en el JSON del panel de salud, decorando dependencias."""
    if muestra is None:
        return {"sin_datos": True}
    dependencias = dependencias or {}
    estados = muestra["estados"]
    servicios = [{"nombre": n, "estado": e, "depende_de": dependencias.get(n, [])}
                 for n, e in sorted(estados.items())]
    caidos = sum(1 for e in estados.values() if e != "ok")
    return {"t": muestra.get("t"), "servicios": servicios, "caidos": caidos, "total": len(estados)}


def _resumen_traza(reg):
    imp = reg.get("impacto_determinado") or {}
    return {"id_decision": reg.get("id_decision"), "timestamp": reg.get("timestamp"),
            "activo": reg.get("activo"), "clase": reg.get("clase"), "confianza": reg.get("confianza"),
            "accion_final": reg.get("accion_final"), "requiere_humano": reg.get("requiere_humano"),
            "impacto": imp.get("impacto")}


def lista_trazas(ruta, n=None):
    try:
        regs = traza.leer_registros(ruta)
    except FileNotFoundError:
        return []
    if n:
        regs = regs[-n:]
    return [_resumen_traza(r) for r in regs]


def traza_detalle(ruta, id_decision):
    try:
        regs = traza.leer_registros(ruta)
    except FileNotFoundError:
        return None
    for r in regs:
        if r.get("id_decision") == id_decision:
            return r
    return None


def verificar_traza(ruta):
    try:
        regs = traza.leer_registros(ruta)
    except FileNotFoundError:
        regs = []
    v = traza.verificar(regs)
    return {"ok": v["valida"], "roto_en": v["primer_fallo"], "motivo": v["motivo"], "n": v["n"]}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`
Expected: PASS (Task 1 + Task 2).

- [ ] **Step 5: Commit**

```bash
git add prototipo/tablero.py prototipo/tests/test_tablero.py
git commit -m "feat(tablero): lectores de salud (JSONL generico) y de trazas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Servidor HTTP y API JSON

El `ThreadingHTTPServer` ligado a `127.0.0.1`, con los endpoints cableados a las Tasks 1 y 2 y el servido de estáticos. Guarda la configuración en atributos del servidor.

**Files:**
- Modify: `prototipo/tablero.py` (añadir el manejador y `crear_servidor` al final)
- Test: `prototipo/tests/test_tablero.py` (añadir clase con `http.client`)

**Interfaces:**
- Consumes: `EstadoTablero`, `leer_salud`, `estado_salud`, `lista_trazas`, `traza_detalle`, `verificar_traza` (Tasks 1–2).
- Produces: `crear_servidor(estado, ruta_traza, salud=None, dependencias=None, estaticos=None, puerto=8787, salud_ejecutar=subprocess.run) -> ThreadingHTTPServer` (con atributos `estado`, `ruta_traza`, `salud`, `dependencias`, `estaticos`, `salud_ejecutar`). Endpoints: `GET /`, `GET /static/<f>`, `GET /api/salud`, `GET /api/decisiones`, `GET /api/pendientes`, `GET /api/trazas`, `GET /api/traza/<id>`, `GET /api/verificar`, `POST /api/aprobar`.

- [ ] **Step 1: Write the failing tests**

```python
# añadir a prototipo/tests/test_tablero.py
import http.client


class TestServidor(unittest.TestCase):
    def _servidor(self, estado=None, ruta_traza="/no/existe.jsonl", salud=None,
                  dependencias=None, salud_ejecutar=subprocess.run, estaticos=None):
        estaticos = estaticos or tempfile.mkdtemp()
        with open(os.path.join(estaticos, "index.html"), "w", encoding="utf-8") as f:
            f.write("<html>tablero</html>")
        srv = tablero.crear_servidor(estado or tablero.EstadoTablero(), ruta_traza, salud=salud,
                                     dependencias=dependencias, estaticos=estaticos, puerto=0,
                                     salud_ejecutar=salud_ejecutar)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv, srv.server_address[1]

    def _get(self, puerto, ruta):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta); r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, cuerpo

    def _post(self, puerto, ruta, obj):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("POST", ruta, json.dumps(obj), {"Content-Type": "application/json"})
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def test_liga_solo_a_localhost(self):
        srv, _ = self._servidor()
        self.assertEqual(srv.server_address[0], "127.0.0.1")

    def test_raiz_sirve_index(self):
        _, puerto = self._servidor()
        estado, cuerpo = self._get(puerto, "/")
        self.assertEqual(estado, 200)
        self.assertIn(b"tablero", cuerpo)

    def test_pendientes_vacio_y_aprobar_resuelve(self):
        estado = tablero.EstadoTablero()
        _, puerto = self._servidor(estado=estado)
        self.assertEqual(json.loads(self._get(puerto, "/api/pendientes")[1]), [])
        salida = {}
        hilo = threading.Thread(target=lambda: salida.setdefault("r", tablero.LectorWeb(estado)("¿aprobar? [s/N] ")))
        hilo.start()
        pid = None
        for _ in range(200):
            p = json.loads(self._get(puerto, "/api/pendientes")[1])
            if p:
                pid = p[0]["id"]; self.assertEqual(p[0]["tipo"], "escalada"); break
            time.sleep(0.005)
        self.assertIsNotNone(pid)
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": pid, "respuesta": "s"}), (200, {"ok": True}))
        hilo.join(timeout=2)
        self.assertEqual(salida["r"], "s")
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": pid, "respuesta": "s"})[0], 409)

    def test_salud_desde_ejecutor_falso(self):
        def ejec(args, **kw):
            return subprocess.CompletedProcess(args, 0, json.dumps({"t": "1", "estados": {"a": "ok"}}) + "\n", "")
        _, puerto = self._servidor(salud={"contenedor": "c", "fichero_en_contenedor": "/x"}, salud_ejecutar=ejec)
        cuerpo = json.loads(self._get(puerto, "/api/salud")[1])
        self.assertEqual(cuerpo["total"], 1)

    def test_trazas_y_verificar(self):
        r1 = traza.encadenar({"id_decision": "s1"}, traza.GENESIS)
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        f.write(json.dumps(r1) + "\n"); f.close(); self.addCleanup(os.unlink, f.name)
        _, puerto = self._servidor(ruta_traza=f.name)
        self.assertEqual(json.loads(self._get(puerto, "/api/trazas")[1])[0]["id_decision"], "s1")
        self.assertEqual(self._get(puerto, "/api/traza/s1")[0], 200)
        self.assertEqual(self._get(puerto, "/api/traza/zzz")[0], 404)
        self.assertTrue(json.loads(self._get(puerto, "/api/verificar")[1])["ok"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero.TestServidor -v`
Expected: FAIL (`crear_servidor` no existe).

- [ ] **Step 3: Write the minimal implementation**

Añadir a `prototipo/tablero.py` (al final; los imports `os` y `from http.server import ...` van con los demás al principio):

```python
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
          ".css": "text/css; charset=utf-8"}
_DIR_ESTATICOS = os.path.join(os.path.dirname(__file__), "tablero")


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):        # silencioso: el daemon ya imprime lo suyo
        pass

    def _responder(self, obj, codigo=200):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _estatico(self, nombre):
        ext = os.path.splitext(nombre)[1]
        if ext not in _TIPOS or os.path.basename(nombre) != nombre:   # sin travesia de rutas
            return self._responder({"error": "no encontrado"}, 404)
        try:
            with open(os.path.join(self.server.estaticos, nombre), "rb") as f:
                datos = f.read()
        except OSError:
            return self._responder({"error": "no encontrado"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", _TIPOS[ext])
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        s = self.server
        ruta = self.path.split("?", 1)[0]
        try:
            if ruta == "/":
                return self._estatico("index.html")
            if ruta.startswith("/static/"):
                return self._estatico(ruta[len("/static/"):])
            if ruta == "/api/salud":
                return self._responder(estado_salud(leer_salud(ejecutar=s.salud_ejecutar, **s.salud),
                                                    s.dependencias))
            if ruta == "/api/decisiones":
                return self._responder(lista_trazas(s.ruta_traza, n=50))
            if ruta == "/api/pendientes":
                return self._responder(s.estado.pendientes())
            if ruta == "/api/trazas":
                return self._responder(lista_trazas(s.ruta_traza))
            if ruta.startswith("/api/traza/"):
                d = traza_detalle(s.ruta_traza, ruta[len("/api/traza/"):])
                return self._responder(d) if d is not None else self._responder({"error": "no encontrada"}, 404)
            if ruta == "/api/verificar":
                return self._responder(verificar_traza(s.ruta_traza))
            return self._responder({"error": "no encontrado"}, 404)
        except Exception as e:            # nunca tumbar el servidor por un handler
            return self._responder({"error": str(e)}, 500)

    def do_POST(self):
        try:
            if self.path.split("?", 1)[0] != "/api/aprobar":
                return self._responder({"error": "no encontrado"}, 404)
            n = int(self.headers.get("Content-Length") or 0)
            cuerpo = json.loads(self.rfile.read(n) or b"{}")
            ok = self.server.estado.resolver(str(cuerpo.get("id")), str(cuerpo.get("respuesta", "")))
            return self._responder({"ok": True}) if ok else self._responder({"error": "pendiente no vigente"}, 409)
        except Exception as e:
            return self._responder({"error": str(e)}, 500)


def crear_servidor(estado, ruta_traza, salud=None, dependencias=None, estaticos=None,
                   puerto=8787, salud_ejecutar=subprocess.run):
    """ThreadingHTTPServer ligado SOLO a 127.0.0.1. `salud` es {} o {ruta} o {contenedor,
    fichero_en_contenedor}. Guarda la config en atributos del servidor para el manejador."""
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), _Manejador)
    srv.estado = estado
    srv.ruta_traza = ruta_traza
    srv.salud = salud or {}
    srv.dependencias = dependencias or {}
    srv.estaticos = estaticos or _DIR_ESTATICOS
    srv.salud_ejecutar = salud_ejecutar
    return srv
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`
Expected: PASS (Tasks 1–3).

- [ ] **Step 5: Commit**

```bash
git add prototipo/tablero.py prototipo/tests/test_tablero.py
git commit -m "feat(tablero): servidor HTTP local y API JSON (solo 127.0.0.1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Frontend (página + JS + CSS)

Una página con cuatro pestañas que sondea la API cada 2 s y permite aprobar/rechazar. Sin build, sin dependencias. Se cierra con una prueba de humo de que los estáticos se sirven con su tipo.

**Files:**
- Create: `prototipo/tablero/index.html`, `prototipo/tablero/tablero.css`, `prototipo/tablero/tablero.js`
- Test: `prototipo/tests/test_tablero.py` (añadir prueba de humo)

**Interfaces:**
- Consumes: la API de la Task 3 (mismos endpoints y shapes) y `_DIR_ESTATICOS` (los estáticos viven junto al módulo).

- [ ] **Step 1: Write the failing smoke test**

```python
# añadir a prototipo/tests/test_tablero.py
class TestEstaticosReales(unittest.TestCase):
    def test_sirve_los_estaticos_del_modulo(self):
        srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        puerto = srv.server_address[1]
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", "/"); r = c.getresponse(); html = r.read(); c.close()
        self.assertEqual(r.status, 200)
        self.assertIn(b"Tablero", html)
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", "/static/tablero.js"); r = c.getresponse(); r.read()
        self.assertEqual(r.status, 200)
        self.assertIn("javascript", r.getheader("Content-Type"))
        c.close()
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero.TestEstaticosReales -v`
Expected: FAIL (no existe `prototipo/tablero/index.html`, `GET /` da 404).

- [ ] **Step 3: Write the frontend files**

```html
<!-- prototipo/tablero/index.html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tablero MDR</title>
  <link rel="stylesheet" href="/static/tablero.css">
</head>
<body>
  <h1>Tablero MDR</h1>
  <nav>
    <button data-tab="salud" class="activa">Salud</button>
    <button data-tab="decisiones">Decisiones</button>
    <button data-tab="aprobaciones">Aprobaciones <span id="n-pend"></span></button>
    <button data-tab="trazas">Trazas</button>
  </nav>
  <section id="salud" class="panel activa"></section>
  <section id="decisiones" class="panel"></section>
  <section id="aprobaciones" class="panel"></section>
  <section id="trazas" class="panel"></section>
  <script src="/static/tablero.js"></script>
</body>
</html>
```

```css
/* prototipo/tablero/tablero.css */
body { font-family: system-ui, sans-serif; margin: 1rem; color: #1a1a1a; }
h1 { font-size: 1.2rem; }
nav button { font: inherit; padding: .4rem .8rem; margin-right: .3rem; border: 1px solid #ccc;
  background: #f5f5f5; cursor: pointer; }
nav button.activa { background: #1a1a1a; color: #fff; }
.panel { display: none; margin-top: 1rem; }
.panel.activa { display: block; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: .3rem .6rem; border-bottom: 1px solid #eee; font-size: .9rem; }
.ok { color: #1a7f37; } .caido { color: #cf222e; font-weight: bold; }
.tarjeta { border: 1px solid #ccc; padding: .6rem; margin-bottom: .6rem; }
.tarjeta pre { background: #f5f5f5; padding: .5rem; overflow-x: auto; white-space: pre-wrap; }
.tarjeta button { font: inherit; padding: .3rem .8rem; margin-right: .4rem; cursor: pointer; }
.aprobar { background: #1a7f37; color: #fff; border: 0; } .rechazar { background: #cf222e; color: #fff; border: 0; }
```

```javascript
// prototipo/tablero/tablero.js
const $ = (s) => document.querySelector(s);
const paneles = document.querySelectorAll(".panel");

document.querySelectorAll("nav button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("activa"));
    paneles.forEach((p) => p.classList.remove("activa"));
    b.classList.add("activa");
    $("#" + b.dataset.tab).classList.add("activa");
  };
});

async function json(ruta, opciones) {
  const r = await fetch(ruta, opciones);
  return r.json();
}
const esc = (t) => String(t == null ? "" : t).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

async function pintarSalud() {
  const d = await json("/api/salud");
  if (d.sin_datos) { $("#salud").innerHTML = "<p>sin datos del monitor (¿banco levantado?)</p>"; return; }
  const filas = d.servicios.map((s) =>
    `<tr><td>${esc(s.nombre)}</td><td class="${s.estado === "ok" ? "ok" : "caido"}">${s.estado === "ok" ? "● OK" : "✖ CAÍDO"}</td><td>${esc((s.depende_de || []).join(", ") || "—")}</td></tr>`).join("");
  $("#salud").innerHTML = `<p>${d.caidos} de ${d.total} servicios caídos · ${esc(d.t)}</p>
    <table><tr><th>Servicio</th><th>Estado</th><th>Depende de</th></tr>${filas}</table>`;
}

function filasDecision(lst) {
  return lst.map((x) =>
    `<tr><td>${esc(x.timestamp)}</td><td>${esc(x.activo)}</td><td>${esc(x.clase)}</td><td>${esc(x.accion_final)}</td><td>${x.requiere_humano ? "humano" : "auto"}</td></tr>`).join("");
}
async function pintarDecisiones() {
  const lst = await json("/api/decisiones");
  $("#decisiones").innerHTML = lst.length
    ? `<table><tr><th>Cuándo</th><th>Activo</th><th>Clase</th><th>Acción</th><th></th></tr>${filasDecision(lst)}</table>`
    : "<p>sin decisiones todavía</p>";
}

async function aprobar(id, respuesta) {
  await fetch("/api/aprobar", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, respuesta }) });
  pintarPendientes();
}
async function pintarPendientes() {
  const lst = await json("/api/pendientes");
  $("#n-pend").textContent = lst.length ? "(" + lst.length + ")" : "";
  $("#aprobaciones").innerHTML = lst.length ? lst.map((p) => {
    const ctrl = p.tipo === "escalada"
      ? `<button class="aprobar" onclick="aprobar('${p.id}','s')">Aprobar</button><button class="rechazar" onclick="aprobar('${p.id}','')">Rechazar</button>`
      : `<button class="aprobar" onclick="aprobar('${p.id}','1')">Aprobar (1)</button><button class="rechazar" onclick="aprobar('${p.id}','2')">Rechazar (2)</button>
         <input id="r-${p.id}" size="3" placeholder="otra"><button onclick="aprobar('${p.id}',document.getElementById('r-${p.id}').value)">Enviar</button>`;
    return `<div class="tarjeta"><pre>${esc((p.lineas || []).join("\n"))}</pre><p>${esc(p.prompt)}</p>${ctrl}</div>`;
  }).join("") : "<p>ninguna decisión esperando</p>";
}

async function pintarTrazas() {
  const lst = await json("/api/trazas");
  const v = await json("/api/verificar");
  const cadena = v.ok ? '<span class="ok">cadena íntegra</span>' : `<span class="caido">cadena rota en ${esc(v.roto_en)}: ${esc(v.motivo)}</span>`;
  $("#trazas").innerHTML = `<p>${cadena} · <button onclick="pintarTrazas()">verificar</button></p>` +
    (lst.length ? `<table><tr><th>Cuándo</th><th>Activo</th><th>Clase</th><th>Acción</th></tr>${filasDecision(lst)}</table>` : "<p>sin trazas</p>");
}

function refrescar() { pintarSalud(); pintarDecisiones(); pintarPendientes(); pintarTrazas(); }
refrescar();
setInterval(refrescar, 2000);
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_tablero -v`
Expected: PASS (todas).

- [ ] **Step 5: Commit**

```bash
git add prototipo/tablero/ prototipo/tests/test_tablero.py
git commit -m "feat(tablero): frontend (4 paneles, sondeo, aprobar/rechazar)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Cablear `stream.py --web`

Bandera nueva, y en `main` armar el estado, arrancar el servidor en un hilo e inyectar `escribir_web`/`LectorWeb` en `ejecutar`. Un helper `construir_web` deja esto testeable sin correr el lazo.

**Files:**
- Modify: `prototipo/stream.py` (`parsear_args`, un helper `construir_web`, y `main`)
- Test: `prototipo/tests/test_stream.py` (añadir tests)

**Interfaces:**
- Consumes: `tablero.EstadoTablero`, `tablero.crear_servidor`, `tablero.LectorWeb`, `tablero.escribir_web`; `ejecutar(..., escribir=, leer=)` (ya existe).
- Produces: `parsear_args` devuelve además `web:bool`, `web_puerto:int`. `construir_web(cfg, perfil) -> (estado, servidor, escribir_fn, leer_fn)`.

- [ ] **Step 1: Write the failing tests**

```python
# añadir a prototipo/tests/test_stream.py (ya importa os, tempfile, unittest; añade tablero)
from prototipo import tablero


class TestWeb(unittest.TestCase):
    def test_parsear_args_web(self):
        self.assertIs(stream.parsear_args(["-", "p"])["web"], False)
        cfg = stream.parsear_args(["-", "p", "--web"])
        self.assertTrue(cfg["web"])
        self.assertEqual(cfg["web_puerto"], 8787)
        self.assertEqual(stream.parsear_args(["-", "p", "--web", "9000"])["web_puerto"], 9000)

    def test_construir_web_liga_a_localhost_e_inyecta_lector(self):
        d = tempfile.mkdtemp()
        cfg = {"web": True, "web_puerto": 0, "salida": os.path.join(d, "t.jsonl")}
        perfil = {"activos": {"middleware": {"depende_de": ["core-db"]}}}
        estado, servidor, escribir_fn, leer_fn = stream.construir_web(cfg, perfil)
        try:
            self.assertEqual(servidor.server_address[0], "127.0.0.1")
            self.assertIsInstance(estado, tablero.EstadoTablero)
            self.assertIsInstance(leer_fn, tablero.LectorWeb)
            self.assertEqual(servidor.dependencias, {"middleware": ["core-db"]})
            escribir_fn("⚠ hola")               # imprime y acumula
            estado.registrar_pendiente("menu", "x")
            self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ hola"])
        finally:
            servidor.server_close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_stream -v`
Expected: FAIL (`web` no está en cfg; `construir_web` no existe).

- [ ] **Step 3: Implement**

En `prototipo/stream.py`:

1. En `parsear_args`, añade los valores por defecto y el manejo de la bandera:

```python
def parsear_args(argv):
    pos, con_llm, ventana, salida, sin_lab, agente = [], False, 5, "trazas-stream.jsonl", False, False
    web, web_puerto = False, 8787
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--con-llm": con_llm = True
        elif a == "--sin-llm": con_llm = False
        elif a == "--sin-lab": sin_lab = True
        elif a == "--agente": agente = True
        elif a == "--web":
            web = True
            if i + 1 < len(argv) and argv[i + 1].isdigit(): i += 1; web_puerto = int(argv[i])
        elif a == "--ventana-agrupacion": i += 1; ventana = int(argv[i])
        elif a == "--salida": i += 1; salida = argv[i]
        else: pos.append(a)
        i += 1
    return {"ruta": pos[0] if pos else "-",
            "perfil": pos[1] if len(pos) > 1 else _PERFIL_DEF,
            "hallazgos": pos[2] if len(pos) > 2 else _HALLAZGOS_DEF,
            "con_llm": con_llm, "ventana": ventana, "salida": salida, "sin_lab": sin_lab,
            "agente": agente, "web": web, "web_puerto": web_puerto}
```

2. Añade el helper y la constante de salud por defecto (junto a los demás helpers, p. ej. tras `construir_justificar_fn`):

```python
_SALUD_DEF = {"contenedor": "clab-banco-mdr-siem", "fichero_en_contenedor": "/var/log/banco/salud.jsonl"}

def construir_web(cfg, perfil):
    """Arma el tablero para --web: EstadoTablero, el servidor (ligado a 127.0.0.1, SIN arrancar el
    hilo), y los `escribir`/`leer` web que se inyectan en ejecutar. Las dependencias salen del perfil."""
    from prototipo import tablero
    estado = tablero.EstadoTablero()
    deps = {n: (a or {}).get("depende_de", []) for n, a in (perfil.get("activos") or {}).items()}
    servidor = tablero.crear_servidor(estado, cfg["salida"], salud=_SALUD_DEF, dependencias=deps,
                                      puerto=cfg["web_puerto"])
    return estado, servidor, tablero.escribir_web(estado), tablero.LectorWeb(estado)
```

3. En `main`, entre construir `ejecutor`/`fuente` y el bloque `try`, elige los `escribir`/`leer` y arranca el hilo si `--web`:

```python
    servidor = None
    if cfg["web"]:
        import threading
        estado, servidor, escribir_fn, leer_fn = construir_web(cfg, perfil)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        print(f"[web] tablero en http://127.0.0.1:{servidor.server_address[1]}")
    else:
        escribir_fn, leer_fn = print, _leer_interactivo()   # comportamiento actual (terminal)
```

y en la llamada a `ejecutar(...)` pasa `escribir=escribir_fn` y cambia `leer=_leer_interactivo()` por `leer=leer_fn`:

```python
            resumen = ejecutar(fuente, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                               justificar_fn=justificar_fn, ventana_agrupacion=cfg["ventana"],
                               salida_traza=traza_f, escribir=escribir_fn, leer=leer_fn,
                               mitigar_fn=mitigar_fn, hash_previo=hash_previo, n_previos=n_previos,
                               nombre_traza=os.path.basename(cfg["salida"]), linaje=linaje)
```

(`threading` ya se importa arriba dentro de `main` para el hilo; si prefieres, súbelo a los imports del módulo.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_stream prototipo.tests.test_tablero -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/stream.py prototipo/tests/test_stream.py
git commit -m "feat(tablero): stream.py --web embebe el tablero y aprueba por web

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Documentación y verificación en vivo

Documentar cómo se usa y dejar una verificación manual de extremo a extremo (lo único que las pruebas unitarias no cubren: aprobar de verdad desde el navegador).

**Files:**
- Modify: `docs/pruebas/README.md` (una línea en el arranque rápido), `docs/pruebas/03-lab-en-vivo.md` (sección `--web`), `documentacion/00-general/estado-y-riesgos.md` (D11: la UI web existe en v1).
- Create: `docs/pruebas/09-tablero-web.md` (guía corta + verificación manual).

- [ ] **Step 1: Escribe la guía**

Crea `docs/pruebas/09-tablero-web.md` con: qué es, cómo se arranca (`python3 -m prototipo.stream <fuente> <perfil> <hallazgos> --web` con el banco levantado y el monitor corriendo), la URL `http://127.0.0.1:8787`, los cuatro paneles, y la nota honesta de seguridad (solo localhost, sin auth, un clic dispara `iptables` real). Incluye la **verificación de extremo a extremo**:

```
1. sh lab/lab.sh up banco && sh lab/banco/banco.sh aprovisionar
2. (arranca el monitor si no corre; ver 08) 
3. python3 -m prototipo.stream <fuente-wazuh> prototipo/perfiles/bancario.yml \
       lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --web
4. Abre http://127.0.0.1:8787 → pestaña Salud muestra los nodos; lanza un ataque que exija
   humano (p. ej. A1 del banco de pruebas) → aparece en Aprobaciones → pulsa Aprobar/Rechazar →
   la decisión pasa a Decisiones y a la traza; verifica la cadena en Trazas.
```

- [ ] **Step 2: Enlaza y actualiza**

- En `docs/pruebas/README.md`, añade al arranque rápido: `# 5) Tablero web (con el daemon)` con el comando `--web`, y una entrada al índice apuntando a `09-tablero-web.md`.
- En `docs/pruebas/03-lab-en-vivo.md`, añade un párrafo corto: el daemon acepta `--web` para observar y aprobar desde el navegador (remite a la guía 09).
- En `documentacion/00-general/estado-y-riesgos.md`, actualiza la nota D11 para decir que la v1 de la UI web existe (`prototipo/tablero.py`, `stream.py --web`): observabilidad + aprobación, solo localhost sin auth; login/TLS siguen como trabajo futuro.

- [ ] **Step 3: Verificación de suites y commit**

Run: `for d in prototipo/tests evaluacion/tests lab/dataset/tests lab/banco/tests; do PYTHONPATH=. python3 -m unittest discover -s $d -t . 2>&1 | tail -1; done`
Expected: `OK` en las cuatro.

```bash
git add docs/pruebas/09-tablero-web.md docs/pruebas/README.md docs/pruebas/03-lab-en-vivo.md documentacion/00-general/estado-y-riesgos.md
git commit -m "docs(tablero): guia del tablero web y nota D11 (UI web v1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Verificación (plan completo)

1. **Suites verdes:** `prototipo/tests` (con `test_tablero.py` y los nuevos de `test_stream.py`), más `evaluacion/tests`, `lab/dataset/tests`, `lab/banco/tests` — cero regresión.
2. **Sin dependencias nuevas** y `prototipo/tablero.py` **no importa `lab/`** (`grep -n "import lab" prototipo/tablero.py` vacío).
3. **Solo localhost:** el servidor liga a `127.0.0.1` (test `test_liga_solo_a_localhost`).
4. **Aprobación de extremo a extremo (manual, Task 6):** una decisión que requiere humano aparece en Aprobaciones y, al pulsar, se ejecuta y pasa al feed y a la traza.
5. **Modo solo lectura:** el tablero arranca y sirve salud/trazas aunque no haya daemon (los endpoints degradan a vacío/`sin_datos`).
