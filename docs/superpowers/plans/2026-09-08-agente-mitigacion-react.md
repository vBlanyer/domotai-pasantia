# Agente de Mitigación (ReAct + Tool Calling acotado) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un módulo `prototipo/agente_mitigacion.py` donde el LLM (agente ReAct) **determina la estrategia de mitigación y escala de dispositivo** (host → firewall) reaccionando a los errores, pero **elige acciones de un catálogo cerrado** (no redacta shell): el código renderiza el comando exacto, valida, exige aprobación humana y ejecuta de forma reversible.

**Architecture:** Bucle ReAct (`Thought → Action(JSON) → Observation`) sobre tres herramientas de código. El agente **solo elige** `(herramienta, dispositivo, accion_lógica, ip)`; el comando lo compone el código desde `catalogo.yml` (RF-15 intacto). Toda la ejecución peligrosa reutiliza `conector.ejecutar_orden` (verificar-antes/aplicar/verificar-después, idempotencia, `_params_seguros`). Si el agente falla o entra en bucle, **degrada** al motor determinista existente (`politica.proponer` + `perfil.filtrar`), como hace hoy el justificador LLM (RNF-09).

**Tech Stack:** Python 3 (probado en 3.14) **solo stdlib** (`json`, `re`, `unittest`) + PyYAML. Sin `pip`/`venv`/`pytest`. Tests con `python3 -m unittest`. LLM = subprocess al 1B local (inyectable; en tests, un generador falso guionizado).

**Spec:** Mensajes del usuario (2026-09-08): agente ReAct/Tool-Calling que decide y escala; herramientas `ejecutar_comando`/`consultar_topologia`/`verificar_mitigacion`; salvaguardas en código (validador RF-19 + contraorden RF-18); escenario host-caído→firewall; invocable desde demo o `stream.py`. **Variante acotada (A) elegida**: el LLM elige acción lógica + dispositivo, el código renderiza el comando. **Decisión de gobernanza = bandera de tiempo de ejecución** `autonomo` (default `False` = aprobación humana por paso, RF-08; `True` = autónomo).

## Global Constraints

- **Solo stdlib + PyYAML.** Sin `pip`/`venv`/`pytest`. Tests: `python3 -m unittest`.
- **RF-15 (catálogo cerrado):** el agente NO redacta comandos; elige de un conjunto **enumerado** de acciones lógicas × dispositivos. El comando lo renderiza el código desde `catalogo.yml`.
- **RF-18 (reversibilidad):** cada acción ejecutada registra su `reversion_cmd` del catálogo en el plan.
- **RF-19 (no cortar gestión):** un validador de código veta cualquier comando que toque `ip_gestion` o traiga patrones destructivos/encadenados. Es la **última** línea; el comando ya viene renderizado y seguro.
- **RF-08 (lazo humano):** con `autonomo=False` (default), cada acción **mutante** pide aprobación (`leer`/`escribir` inyectables); las herramientas *read-only* no piden nada.
- **RNF-09 (degradación):** si el agente no produce una acción válida en `max_pasos`, se cae al motor determinista y se marca `degradado=True`.
- **Cero regresión** en `prototipo/tests` (127+), `lab/dataset/tests` (33), `evaluacion/tests` (22).
- **Aditivo:** no se renombra ni se altera el comportamiento de `catalogo.yml`, `conector.py`, `perfil.py`, `triaje.py`, `lazo.py`, `traza.py` existentes. Solo se **añaden** entradas de catálogo, claves de perfil y un módulo nuevo.
- **Commits** terminan con `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

- **Create `prototipo/agente_mitigacion.py`** — el agente: `resolver_topologia`, `validar_comando`, `parsear_accion`, las tres herramientas, `bucle_react`, `degradar`, `construir_prompt_sistema`. Sin lógica de red propia fuera de las herramientas.
- **Create `prototipo/tests/test_agente_mitigacion.py`** — TDD con generador guionizado + ejecutor falso (host caído / firewall ok) + `leer` inyectado.
- **Modify `prototipo/catalogo.yml`** — añadir `BLOQUEAR_IP_FIREWALL` (cadena `FORWARD`, impacto `alcanza_servicio`); `BLOQUEAR_IP` (host, `INPUT`) se deja igual.
- **Modify `prototipo/perfiles/empresarial.yml`** — añadir `topologia:` (roles/IPs de nodo) e `ip_gestion:`.
- **Create `lab/scripts/demo-agente-escalado.py`** — demo del escalado host→firewall (ejecutores simulados por defecto; nota para lab real).
- **Modify `COMO-PROBAR.md` y `prototipo/README.md`** — documentar el agente y la demo.

---

## Task 1: Datos de topología y catálogo por dispositivo + `resolver_topologia`

Los cimientos de datos: el perfil declara la topología (qué nodo es host víctima, cuál firewall) y la IP de gestión a proteger; el catálogo gana la acción de firewall.

**Files:**
- Modify: `prototipo/catalogo.yml`
- Modify: `prototipo/perfiles/empresarial.yml`
- Create: `prototipo/agente_mitigacion.py`
- Test: `prototipo/tests/test_agente_mitigacion.py`

**Interfaces:**
- Produces: `resolver_topologia(perfil) -> dict` con `{ "<dispositivo>": {"rol": str, "ip": str, ...}, ..., "ip_gestion": str|None }`.

- [ ] **Step 1: Write the failing test**

Crea `prototipo/tests/test_agente_mitigacion.py`:

```python
import json, os, unittest, yaml
from prototipo import agente_mitigacion as ag, catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))

class TestTopologia(unittest.TestCase):
    def test_resolver_topologia_expone_roles_e_ip_gestion(self):
        perfil = {"topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                                "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
                  "ip_gestion": "192.168.1.100"}
        topo = ag.resolver_topologia(perfil)
        self.assertEqual(topo["objetivo-vuln"]["rol"], "host_victima")
        self.assertEqual(topo["gateway"]["ip"], "192.168.1.1")
        self.assertEqual(topo["ip_gestion"], "192.168.1.100")

    def test_catalogo_tiene_accion_de_firewall(self):
        self.assertIn("BLOQUEAR_IP_FIREWALL", CAT)
        self.assertIn("FORWARD", CAT["BLOQUEAR_IP_FIREWALL"]["comando"])
        self.assertEqual(CAT["BLOQUEAR_IP_FIREWALL"]["impacto"], "alcanza_servicio")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestTopologia -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prototipo.agente_mitigacion'`.

- [ ] **Step 3: Write minimal implementation**

Añade a `prototipo/catalogo.yml` (tras `BLOQUEAR_IP`):

```yaml
BLOQUEAR_IP_FIREWALL: { categoria: contencion, impacto: alcanza_servicio, reversion: definida, comando: "iptables -A FORWARD -s {ip} -j DROP", reversion_cmd: "iptables -D FORWARD -s {ip} -j DROP", verificacion: "iptables -L FORWARD -n | grep {ip}" }
```

Añade a `prototipo/perfiles/empresarial.yml` (nivel superior):

```yaml
topologia:
  objetivo-vuln: { rol: host_victima, ip: 192.168.1.30, gateway: gateway }
  gateway:       { rol: firewall_perimetral, ip: 192.168.1.1 }
ip_gestion: 192.168.1.100
```

Crea `prototipo/agente_mitigacion.py`:

```python
"""Agente de mitigación (ReAct + Tool Calling acotado). El LLM decide la estrategia y escala de
dispositivo eligiendo acciones de un catálogo CERRADO; el código renderiza el comando, lo valida,
pide aprobación humana y lo ejecuta de forma reversible reutilizando conector.ejecutar_orden.
"""
import json, re
from prototipo import conector, politica

def resolver_topologia(perfil):
    topo = dict(perfil.get("topologia", {}) or {})
    topo["ip_gestion"] = perfil.get("ip_gestion")
    return topo
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestTopologia -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/catalogo.yml prototipo/perfiles/empresarial.yml prototipo/agente_mitigacion.py prototipo/tests/test_agente_mitigacion.py
git commit -m "feat(agente): topologia en perfil + accion de firewall en catalogo"
```

---

## Task 2: Validador de comandos (RF-19 + destructivos)

La salvaguarda de código que veta lo peligroso, **independiente del LLM**.

**Files:**
- Modify: `prototipo/agente_mitigacion.py`
- Test: `prototipo/tests/test_agente_mitigacion.py`

**Interfaces:**
- Produces: `validar_comando(comando, ip_gestion) -> (ok: bool, motivo: str)`.

- [ ] **Step 1: Write the failing test**

```python
class TestValidador(unittest.TestCase):
    def test_veta_plano_de_gestion(self):
        ok, motivo = ag.validar_comando("iptables -A INPUT -s 192.168.1.100 -j DROP", "192.168.1.100")
        self.assertFalse(ok); self.assertIn("gestion", motivo)

    def test_veta_destructivo_y_encadenado(self):
        self.assertFalse(ag.validar_comando("iptables -F", None)[0])
        self.assertFalse(ag.validar_comando("reboot", None)[0])
        self.assertFalse(ag.validar_comando("ls; rm -rf /", None)[0])

    def test_permite_comando_renderizado_del_catalogo(self):
        ok, _ = ag.validar_comando("iptables -A FORWARD -s 192.168.1.10 -j DROP", "192.168.1.100")
        self.assertTrue(ok)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestValidador -v`
Expected: FAIL — `module 'prototipo.agente_mitigacion' has no attribute 'validar_comando'`.

- [ ] **Step 3: Write minimal implementation**

Añade a `prototipo/agente_mitigacion.py`:

```python
_DESTRUCTIVO = re.compile(r'(-F|--flush|-X|-Z|\brm\b|\breboot\b|\bshutdown\b|;|\||&&|`|\$\()')

def validar_comando(comando, ip_gestion):
    """Última línea de defensa (RF-19): veta gestión y patrones destructivos/encadenados."""
    if ip_gestion and ip_gestion in comando:
        return (False, "el comando afecta al plano de gestion (RF-19)")
    if _DESTRUCTIVO.search(comando):
        return (False, "patron destructivo o encadenamiento no permitido")
    return (True, "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestValidador -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/agente_mitigacion.py prototipo/tests/test_agente_mitigacion.py
git commit -m "feat(agente): validador de comandos (RF-19 + destructivos)"
```

---

## Task 3: Parser de la acción del LLM

Extrae la `Action`/`Final` (JSON) de la salida del modelo, tolerante al ruido del 1B.

**Files:**
- Modify: `prototipo/agente_mitigacion.py`
- Test: `prototipo/tests/test_agente_mitigacion.py`

**Interfaces:**
- Produces: `parsear_accion(texto) -> dict|None`. El dict lleva `kind` (`"action"`|`"final"`) más las claves del JSON (`tool`, `args`, o `resultado`/`dispositivo_ejecutor`).

- [ ] **Step 1: Write the failing test**

```python
class TestParser(unittest.TestCase):
    def test_extrae_action_json(self):
        t = 'Thought: intento el host\nAction: {"tool": "ejecutar_comando", "args": {"dispositivo": "objetivo-vuln", "accion": "bloquear_ip"}}'
        a = ag.parsear_accion(t)
        self.assertEqual(a["kind"], "action")
        self.assertEqual(a["tool"], "ejecutar_comando")
        self.assertEqual(a["args"]["dispositivo"], "objetivo-vuln")

    def test_extrae_final(self):
        a = ag.parsear_accion('Final: {"resultado": "mitigado", "dispositivo_ejecutor": "gateway"}')
        self.assertEqual(a["kind"], "final")
        self.assertEqual(a["resultado"], "mitigado")

    def test_ruido_sin_json_devuelve_none(self):
        self.assertIsNone(ag.parsear_accion("no hay ninguna accion aqui"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestParser -v`
Expected: FAIL — `has no attribute 'parsear_accion'`.

- [ ] **Step 3: Write minimal implementation**

```python
_ACCION_RE = re.compile(r'(Action|Final)\s*:\s*(\{.*)', re.DOTALL)

def _primer_json(s):
    inicio = s.find("{")
    if inicio < 0:
        return None
    prof = 0
    for i in range(inicio, len(s)):
        if s[i] == "{":
            prof += 1
        elif s[i] == "}":
            prof -= 1
            if prof == 0:
                try:
                    return json.loads(s[inicio:i + 1])
                except json.JSONDecodeError:
                    return None
    return None

def parsear_accion(texto):
    m = _ACCION_RE.search(texto or "")
    if not m:
        return None
    obj = _primer_json(m.group(2))
    if obj is None:
        return None
    return {"kind": "final" if m.group(1).lower() == "final" else "action", **obj}

def _extraer_thought(texto):
    m = re.search(r'Thought\s*:\s*(.+)', texto or "")
    return m.group(1).strip() if m else ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestParser -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/agente_mitigacion.py prototipo/tests/test_agente_mitigacion.py
git commit -m "feat(agente): parser tolerante de Action/Final del LLM"
```

---

## Task 4: Herramientas read-only (`consultar_topologia`, `verificar_mitigacion`)

Las herramientas que **no** mutan estado: no piden aprobación humana.

**Files:**
- Modify: `prototipo/agente_mitigacion.py`
- Test: `prototipo/tests/test_agente_mitigacion.py`

**Interfaces:**
- Consumes: `resolver_topologia` (Task 1); `catalogo` (dict de `cargar_catalogo`).
- Produces:
  - `_ACCION_POR_ROL` (dict) mapea `(accion_logica, rol)` → `accion_id` del catálogo.
  - `herramienta_consultar_topologia(topo) -> str`.
  - `herramienta_verificar_mitigacion(topo, catalogo, ejecutor, dispositivo, ip) -> str` (`"bloqueado"`|`"activo"`|`"Error: ..."`). `ejecutor` es `(nodo_ip, comando) -> (rc, salida)`.

- [ ] **Step 1: Write the failing test**

```python
class TestHerramientasReadOnly(unittest.TestCase):
    def test_consultar_topologia_lista_roles(self):
        topo = ag.resolver_topologia(y_perfil())
        obs = ag.herramienta_consultar_topologia(topo)
        self.assertIn("objetivo-vuln=host_victima", obs)
        self.assertIn("gateway=firewall_perimetral", obs)

    def test_verificar_bloqueado_segun_ejecutor(self):
        topo = ag.resolver_topologia(y_perfil())
        ej = lambda ip, cmd: (0, "DROP 192.168.1.10")   # verificacion rc0 -> bloqueado
        self.assertEqual(ag.herramienta_verificar_mitigacion(topo, CAT, ej, "gateway", "192.168.1.10"), "bloqueado")
        ej2 = lambda ip, cmd: (1, "")
        self.assertEqual(ag.herramienta_verificar_mitigacion(topo, CAT, ej2, "gateway", "192.168.1.10"), "activo")
```

Añade el helper al principio del fichero de test (tras los imports):

```python
def y_perfil():
    return {"topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                          "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
            "ip_gestion": "192.168.1.100"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestHerramientasReadOnly -v`
Expected: FAIL — `has no attribute 'herramienta_consultar_topologia'`.

- [ ] **Step 3: Write minimal implementation**

```python
_ACCION_POR_ROL = {
    ("bloquear_ip", "host_victima"): "BLOQUEAR_IP",
    ("bloquear_ip", "firewall_perimetral"): "BLOQUEAR_IP_FIREWALL",
}

def herramienta_consultar_topologia(topo):
    dev = {k: v.get("rol") for k, v in topo.items() if isinstance(v, dict) and v.get("rol")}
    return "nodos: " + ", ".join(f"{k}={r}" for k, r in dev.items())

def herramienta_verificar_mitigacion(topo, catalogo, ejecutor, dispositivo, ip):
    nodo = topo.get(dispositivo)
    if not isinstance(nodo, dict):
        return f"Error: dispositivo desconocido '{dispositivo}'"
    accion_id = _ACCION_POR_ROL.get(("bloquear_ip", nodo.get("rol")))
    if accion_id is None:
        return f"Error: sin verificacion para '{dispositivo}'"
    cmd = catalogo[accion_id]["verificacion"].format(ip=ip)
    rc, _ = ejecutor(nodo.get("ip"), cmd)
    return "bloqueado" if rc == 0 else "activo"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestHerramientasReadOnly -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/agente_mitigacion.py prototipo/tests/test_agente_mitigacion.py
git commit -m "feat(agente): herramientas read-only (topologia + verificacion)"
```

---

## Task 5: Herramienta `ejecutar_comando` (validar → aprobar → ejecutar → reversión)

La única herramienta que **muta**: renderiza desde el catálogo, valida (Task 2), pide aprobación humana (salvo `autonomo`), ejecuta con `conector.ejecutar_orden` y registra la contraorden (RF-18).

**Files:**
- Modify: `prototipo/agente_mitigacion.py`
- Test: `prototipo/tests/test_agente_mitigacion.py`

**Interfaces:**
- Consumes: `_ACCION_POR_ROL`, `validar_comando`, `conector.ejecutar_orden(orden, catalogo, ejecutor, timestamp)`.
- Produces: `herramienta_ejecutar_comando(topo, catalogo, ejecutor, dispositivo, accion, ip, ip_gestion, decision_id, timestamp, autonomo, leer, escribir) -> (observacion: str, registro: dict|None)`. `registro` lleva `accion_id` y las banderas `vetado`/`cancelado`/`exito` y `reversion_cmd`.

- [ ] **Step 1: Write the failing test**

```python
class TestEjecutarComando(unittest.TestCase):
    def _args(self, ejecutor, **kw):
        base = dict(topo=ag.resolver_topologia(y_perfil()), catalogo=CAT, ejecutor=ejecutor,
                    dispositivo="gateway", accion="bloquear_ip", ip="192.168.1.10",
                    ip_gestion="192.168.1.100", decision_id="d1", timestamp="t",
                    autonomo=True, leer=lambda *_: "s", escribir=lambda *_: None)
        base.update(kw); return base

    def test_ejecuta_en_firewall_y_registra_reversion(self):
        ej = lambda ip, cmd: (1, "") if "grep" in cmd else (0, "")   # verif-antes: no está; aplicar: ok
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(ej))
        self.assertTrue(obs.startswith("OK"))
        self.assertTrue(reg["exito"])
        self.assertEqual(reg["accion_id"], "BLOQUEAR_IP_FIREWALL")
        self.assertIn("FORWARD", reg["reversion_cmd"])

    def test_host_caido_devuelve_error(self):
        ej = lambda ip, cmd: (255, "connect: Connection refused")
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(ej, dispositivo="objetivo-vuln"))
        self.assertTrue(obs.startswith("Error"))
        self.assertFalse(reg["exito"])

    def test_no_autonomo_pide_aprobacion_y_rechazo_cancela(self):
        ej = lambda ip, cmd: (0, "")
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(ej, autonomo=False, leer=lambda *_: "n"))
        self.assertIn("Cancelado", obs)
        self.assertTrue(reg["cancelado"])

    def test_dispositivo_desconocido(self):
        ej = lambda ip, cmd: (0, "")
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(ej, dispositivo="marte"))
        self.assertTrue(obs.startswith("Error")); self.assertIsNone(reg)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestEjecutarComando -v`
Expected: FAIL — `has no attribute 'herramienta_ejecutar_comando'`.

- [ ] **Step 3: Write minimal implementation**

```python
def _aprobar(dispositivo, nodo_ip, accion_id, ip, leer, escribir):
    escribir(f"── Validación humana ── {accion_id} en {dispositivo} ({nodo_ip}) contra {ip}")
    return leer("¿aprobar la ejecución? [s/N] ").strip().lower().startswith("s")

def herramienta_ejecutar_comando(topo, catalogo, ejecutor, dispositivo, accion, ip, ip_gestion,
                                 decision_id, timestamp, autonomo, leer, escribir):
    nodo = topo.get(dispositivo)
    if not isinstance(nodo, dict):
        return (f"Error: dispositivo desconocido '{dispositivo}'", None)
    accion_id = _ACCION_POR_ROL.get((accion, nodo.get("rol")))
    if accion_id is None or accion_id not in catalogo:
        return (f"Error: accion '{accion}' no valida para el rol '{nodo.get('rol')}'", None)
    comando = catalogo[accion_id]["comando"].format(ip=ip)
    ok, motivo = validar_comando(comando, ip_gestion)
    reversion_cmd = catalogo[accion_id].get("reversion_cmd", "").format(ip=ip)
    if not ok:
        return (f"Error: {motivo}", {"accion_id": accion_id, "vetado": True, "reversion_cmd": reversion_cmd})
    if not autonomo and not _aprobar(dispositivo, nodo.get("ip"), accion_id, ip, leer, escribir):
        return (f"Cancelado por el humano: {accion_id} en {dispositivo}",
                {"accion_id": accion_id, "cancelado": True, "reversion_cmd": reversion_cmd})
    orden = {"decision_id": decision_id, "accion_id": accion_id, "nodo_objetivo": dispositivo,
             "nodo_ip": nodo.get("ip"), "params": {"ip": ip}, "impacto": catalogo[accion_id]["impacto"]}
    res = conector.ejecutar_orden(orden, catalogo, ejecutor, timestamp)
    if res.get("exito"):
        return (f"OK: {accion_id} aplicada en {dispositivo} (rc={res.get('codigo_salida')})",
                {"accion_id": accion_id, "exito": True, "reversion_cmd": reversion_cmd, "resultado": res})
    return (f"Error: fallo en {dispositivo} (rc={res.get('codigo_salida')})",
            {"accion_id": accion_id, "exito": False, "reversion_cmd": reversion_cmd, "resultado": res})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestEjecutarComando -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/agente_mitigacion.py prototipo/tests/test_agente_mitigacion.py
git commit -m "feat(agente): herramienta ejecutar_comando (validar/aprobar/ejecutar/revertir)"
```

---

## Task 6: `bucle_react` + prompt + degradación (el agente completo)

Ata las piezas: construye el prompt, itera Thought→Action→Observation, despacha herramientas, escala al reaccionar a errores, y degrada si no hay acción válida. Incluye **el test estrella de escalado**.

**Files:**
- Modify: `prototipo/agente_mitigacion.py`
- Test: `prototipo/tests/test_agente_mitigacion.py`

**Interfaces:**
- Consumes: todas las herramientas (Tasks 4-5), `parsear_accion`/`_extraer_thought` (Task 3), `politica.proponer(clase, alerta)`.
- Produces:
  - `construir_prompt_sistema(alerta, topo) -> str`.
  - `bucle_react(alerta, clase, perfil, catalogo, ejecutor, generador, leer=input, autonomo=False, max_pasos=6, escribir=print, timestamp="") -> dict` (plan: `pasos`, `reversiones`, `dispositivo_ejecutor`, `escalado`, `resultado`, `degradado`; y `accion_determinista` solo si degradado).
  - `degradar(alerta, clase, pasos) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
class GeneradorGuion:
    """LLM falso: emite pasos ReAct prefijados, ignora el prompt."""
    def __init__(self, pasos): self.pasos, self.i = list(pasos), 0
    def __call__(self, prompt):
        if self.i >= len(self.pasos): return "ruido sin accion"
        p = self.pasos[self.i]; self.i += 1; return p

def ejecutor_escalado(nodo_ip, cmd):
    # host víctima (.30) caído; firewall (.1) responde
    if nodo_ip == "192.168.1.30":
        return (255, "connect to host 192.168.1.30 port 22: Connection refused")
    return (1, "") if "grep" in cmd else (0, "")   # firewall: verif-antes no está, aplicar ok

class TestBucleReact(unittest.TestCase):
    def _alerta(self):
        return {"id_alerta": "a1", "origen_ip": "192.168.1.10", "activo": "objetivo-vuln",
                "servicio": "ssh", "regla_id": "5760", "mitre": ["T1110.001"]}

    def test_escalado_host_caido_a_firewall(self):
        guion = [
            'Thought: intento el bloqueo local en el host victima.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"objetivo-vuln","accion":"bloquear_ip"}}',
            'Thought: el host no responde; escalo al firewall perimetral.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
            'Thought: verifico el corte en el firewall.\nAction: {"tool":"verificar_mitigacion","args":{"dispositivo":"gateway"}}',
            'Final: {"resultado":"mitigado","dispositivo_ejecutor":"gateway"}',
        ]
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              ejecutor_escalado, GeneradorGuion(guion),
                              leer=lambda *_: "s", autonomo=True, escribir=lambda *_: None)
        self.assertTrue(plan["escalado"])
        self.assertEqual(plan["dispositivo_ejecutor"], "gateway")
        self.assertEqual(plan["resultado"], "mitigado")
        self.assertFalse(plan["degradado"])
        self.assertTrue(any("FORWARD" in r for r in plan["reversiones"]))   # RF-18

    def test_rechazo_humano_cancela(self):
        guion = ['Action: {"tool":"ejecutar_comando","args":{"dispositivo":"objetivo-vuln","accion":"bloquear_ip"}}']
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              lambda ip, c: (0, ""), GeneradorGuion(guion),
                              leer=lambda *_: "n", autonomo=False, escribir=lambda *_: None)
        self.assertEqual(plan["resultado"], "cancelado_por_humano")

    def test_degrada_si_no_hay_accion_valida(self):
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              lambda ip, c: (0, ""), GeneradorGuion(["basura", "mas basura"]),
                              leer=lambda *_: "s", autonomo=True, escribir=lambda *_: None, max_pasos=2)
        self.assertTrue(plan["degradado"])
        self.assertEqual(plan["resultado"], "degradado")
        self.assertEqual(plan["accion_determinista"], "BLOQUEAR_IP")   # politica.proponer

    def test_gestion_vetada_por_codigo_y_continua(self):
        # el guion intenta tocar la IP de gestion via una accion sobre el firewall cuyo render la incluiria;
        # aquí forzamos el veto usando ip_gestion == IP atacante para probar el camino de veto en el bucle.
        alerta = dict(self._alerta()); alerta["origen_ip"] = "192.168.1.100"   # = ip_gestion
        guion = ['Action: {"tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
                 'Final: {"resultado":"fallido"}']
        plan = ag.bucle_react(alerta, "vp_intento_acceso", y_perfil(), CAT,
                              lambda ip, c: (0, ""), GeneradorGuion(guion),
                              leer=lambda *_: "s", autonomo=True, escribir=lambda *_: None)
        self.assertIsNone(plan["dispositivo_ejecutor"])                 # nada se ejecutó
        self.assertTrue(any(p.get("observacion", "").startswith("Error") for p in plan["pasos"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion.TestBucleReact -v`
Expected: FAIL — `has no attribute 'bucle_react'`.

- [ ] **Step 3: Write minimal implementation**

```python
def construir_prompt_sistema(alerta, topo):
    nodos = ", ".join(f"{k}({v.get('rol')})" for k, v in topo.items() if isinstance(v, dict) and v.get("rol"))
    return (
        "Eres un agente de respuesta a incidentes. Objetivo: cortar el trafico del atacante "
        f"{alerta.get('origen_ip')} hacia la victima {alerta.get('activo')}. NO escribes comandos de "
        "shell; SOLO invocas herramientas.\n"
        "Herramientas (unica salida permitida por paso):\n"
        "  consultar_topologia()                     -> nodos y su rol\n"
        "  ejecutar_comando(dispositivo, accion)     -> accion en {\"bloquear_ip\"}\n"
        "  verificar_mitigacion(dispositivo)         -> bloqueado|activo\n"
        f"Nodos disponibles: {nodos}.\n"
        "Reglas: una accion por paso; solo estas herramientas; solo accion 'bloquear_ip'; nunca toques "
        "el plano de gestion. Si una herramienta devuelve Error, RAZONA y escala a otro dispositivo. "
        "Cuando el trafico este bloqueado, responde con Final.\n"
        "Formato EXACTO por paso:\nThought: <una frase>\nAction: {\"tool\": \"...\", \"args\": {...}}\n"
        "  (o al terminar)\nFinal: {\"resultado\": \"mitigado|fallido\", \"dispositivo_ejecutor\": \"<nodo>\"}\n"
    )

def _plan(pasos, reversiones, dispositivo_ejecutor, tocados, resultado, degradado, extra=None):
    p = {"pasos": pasos, "reversiones": reversiones, "dispositivo_ejecutor": dispositivo_ejecutor,
         "escalado": len(set(tocados)) > 1, "resultado": resultado, "degradado": degradado}
    if extra:
        p.update(extra)
    return p

def degradar(alerta, clase, pasos):
    accion, _params = politica.proponer(clase, alerta)
    return _plan(pasos, [], None, [], "degradado", True, {"accion_determinista": accion})

def bucle_react(alerta, clase, perfil, catalogo, ejecutor, generador, leer=input, autonomo=False,
                max_pasos=6, escribir=print, timestamp=""):
    topo = resolver_topologia(perfil)
    ip_gestion, ip_atacante = topo.get("ip_gestion"), alerta.get("origen_ip")
    prompt = construir_prompt_sistema(alerta, topo)
    pasos, reversiones, tocados, dispositivo_ejecutor = [], [], [], None
    for _ in range(max_pasos):
        salida = generador(prompt) or ""
        acc = parsear_accion(salida)
        thought = _extraer_thought(salida)
        if acc is None:
            pasos.append({"tipo": "invalido", "bruto": salida[:200]})
            prompt += salida + "\nObservation: Error: formato invalido; usa Action con JSON.\n"
            continue
        if acc["kind"] == "final":
            pasos.append({"tipo": "final", "thought": thought, "datos": acc})
            resultado = acc.get("resultado", "mitigado" if dispositivo_ejecutor else "fallido")
            return _plan(pasos, reversiones, dispositivo_ejecutor, tocados, resultado, False)
        tool, args = acc.get("tool"), acc.get("args", {}) or {}
        if tool == "consultar_topologia":
            obs = herramienta_consultar_topologia(topo)
        elif tool == "verificar_mitigacion":
            obs = herramienta_verificar_mitigacion(topo, catalogo, ejecutor, args.get("dispositivo"), ip_atacante)
        elif tool == "ejecutar_comando":
            disp = args.get("dispositivo")
            obs, reg = herramienta_ejecutar_comando(topo, catalogo, ejecutor, disp, args.get("accion"),
                        ip_atacante, ip_gestion, alerta.get("id_alerta", ""), timestamp, autonomo, leer, escribir)
            if reg is not None:
                tocados.append(disp)
                if reg.get("reversion_cmd"):
                    reversiones.append(reg["reversion_cmd"])
                if reg.get("cancelado"):
                    pasos.append({"tipo": "accion", "thought": thought, "tool": tool, "args": args, "observacion": obs})
                    return _plan(pasos, reversiones, dispositivo_ejecutor, tocados, "cancelado_por_humano", False)
                if reg.get("exito"):
                    dispositivo_ejecutor = disp
        else:
            obs = f"Error: herramienta desconocida '{tool}'"
        pasos.append({"tipo": "accion" if tool == "ejecutar_comando" else "lectura",
                      "thought": thought, "tool": tool, "args": args, "observacion": obs})
        prompt += salida + f"\nObservation: {obs}\n"
    if dispositivo_ejecutor:
        return _plan(pasos, reversiones, dispositivo_ejecutor, tocados, "mitigado", False)
    return degradar(alerta, clase, pasos)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest prototipo.tests.test_agente_mitigacion -v`
Expected: PASS (toda la suite del agente).

- [ ] **Step 5: Regression + commit**

```bash
python3 -m unittest discover -s prototipo/tests && python3 -m unittest discover -s lab/dataset/tests && python3 -m unittest discover -s evaluacion/tests
git add prototipo/agente_mitigacion.py prototipo/tests/test_agente_mitigacion.py
git commit -m "feat(agente): bucle ReAct con escalado host->firewall y degradacion determinista"
```

---

## Task 7: Demo de escalado + documentación

Una demo ejecutable del escalado (ejecutores simulados por defecto, honesta con las limitaciones del lab) y la documentación de uso.

**Files:**
- Create: `lab/scripts/demo-agente-escalado.py`
- Modify: `COMO-PROBAR.md`
- Modify: `prototipo/README.md`

- [ ] **Step 1: Crear la demo**

`lab/scripts/demo-agente-escalado.py`:

```python
"""Demo del agente de mitigación (ReAct + Tool Calling acotado): escalado host->firewall.
Por defecto usa ejecutores SIMULADOS (host caído / firewall ok), que reproducen el escenario sin
necesitar SSH en el firewall del lab. Con --lab usa el conector SSH real (requiere el firewall
'borde' provisionado con sshd + credenciales, no incluido por defecto).

Uso:  python3 lab/scripts/demo-agente-escalado.py [--lab] [--autonomo] [--con-llm]
"""
import json, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from prototipo import agente_mitigacion as ag, catalogo as catm, perfil as perfilm, conector

def ejecutor_simulado(nodo_ip, cmd):
    if nodo_ip == "192.168.1.30":                       # host víctima: caído
        return (255, "connect to host 192.168.1.30 port 22: Connection refused")
    return (1, "") if "grep" in cmd else (0, "(simulado)")   # firewall: aplica

def generador_guion(_prompt, _estado={"i": 0}):
    pasos = [
        'Thought: intento el bloqueo local en el host victima.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"objetivo-vuln","accion":"bloquear_ip"}}',
        'Thought: el host no responde; escalo al firewall perimetral.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
        'Thought: verifico el corte en el firewall.\nAction: {"tool":"verificar_mitigacion","args":{"dispositivo":"gateway"}}',
        'Final: {"resultado":"mitigado","dispositivo_ejecutor":"gateway"}']
    i = _estado["i"]; _estado["i"] = min(i + 1, len(pasos) - 1); return pasos[i]

def main():
    lab, autonomo, con_llm = "--lab" in sys.argv, "--autonomo" in sys.argv, "--con-llm" in sys.argv
    perfil = perfilm.cargar(os.path.join(REPO, "prototipo/perfiles/empresarial.yml"))
    catalogo = catm.cargar_catalogo(os.path.join(REPO, "prototipo/catalogo.yml"))
    ejecutor = conector.ejecutor_ssh_lab if lab else ejecutor_simulado
    if con_llm:
        from prototipo import justificador_llm
        generador = justificador_llm.generador_llama          # el 1B real (puede degradar)
    else:
        generador = generador_guion
    alerta = {"id_alerta": "demo1", "origen_ip": "192.168.1.10", "activo": "objetivo-vuln",
              "servicio": "ssh", "regla_id": "5760", "mitre": ["T1110.001"]}
    print("== DEMO Agente de Mitigación — escalado host -> firewall ==")
    plan = ag.bucle_react(alerta, "vp_intento_acceso", perfil, catalogo, ejecutor, generador,
                          autonomo=autonomo, timestamp="demo")
    for p in plan["pasos"]:
        if p.get("thought"): print("  Thought:", p["thought"])
        if p.get("observacion"): print("  Observation:", p["observacion"])
    print(f"\n  Resultado: {plan['resultado']} · dispositivo ejecutor: {plan['dispositivo_ejecutor']} · "
          f"escalado: {plan['escalado']} · degradado: {plan['degradado']}")
    print(f"  Reversiones registradas (RF-18): {plan['reversiones']}")
    print("\n" + json.dumps(plan, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Ejecutar la demo (verificación manual)**

Run: `python3 lab/scripts/demo-agente-escalado.py`
Expected: imenta el intento en el host (Error: Connection refused), el escalado al firewall (OK), la verificación (`bloqueado`), `resultado: mitigado`, `dispositivo ejecutor: gateway`, `escalado: True`, y las reversiones con `FORWARD`.

- [ ] **Step 3: Documentar**

En `COMO-PROBAR.md`, añade una sección "Nivel 3.ter · Agente de mitigación (escalado multi-nodo)" que explique: qué demuestra (el LLM decide y escala host→firewall sobre catálogo cerrado), el comando `python3 lab/scripts/demo-agente-escalado.py [--lab] [--autonomo] [--con-llm]`, y que por defecto los ejecutores son simulados (el firewall `borde` del lab no trae sshd por defecto).

En `prototipo/README.md`, añade una sección "14. Agente de mitigación (ReAct + Tool Calling acotado)" que describa: el LLM elige `(herramienta, dispositivo, accion_logica)`, el código renderiza el comando del catálogo (RF-15), valida (RF-19), pide aprobación (RF-08, salvo `autonomo`), ejecuta reversible (RF-18) reutilizando `conector.ejecutar_orden`, y degrada al motor determinista si falla (RNF-09).

- [ ] **Step 4: Commit**

```bash
git add lab/scripts/demo-agente-escalado.py COMO-PROBAR.md prototipo/README.md
git commit -m "feat(agente): demo de escalado host->firewall + documentacion"
```

---

## Verificación (de punta a punta)

1. **Baterías completas** (cero regresión): `prototipo/tests` (con la suite nueva del agente), `lab/dataset/tests`, `evaluacion/tests` → verde.
2. **Escenario estrella** (unit): `test_escalado_host_caido_a_firewall` demuestra host-caído→firewall con `dispositivo_ejecutor == "gateway"`, `escalado == True` y la reversión `FORWARD` (RF-18) — sin lab ni LLM.
3. **Salvaguardas de código**: `TestValidador` + `test_gestion_vetada_por_codigo_y_continua` demuestran que el veto (RF-19) lo hace el código, no el modelo.
4. **Gobernanza**: `test_no_autonomo_pide_aprobacion_y_rechazo_cancela` + `test_rechazo_humano_cancela` demuestran RF-08 por paso; `autonomo=True` lo salta.
5. **Degradación**: `test_degrada_si_no_hay_accion_valida` demuestra la red de seguridad RNF-09.
6. **Demo**: `python3 lab/scripts/demo-agente-escalado.py` narra el escalado de punta a punta.

---

## Self-Review (hecho)

- **Cobertura de la spec:** agente decide/escala → Task 6 (`bucle_react`, test de escalado). Tres herramientas → Tasks 4-5. Validador RF-19 → Task 2. Contraorden RF-18 → Task 5 (`reversion_cmd` en el registro). Catálogo cerrado A/RF-15 → Task 1 (entradas enumeradas) + Task 5 (`_ACCION_POR_ROL`, sin shell libre). Lazo humano RF-08 → Task 5 (`autonomo`/`_aprobar`). Escenario host-caído→firewall → Task 6 test + Task 7 demo. Invocable desde demo/stream → Task 7 (`bucle_react` es una función pura inyectable; la demo la invoca, y la nota de stream documenta el hook). TDD con generador mockeado → todas. Solo stdlib+PyYAML, cero regresión → Global Constraints + Verificación.
- **Sin placeholders:** cada step trae código real.
- **Consistencia de tipos:** `resolver_topologia -> dict` (Task 1) consumido por todas; `validar_comando -> (ok, motivo)` (Task 2) usado en Task 5; `parsear_accion -> dict|None` con `kind` (Task 3) usado en Task 6; `herramienta_ejecutar_comando -> (obs, registro)` (Task 5) consumido por `bucle_react` (Task 6); `_ACCION_POR_ROL` definido en Task 4, reusado en Task 5. `conector.ejecutar_orden(orden, catalogo, ejecutor, timestamp)` y la forma de `orden` coinciden con `prototipo/conector.py` y `prototipo/orden.py`.
- **Decisión de gobernanza** = bandera `autonomo` (no bifurca el diseño). **Integración con `stream.py`** se documenta como hook (llamar `bucle_react` en el paso de mitigación) para no acoplar dos lazos humanos en este plan; la demo cubre la invocación real.
- **Honestidad del lab:** el firewall `borde` no trae sshd por defecto, así que la demo usa ejecutores **simulados** salvo `--lab`; se declara, no se oculta.
```
