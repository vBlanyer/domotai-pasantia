# Fase 5B — Lazo en vivo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el lazo del motor de triaje: de la decisión de 5A a la ejecución real sobre el nodo, con validación humana, verificación y traza del lazo completo.

**Architecture:** Módulos nuevos en `prototipo/` que consumen la decisión de 5A y una **orden de acción como dato plano** (frontera que mantiene barato un futuro conector en Go). El conector traduce acción→comando del catálogo cerrado y ejecuta por un **ejecutor inyectable** (SSH en el lab, falso en los tests). Validación humana por terminal, verificación por el comando del catálogo, y una traza que reúne todo el lazo.

**Tech Stack:** Python 3.14 (stdlib: `json`, `unittest`, `subprocess`; `pyyaml`). **Sin pip/venv/pytest.** El ejecutor SSH del laboratorio usa `docker exec` + `ssh`; el resto se prueba con ejecutor/input falsos, sin laboratorio.

**Spec:** [docs/superpowers/specs/2026-08-31-fase5b-lazo-en-vivo-design.md](../specs/2026-08-31-fase5b-lazo-en-vivo-design.md)

## Global Constraints

- **Sin dependencias externas.** Solo stdlib + `pyyaml`. Tests con `python3 -m unittest`, nunca pytest. Ejecutar desde la raíz del repo.
- **La orden es dato plano** (dict/JSON), nunca un objeto acoplado: un conector en Go leería el mismo JSON. `conector.py` tiene un `__main__` que lee una orden de stdin.
- **El motor no emite comandos:** el conector selecciona la acción del catálogo cerrado (`catalogo.yml`) y materializa el comando. RF-15.
- **Idempotencia por verificar-antes-de-actuar** (RF de flujo §5): antes de ejecutar, comprobar si el estado deseado ya está; si sí, no reejecutar.
- **El ejecutor se inyecta.** Firma: `ejecutor(nodo_ip, comando) -> (codigo_salida:int, salida:str)`. En los tests es falso; solo `ejecutor_ssh_lab` toca el laboratorio y se valida en vivo, no con unittest.
- **La lectura de la validación humana se inyecta** (`leer=input`), para probar la TUI sin teclear.
- **RF-09 — traza reproducible:** cada registro del lazo reúne decisión + veredicto humano + orden + ejecución + verificación, con timestamps pasados como parámetro.
- **Reutiliza 5A:** `triaje.procesar`, `catalogo.cargar_catalogo`, `perfil.cargar`. No los reimplementes.
- **UTF-8**; `ensure_ascii=False` al escribir JSON. Commits en español terminados con: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Estructura de ficheros

```
prototipo/
├── orden.py           construye la orden de acción (mensaje) desde decisión + alerta
├── conector.py        traduce acción→comando, ejecuta por el ejecutor, captura (+ __main__)
├── validacion.py      la TUI de validación humana (mostrar + pedir)
├── verificacion.py    confirma el efecto de la acción
├── lazo.py            orquestador del lazo en vivo + CLI
└── tests/
    ├── test_orden.py
    ├── test_conector.py
    ├── test_validacion.py
    ├── test_verificacion.py
    └── test_lazo.py
```

Todos consumen la decisión de 5A (dict con `accion_final`, `activo`, `id_decision`, `impacto`, `justificacion`, `requiere_humano`, `clase`, `prioridad`, `confianza`).

---

## Task 1: La orden de acción

**Files:**
- Create: `prototipo/orden.py`
- Test: `prototipo/tests/test_orden.py`

**Interfaces:**
- Produces: `construir(decision, alerta) -> dict | None`. Devuelve `None` si `decision["accion_final"]` es None. Campos de la orden: `decision_id, accion_id, nodo_objetivo, nodo_ip, params, impacto, justificacion`. `IP_DE_NODO` mapea el activo a su IP del plano de datos.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_orden.py
import unittest
from prototipo import orden

DECISION_VP = {
    "id_decision": "d1", "activo": "objetivo-vuln", "accion_final": "BLOQUEAR_IP",
    "impacto": "localizado", "justificacion": "...", "requiere_humano": False,
}
ALERTA = {"origen_ip": "192.168.1.10", "servicio": "ssh"}

class TestConstruir(unittest.TestCase):
    def test_orden_de_bloquear_ip(self):
        o = orden.construir(DECISION_VP, ALERTA)
        self.assertEqual(o["accion_id"], "BLOQUEAR_IP")
        self.assertEqual(o["nodo_objetivo"], "objetivo-vuln")
        self.assertEqual(o["nodo_ip"], "192.168.1.30")
        self.assertEqual(o["params"], {"ip": "192.168.1.10"})
        self.assertEqual(o["decision_id"], "d1")

    def test_sin_accion_devuelve_none(self):
        d = dict(DECISION_VP); d["accion_final"] = None
        self.assertIsNone(orden.construir(d, ALERTA))
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_orden -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/orden.py
"""Construye la orden de acción (mensaje) que el conector consume. Frontera motor↔conector."""

# Mapa activo->IP del plano de datos (lab). Un despliegue real lo resolvería del inventario (V4).
IP_DE_NODO = {
    "objetivo-vuln": "192.168.1.30", "puesto": "192.168.1.10",
    "iot": "192.168.1.20", "borde": "192.168.1.1",
}
_ACCIONES_SOBRE_ORIGEN = {"BLOQUEAR_IP", "MATAR_CONEXION"}

def construir(decision, alerta):
    accion = decision.get("accion_final")
    if accion is None:
        return None
    activo = decision.get("activo")
    if accion in _ACCIONES_SOBRE_ORIGEN:
        params = {"ip": alerta.get("origen_ip")}
    else:
        params = {"servicio": alerta.get("servicio")}
    return {
        "decision_id": decision.get("id_decision"),
        "accion_id": accion,
        "nodo_objetivo": activo,
        "nodo_ip": IP_DE_NODO.get(activo),
        "params": params,
        "impacto": decision.get("impacto"),
        "justificacion": decision.get("justificacion"),
    }
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_orden -v`
Expected: PASS (2)

- [ ] **Step 5: Commit**

```bash
git add prototipo/orden.py prototipo/tests/test_orden.py
git commit -m "Orden de accion: la frontera motor-conector como dato plano

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: El conector (traducción, idempotencia, ejecución)

**Files:**
- Create: `prototipo/conector.py`
- Test: `prototipo/tests/test_conector.py`

**Interfaces:**
- Consumes: el catálogo (5A), una orden (Task 1).
- Produces:
  - `render_comando(catalogo, accion_id, params) -> str`
  - `ejecutar_orden(orden, catalogo, ejecutor, timestamp) -> dict` con `{decision_id, accion_id, nodo, comando_ejecutado, codigo_salida, salida, exito, idempotente, timestamp}`. `ejecutor(nodo_ip, comando) -> (int, str)`.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_conector.py
import os, unittest
from prototipo import conector, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
ORDEN = {"decision_id": "d1", "accion_id": "BLOQUEAR_IP", "nodo_objetivo": "objetivo-vuln",
         "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}, "impacto": "localizado"}

class EjecutorFalso:
    """Simula iptables: la regla no existe hasta que se aplica."""
    def __init__(self): self.aplicada = False; self.llamadas = []
    def __call__(self, nodo_ip, comando):
        self.llamadas.append(comando)
        if "grep" in comando:                       # verificación
            return (0, "DROP ... 192.168.1.10") if self.aplicada else (1, "")
        if "-A INPUT" in comando:                    # aplicar
            self.aplicada = True; return (0, "")
        return (0, "")

class TestConector(unittest.TestCase):
    def test_render_rellena_params(self):
        cmd = conector.render_comando(CAT, "BLOQUEAR_IP", {"ip": "1.2.3.4"})
        self.assertEqual(cmd, "iptables -A INPUT -s 1.2.3.4 -j DROP")

    def test_ejecuta_y_verifica(self):
        ej = EjecutorFalso()
        r = conector.ejecutar_orden(ORDEN, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["exito"])
        self.assertFalse(r["idempotente"])
        self.assertEqual(r["comando_ejecutado"], "iptables -A INPUT -s 192.168.1.10 -j DROP")

    def test_idempotente_si_ya_aplicada(self):
        ej = EjecutorFalso(); ej.aplicada = True     # ya está
        r = conector.ejecutar_orden(ORDEN, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["idempotente"])
        self.assertTrue(r["exito"])
        self.assertNotIn("-A INPUT", " ".join(ej.llamadas))   # NO reejecutó la acción
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_conector -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/conector.py
"""El conector: traduce la orden a un comando del catálogo y lo ejecuta por el ejecutor inyectado."""
import json, sys

def render_comando(catalogo, accion_id, params):
    return catalogo[accion_id]["comando"].format(**params)

def _resultado(orden, comando, rc, salida, exito, idempotente, timestamp):
    return {
        "decision_id": orden.get("decision_id"), "accion_id": orden.get("accion_id"),
        "nodo": orden.get("nodo_objetivo"), "comando_ejecutado": comando,
        "codigo_salida": rc, "salida": salida, "exito": exito,
        "idempotente": idempotente, "timestamp": timestamp,
    }

def ejecutar_orden(orden, catalogo, ejecutor, timestamp):
    acc = catalogo[orden["accion_id"]]
    cmd_verif = acc["verificacion"].format(**orden["params"])
    # 1. Verificar-antes-de-actuar: si ya está en el estado deseado, no reejecutar (idempotencia).
    rc_v, out_v = ejecutor(orden["nodo_ip"], cmd_verif)
    if rc_v == 0:
        return _resultado(orden, None, rc_v, out_v, True, True, timestamp)
    # 2. Ejecutar y volver a verificar para confirmar el efecto.
    cmd = render_comando(catalogo, orden["accion_id"], orden["params"])
    rc, out = ejecutor(orden["nodo_ip"], cmd)
    rc_v2, out_v2 = ejecutor(orden["nodo_ip"], cmd_verif)
    return _resultado(orden, cmd, rc, out, rc == 0 and rc_v2 == 0, False, timestamp)

def _main(argv):  # lee una orden de stdin y la ejecuta (frontera de proceso; futuro conector en Go)
    import os, yaml
    from prototipo import catalogo as catm
    orden = json.loads(sys.stdin.read())
    cat = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
    r = ejecutar_orden(orden, cat, ejecutor_ssh_lab, argv[1] if len(argv) > 1 else "")
    print(json.dumps(r, ensure_ascii=False))

def ejecutor_ssh_lab(nodo_ip, comando):  # el ejecutor del laboratorio (se valida en vivo, no en unittest)
    import subprocess
    ssh = ("ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "
           "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no "
           "-o PreferredAuthentications=password")
    remoto = f"echo msfadmin | sudo -S {comando}"
    cp = subprocess.run(
        ["docker", "exec", "clab-red-cliente-auditor", "sh", "-c",
         f"sshpass -p msfadmin {ssh} msfadmin@{nodo_ip} \"{remoto}\""],
        capture_output=True, text=True)
    return (cp.returncode, cp.stdout + cp.stderr)

if __name__ == "__main__":
    _main(sys.argv)
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_conector -v`
Expected: PASS (3)

- [ ] **Step 5: Commit**

```bash
git add prototipo/conector.py prototipo/tests/test_conector.py
git commit -m "Conector: traduce accion a comando e idempotencia verificar-antes-de-actuar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: La validación humana (TUI)

**Files:**
- Create: `prototipo/validacion.py`
- Test: `prototipo/tests/test_validacion.py`

**Interfaces:**
- Produces:
  - `mostrar(decision, alerta) -> str` (la presentación, testeable).
  - `pedir(decision, alerta, leer=input, escribir=print) -> str` con veredicto en {`aprobar`, `rechazar`, `modificar`}. Por defecto `rechazar` (seguro) ante respuesta no reconocida.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_validacion.py
import unittest
from prototipo import validacion

DECISION = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 0.5,
            "justificacion": "Alerta 5760 desde 192.168.1.10 ...", "accion_propuesta": "BLOQUEAR_IP",
            "accion_final": "BLOQUEAR_IP", "impacto": "localizado", "resultado_filtro": "veta"}
ALERTA = {"activo": "objetivo-vuln", "origen_ip": "192.168.1.10", "servicio": "ssh"}

class TestValidacion(unittest.TestCase):
    def test_mostrar_incluye_lo_esencial(self):
        txt = validacion.mostrar(DECISION, ALERTA)
        for frag in ("vp_intento_acceso", "0.5", "BLOQUEAR_IP", "192.168.1.10", "objetivo-vuln"):
            self.assertIn(frag, txt)

    def test_pedir_aprobar(self):
        v = validacion.pedir(DECISION, ALERTA, leer=lambda _: "aprobar", escribir=lambda _: None)
        self.assertEqual(v, "aprobar")

    def test_pedir_rechazar(self):
        v = validacion.pedir(DECISION, ALERTA, leer=lambda _: "r", escribir=lambda _: None)
        self.assertEqual(v, "rechazar")

    def test_respuesta_desconocida_es_rechazar(self):
        v = validacion.pedir(DECISION, ALERTA, leer=lambda _: "xyz", escribir=lambda _: None)
        self.assertEqual(v, "rechazar")
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_validacion -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/validacion.py
"""Validación humana por terminal (D11): muestra la decisión y captura el veredicto (RF-08)."""

def mostrar(decision, alerta):
    return (
        "── Validación humana requerida ──\n"
        f"Activo: {alerta.get('activo')}  ·  Origen: {alerta.get('origen_ip')}  ·  Servicio: {alerta.get('servicio')}\n"
        f"Clase: {decision.get('clase')}  ·  Prioridad: {decision.get('prioridad')}  ·  Confianza: {decision.get('confianza')}\n"
        f"Justificación: {decision.get('justificacion')}\n"
        f"Acción propuesta: {decision.get('accion_propuesta')}  ·  Impacto: {decision.get('impacto')}  ·  Filtro: {decision.get('resultado_filtro')}\n"
        f"Acción final: {decision.get('accion_final')}\n"
    )

def pedir(decision, alerta, leer=input, escribir=print):
    escribir(mostrar(decision, alerta))
    resp = leer("¿aprobar / rechazar / modificar? ").strip().lower()
    if resp.startswith("a"):
        return "aprobar"
    if resp.startswith("m"):
        return "modificar"
    return "rechazar"   # por defecto, seguro
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_validacion -v`
Expected: PASS (4)

- [ ] **Step 5: Commit**

```bash
git add prototipo/validacion.py prototipo/tests/test_validacion.py
git commit -m "Validacion humana por terminal: mostrar la decision y capturar el veredicto

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: La verificación

**Files:**
- Create: `prototipo/verificacion.py`
- Test: `prototipo/tests/test_verificacion.py`

**Interfaces:**
- Produces: `confirmar(orden, catalogo, ejecutor) -> dict` con `{verificado: bool, evidencia: str}`. Ejecuta el comando `verificacion` del catálogo (independiente del conector) y confirma el estado.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_verificacion.py
import os, unittest
from prototipo import verificacion, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
ORDEN = {"accion_id": "BLOQUEAR_IP", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}

class TestVerificacion(unittest.TestCase):
    def test_verificado_cuando_la_regla_esta(self):
        r = verificacion.confirmar(ORDEN, CAT, lambda ip, cmd: (0, "DROP ... 192.168.1.10"))
        self.assertTrue(r["verificado"])
        self.assertIn("192.168.1.10", r["evidencia"])

    def test_no_verificado_cuando_no_esta(self):
        r = verificacion.confirmar(ORDEN, CAT, lambda ip, cmd: (1, ""))
        self.assertFalse(r["verificado"])
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_verificacion -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/verificacion.py
"""Confirma el efecto de una acción ejecutando el comando de verificación del catálogo."""

def confirmar(orden, catalogo, ejecutor):
    cmd = catalogo[orden["accion_id"]]["verificacion"].format(**orden["params"])
    rc, salida = ejecutor(orden["nodo_ip"], cmd)
    return {"verificado": rc == 0, "evidencia": salida}
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_verificacion -v`
Expected: PASS (2)

- [ ] **Step 5: Commit**

```bash
git add prototipo/verificacion.py prototipo/tests/test_verificacion.py
git commit -m "Verificacion: confirma el efecto de la accion con el comando del catalogo

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: El orquestador del lazo en vivo

**Files:**
- Create: `prototipo/lazo.py`
- Test: `prototipo/tests/test_lazo.py`

**Interfaces:**
- Consumes: `triaje.procesar` (5A), `orden.construir`, `conector.ejecutar_orden`, `validacion.pedir`, `verificacion.confirmar`.
- Produces: `procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp, leer=input) -> dict` — la traza del lazo completo. Y `main(argv)` CLI con modo `--auto` (ejecutor falso).

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_lazo.py
import json, os, unittest, yaml
from prototipo import lazo, catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
def j(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return json.loads(f.read().strip())
def y(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return yaml.safe_load(f)

def ejecutor_ok(nodo_ip, comando):
    # verificación: no está antes de aplicar, sí después; aplicar: rc 0
    if "grep" in comando: return (1, "")   # primera verificación: no está
    return (0, "")

class TestLazo(unittest.TestCase):
    def test_lazo_vp_ejecuta_y_traza(self):
        # alerta_vp: fuerza bruta SSH contra objetivo-vuln con SSH expuesto -> vp_intento -> BLOQUEAR_IP -> permite
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                               "prueba", CAT, ejecutor_ok, "d1", "2026-08-31T00:00:00Z")
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertIsNotNone(r["orden"])
        self.assertEqual(r["orden"]["accion_id"], "BLOQUEAR_IP")
        self.assertIsNotNone(r["ejecucion"])
        self.assertIn("verificacion", r)
        self.assertIsNone(r["veredicto_humano"])   # confianza alta, no requiere humano

    def test_lazo_rechazo_humano_no_ejecuta(self):
        # forzamos requiere_humano con confianza baja: activo desconocido -> postura None -> confianza 0.5 -> veta
        a = dict(j("alerta_vp.json")); a["activo"] = "fantasma"
        r = lazo.procesar_lazo(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                               ejecutor_ok, "d2", "2026-08-31T00:00:00Z", leer=lambda _: "rechazar")
        self.assertEqual(r["veredicto_humano"], "rechazar")
        self.assertIsNone(r["ejecucion"])          # rechazada -> no se ejecuta
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_lazo -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/lazo.py
"""Orquestador del lazo en vivo: decisión (5A) -> validación -> orden -> conector -> verificación -> traza."""
import json, os, sys, yaml
from prototipo import triaje, orden as ordenm, conector, validacion, verificacion, perfil as perfilm, catalogo as catm

def procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp, leer=input):
    decision = triaje.procesar(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp)
    veredicto = None
    if decision.get("requiere_humano"):
        veredicto = validacion.pedir(decision, alerta, leer=leer)
        if veredicto == "rechazar":
            return {**decision, "veredicto_humano": veredicto, "orden": None, "ejecucion": None, "verificacion": None}
    o = ordenm.construir(decision, alerta)
    if o is None:
        return {**decision, "veredicto_humano": veredicto, "orden": None, "ejecucion": None, "verificacion": None}
    ejecucion = conector.ejecutar_orden(o, catalogo, ejecutor, timestamp)
    verif = verificacion.confirmar(o, catalogo, ejecutor)
    return {**decision, "veredicto_humano": veredicto, "orden": o, "ejecucion": ejecucion, "verificacion": verif}

def _ejecutor_auto(nodo_ip, comando):   # ejecutor falso para --auto (sin laboratorio)
    if "grep" in comando:
        return (1, "")
    return (0, "(simulado)")

def main(argv):
    args = [a for a in argv[1:] if a != "--auto"]
    auto = "--auto" in argv
    alertas_path, perfil_path, hallazgos_path, salida = args[0:4]
    perfil = perfilm.cargar(perfil_path)
    perfil_nombre = os.path.basename(perfil_path).replace(".yml", "")
    with open(hallazgos_path, encoding="utf-8") as f:
        hallazgos = json.load(f)
    catalogo = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
    ejecutor = _ejecutor_auto if auto else conector.ejecutor_ssh_lab
    n = 0
    with open(alertas_path, encoding="utf-8") as fin, open(salida, "w", encoding="utf-8") as fout:
        for i, linea in enumerate(fin):
            linea = linea.strip()
            if not linea:
                continue
            try:
                alerta = json.loads(linea)
            except json.JSONDecodeError:
                continue
            r = procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                              f"d{i}", alerta.get("timestamp", ""))
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} pasos del lazo -> {salida}")

if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Verificar que pasa + batería completa**

Run: `python3 -m unittest discover -s prototipo/tests -v`
Expected: PASS (todas)

- [ ] **Step 5: Commit**

```bash
git add prototipo/lazo.py prototipo/tests/test_lazo.py
git commit -m "Orquestador del lazo en vivo y CLI (modo --auto sin laboratorio)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Ejecución en vivo contra el laboratorio

**Files:**
- (ninguno de código; produce evidencia de la ejecución en vivo)

**Interfaces:**
- Consumes: todo lo anterior + el laboratorio desplegado.
- Produces: la prueba de que el conector ejecuta `BLOQUEAR_IP` sobre `objetivo-vuln` de verdad, y su reversión.

- [ ] **Step 1: Asegurar el laboratorio arriba**

Run:
```bash
sh lab/lab.sh status 2>/dev/null | grep -q OK || (sh lab/lab.sh down; sh lab/lab.sh up)
docker exec clab-red-cliente-auditor sh -c 'command -v sshpass >/dev/null 2>&1 || apk add --no-cache openssh-client sshpass >/dev/null 2>&1'
```

- [ ] **Step 2: Ejecutar el ejecutor del lab directamente (acción + verificación + reversión)**

Run:
```bash
python3 - <<'PY'
from prototipo import conector, catalogo
CAT = catalogo.cargar_catalogo("prototipo/catalogo.yml")
orden = {"decision_id":"live1","accion_id":"BLOQUEAR_IP","nodo_objetivo":"objetivo-vuln",
         "nodo_ip":"192.168.1.30","params":{"ip":"192.168.1.10"},"impacto":"localizado"}
r = conector.ejecutar_orden(orden, CAT, conector.ejecutor_ssh_lab, "live")
print("EJECUCION:", r["exito"], r["comando_ejecutado"], "rc", r["codigo_salida"])
# revertir para dejar el lab limpio
rc, out = conector.ejecutor_ssh_lab("192.168.1.30", "iptables -D INPUT -s 192.168.1.10 -j DROP")
print("REVERSION rc:", rc)
PY
```
Expected: `EJECUCION: True iptables -A INPUT -s 192.168.1.10 -j DROP rc 0` y `REVERSION rc: 0`. Si `exito` es False, revisa que el sshd de objetivo-vuln acepta login (msfadmin/msfadmin) y que sshpass está instalado en el auditor.

- [ ] **Step 3: Ejecutar el lazo en vivo sobre una alerta y confirmar la traza**

Run:
```bash
# extrae UNA alerta VP real del dataset (activo objetivo-vuln, servicio ssh expuesto)
python3 - <<'PYSEL'
import json
for l in open("lab/dataset/etiquetado.jsonl", encoding="utf-8"):
    if json.loads(l)["etiqueta"] == "VP":
        open("/tmp/una-alerta.jsonl", "w", encoding="utf-8").write(l)
        break
PYSEL
python3 -m prototipo.lazo /tmp/una-alerta.jsonl prototipo/perfiles/empresarial.yml lab/campañas/2026-08-31-evaluacion/hallazgos.json /tmp/lazo-vivo.jsonl
python3 -c "import json;r=json.loads(open('/tmp/lazo-vivo.jsonl',encoding='utf-8').readline());print('clase',r['clase'],'| orden',r['orden'] and r['orden']['accion_id'],'| ejecucion_exito',r['ejecucion'] and r['ejecucion']['exito'],'| verificado',r['verificacion'] and r['verificacion']['verificado'])"
# limpiar la regla que dejó
docker exec clab-red-cliente-auditor sh -c "sshpass -p msfadmin ssh -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no -o PreferredAuthentications=password msfadmin@192.168.1.30 'echo msfadmin | sudo -S iptables -F' 2>/dev/null" || true
```
Expected: una traza con `clase vp_intento_acceso`, `orden BLOQUEAR_IP`, `ejecucion_exito True`, `verificado True`. Anota el resultado real en el informe.

- [ ] **Step 4: Commit (registro de la verificación en vivo)**

No hay cambios de código; si generaste algún artefacto de evidencia versionable (no /tmp), añádelo. Si no, salta el commit y anota en el informe que la verificación en vivo pasó.

---

## Task 7: Escenario de validación humana, cierre y documentación

**Files:**
- Create: `prototipo/README.md` (actualizar sección) — o modificar el existente
- Modify: `documentacion/05-fase5-implementacion-del-prototipo/README.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: la demo de la validación humana TUI, la actualización de docs, y el criterio de cierre de 5B.

- [ ] **Step 1: Demostrar la validación humana con un escenario provocado**

Run (una alerta cuyo activo no está en hallazgos → postura None → confianza 0.5 → veta → requiere_humano):
```bash
python3 - <<'PY'
import json
from prototipo import lazo, catalogo, perfil
CAT = catalogo.cargar_catalogo("prototipo/catalogo.yml")
P = perfil.cargar("prototipo/perfiles/empresarial.yml")
H = json.load(open("prototipo/tests/fixtures/hallazgos.json"))
alerta = {"id_alerta":"prov","timestamp":"2026-08-31T00:00:00Z","activo":"nodo-sin-postura",
          "servicio":"ssh","familia":"acceso_credenciales","origen_ip":"192.168.1.10",
          "mitre":["T1110"],"regla_id":"5760","nivel_wazuh":5}
# ejecutor falso; validación humana simulada: aprobar
r = lazo.procesar_lazo(alerta, H, P, "empresarial", CAT,
                       lambda ip,c: (1,"") if "grep" in c else (0,""),
                       "prov", "2026-08-31T00:00:00Z", leer=lambda _: "aprobar")
print("requiere_humano:", r["requiere_humano"], "| veredicto:", r["veredicto_humano"],
      "| ejecuto:", r["ejecucion"] is not None)
PY
```
Expected: `requiere_humano: True | veredicto: aprobar | ejecuto: True` — la orden se retuvo, la validación la aprobó, y entonces se ejecutó.

- [ ] **Step 2: Verificar el criterio de cierre de 5B**

Run:
```bash
python3 -m unittest discover -s prototipo/tests 2>&1 | tail -2
```
Expected: OK. Confirma también que las trazas del lazo (Task 6) reunían decisión + orden + ejecución + verificación.

- [ ] **Step 3: Actualizar `prototipo/README.md`**

Añade una sección **5B — el lazo en vivo**: el conector (orden como frontera de dato, idempotencia verificar-antes-de-actuar, ejecutor inyectable), la validación humana por terminal, la verificación, y el orquestador `lazo.py` con su CLI (`--auto` vs vivo). Documenta HONESTAMENTE: el conector actúa solo sobre `objetivo-vuln` (único con sshd); `msfadmin`+`sudo` es sustituto de la clave de servicio; la validación humana se demuestra con escenario provocado porque el baseline sobre datos reales casi nunca la dispara. Enlaza a la spec de 5B.

- [ ] **Step 4: Actualizar el README de la Fase 5**

En `documentacion/05-fase5-implementacion-del-prototipo/README.md`, marca **5B como hecho** (conector SSH + validación humana + verificación, lazo en vivo demostrado), enlazando a `prototipo/`. Deja **5C** (ML) como lo único pendiente de la Fase 5. Nota que el lazo se demostró sobre `objetivo-vuln` con `BLOQUEAR_IP`.

- [ ] **Step 5: Commit**

```bash
git add prototipo/README.md documentacion/05-fase5-implementacion-del-prototipo/README.md
git commit -m "Cerrar la Fase 5B: lazo en vivo demostrado y documentado

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas de ejecución

- **Tasks 1–5 son Python puro** con ejecutor/input falsos; no necesitan el laboratorio.
- **Tasks 6–7 tocan el laboratorio** (ejecución en vivo). Necesitan `sh lab/lab.sh up` con el plano de datos OK y `sshpass` en el contenedor del auditor.
- **Ejecutar desde la raíz del repo.** Batería completa: `python3 -m unittest discover -s prototipo/tests`.
- **Dejar el laboratorio limpio:** cada ejecución en vivo que aplique una regla `iptables` debe revertirla (`-D` o `iptables -F`), como indican los pasos.
