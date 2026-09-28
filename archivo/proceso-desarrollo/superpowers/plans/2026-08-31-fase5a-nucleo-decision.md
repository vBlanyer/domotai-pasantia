# Fase 5A — Núcleo de decisión — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el lazo de decisión del motor de triaje (ingesta → análisis baseline → política → perfil/filtro → traza), offline y sin SSH ni ML, en un paquete `prototipo/`.

**Architecture:** Núcleo Python puro. Reutiliza la ingesta de `lab/dataset/` (normalización y postura). Un clasificador baseline determinista detrás de la interfaz `clasificar`/`justificar`; la política propone una acción del catálogo; el perfil de cliente la filtra (permite/degrada/veta); todo queda en una traza JSONL. No ejecuta acciones (eso es 5B) ni usa modelos (eso es 5C).

**Tech Stack:** Python 3.14 (stdlib: `json`, `unittest`; `pyyaml` del sistema). **Sin pip/venv/pytest** — entorno externally-managed, sin dependencias externas.

**Spec:** [docs/superpowers/specs/2026-08-31-fase5a-nucleo-decision-design.md](../specs/2026-08-31-fase5a-nucleo-decision-design.md)

## Global Constraints

- **Sin dependencias externas.** Solo stdlib + `pyyaml`. Tests con `python3 -m unittest`, nunca pytest. Ejecutar desde la raíz del repo.
- **El baseline no usa información privilegiada.** El clasificador usa familia, postura (del auditor) y nivel de Wazuh; NUNCA la lista de orígenes legítimos ni la etiqueta del dataset (`etiqueta`, `etiqueta_por`, `particion` se ignoran como entrada).
- **RNF-09 — nunca descartar en silencio.** El filtro del perfil devuelve siempre uno de: `permite`, `degrada`, `veta`, o `sin_accion` (cuando no hay acción propuesta).
- **RF-09 — traza reproducible.** Cada decisión registra entrada, clase, confianza, justificación, acción propuesta, impacto, resultado del filtro, acción final, requiere_humano, y versiones. Los timestamps se pasan como parámetro (no se generan dentro).
- **Reutiliza, no reimplementa:** la normalización y la postura vienen de `lab.dataset.esquema` y `lab.dataset.etiquetar` (`postura_de`).
- **Umbral de confianza:** `UMBRAL_CONFIANZA = 0.7`, declarado como constante recalibrable en la Fase 6.
- **UTF-8**; `ensure_ascii=False` al escribir JSON. Commits en español terminados con: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Estructura de ficheros

```
prototipo/
├── __init__.py
├── catalogo.py         carga el catálogo como dato; impacto por acción
├── catalogo.yml        las 14 acciones con impacto, reversión, comando (dato)
├── analisis.py         interfaz clasificar/justificar (baseline) + enriquecer
├── politica.py         clase → acción candidata (regla de decisión)
├── perfil.py           carga el perfil YAML; filtro permite/degrada/veta
├── traza.py            construye el registro de decisión (RF-09)
├── triaje.py           orquestador del lazo + CLI
├── perfiles/
│   ├── residencial.yml
│   └── empresarial.yml
├── ilustrativas.jsonl  alertas ilustrativas para la demo de RNF-14
└── tests/
    ├── __init__.py
    ├── fixtures/
    │   ├── alerta_vp.json       alerta normalizada (fuerza bruta SSH contra objetivo-vuln)
    │   ├── hallazgos.json       postura de ejemplo
    │   └── perfil.yml           perfil de ejemplo
    ├── test_catalogo.py
    ├── test_analisis.py
    ├── test_politica.py
    ├── test_perfil.py
    ├── test_traza.py
    └── test_triaje.py
```

Responsabilidades: cada módulo una sola. `analisis`, `politica`, `perfil` son funciones puras; `triaje` orquesta y hace E/S; `catalogo`/`perfil` cargan datos.

---

## Task 1: Andamiaje del paquete, catálogo como dato y fixtures

**Files:**
- Create: `prototipo/__init__.py`, `prototipo/tests/__init__.py` (vacíos)
- Create: `prototipo/catalogo.yml`
- Create: `prototipo/tests/fixtures/alerta_vp.json`, `hallazgos.json`, `perfil.yml`

**Interfaces:**
- Produces: los datos base que las demás tareas consumen.

- [ ] **Step 1: Crear paquetes vacíos**

```bash
mkdir -p prototipo/tests/fixtures prototipo/perfiles
touch prototipo/__init__.py prototipo/tests/__init__.py
```

- [ ] **Step 2: Crear `prototipo/catalogo.yml`** con las 14 acciones y su impacto (de la revisión de la Fase 4)

```yaml
# Catálogo de acciones como dato. Fuente para máquinas; la narrativa vive en
# documentacion/04-.../catalogo-de-acciones.md. impacto: ninguno|localizado|alcanza_servicio.
OBS_CONEXIONES:  { categoria: observacion, impacto: ninguno, reversion: no_aplica, comando: "ss -tunap", verificacion: "salida capturada" }
OBS_PROCESOS:    { categoria: observacion, impacto: ninguno, reversion: no_aplica, comando: "ps aux", verificacion: "salida capturada" }
OBS_ESCUCHA:     { categoria: observacion, impacto: ninguno, reversion: no_aplica, comando: "ss -lntu", verificacion: "salida capturada" }
OBS_CONFIG:      { categoria: observacion, impacto: ninguno, reversion: no_aplica, comando: "ip addr; ip route", verificacion: "salida capturada" }
OBS_CAPTURA:     { categoria: observacion, impacto: ninguno, reversion: no_aplica, comando: "timeout 10 tcpdump -c 100 -w -", verificacion: "pcap devuelto" }
BLOQUEAR_IP:     { categoria: contencion, impacto: localizado, reversion: definida, comando: "iptables -A INPUT -s {ip} -j DROP", reversion_cmd: "iptables -D INPUT -s {ip} -j DROP", verificacion: "iptables -L -n | grep {ip}" }
BLOQUEAR_PUERTO: { categoria: contencion, impacto: alcanza_servicio, reversion: definida, comando: "iptables -A INPUT -p tcp --dport {puerto} -j DROP", reversion_cmd: "iptables -D INPUT -p tcp --dport {puerto} -j DROP", verificacion: "iptables -L -n" }
AISLAR_NODO:     { categoria: contencion, impacto: alcanza_servicio, reversion: definida, comando: "iptables -A FORWARD -s {ip_nodo} -j DROP", reversion_cmd: "iptables -D FORWARD -s {ip_nodo} -j DROP", verificacion: "iptables -L -n" }
LIMITAR_BANDA:   { categoria: contencion, impacto: alcanza_servicio, reversion: definida, comando: "tc qdisc add dev {if} root tbf rate {rate}", reversion_cmd: "tc qdisc del dev {if} root", verificacion: "tc qdisc show" }
CERRAR_SERVICIO: { categoria: endurecimiento, impacto: alcanza_servicio, reversion: definida, comando: "service {servicio} stop", reversion_cmd: "service {servicio} start", verificacion: "ss -lntu", corta_gestion_si: ssh }
FORZAR_CAMBIO_PASS: { categoria: endurecimiento, impacto: alcanza_servicio, reversion: definida, comando: "passwd -l {usuario}", reversion_cmd: "passwd -u {usuario}", verificacion: "passwd -S {usuario}" }
MATAR_CONEXION:  { categoria: endurecimiento, impacto: localizado, reversion: transitoria, comando: "ss -K dst {ip}", verificacion: "ss -tunap | grep {ip}" }
REINICIAR_NODO:  { categoria: remediacion, impacto: alcanza_servicio, reversion: auto, comando: "reboot", verificacion: "ping -c1 {ip_nodo}" }
RESTAURAR_CONFIG: { categoria: remediacion, impacto: alcanza_servicio, reversion: definida, comando: "restaurar {respaldo}", reversion_cmd: "restaurar {respaldo_previo}", verificacion: "diff config respaldo" }
```

- [ ] **Step 3: Crear `prototipo/tests/fixtures/alerta_vp.json`** (una alerta normalizada; una línea JSON)

```json
{"id_alerta":"1788184171.1318","timestamp":"2026-08-31T13:49:31.755+0000","campaña":"fx","fuente":"wazuh","activo":"objetivo-vuln","servicio":"ssh","familia":"acceso_credenciales","origen_ip":"192.168.1.10","mitre":["T1110.001"],"evento_crudo":"Failed password for root from 192.168.1.10","nivel_wazuh":5,"regla_id":"5760"}
```

- [ ] **Step 4: Crear `prototipo/tests/fixtures/hallazgos.json`**

```json
{"version_herramienta":"Nmap 7.99","timestamp":"2026-08-31T13:00:00+0000","nodos":{"objetivo-vuln":[{"puerto":22,"servicio":"ssh","estado":"open"}],"puesto":[]}}
```

- [ ] **Step 5: Crear `prototipo/tests/fixtures/perfil.yml`**

```yaml
activos:
  objetivo-vuln: { criticidad: alta, servicios_prestados: [] }
  puesto:        { criticidad: media, servicios_prestados: [] }
continuidad:
  impacto_ninguno:          automatica
  impacto_localizado:       automatica_si_confianza
  impacto_alcanza_servicio: humano_siempre
  reversibilidad_obligatoria: true
  no_cortar_gestion: true
excepciones: []
```

- [ ] **Step 6: Commit**

```bash
git add prototipo/
git commit -m "Andamiaje del paquete prototipo: catalogo como dato y fixtures

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Cargar el catálogo

**Files:**
- Create: `prototipo/catalogo.py`
- Test: `prototipo/tests/test_catalogo.py`

**Interfaces:**
- Produces: `cargar_catalogo(ruta) -> dict`; `impacto_de(catalogo, accion_id) -> str`.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_catalogo.py
import os, unittest
from prototipo import catalogo

RAIZ = os.path.join(os.path.dirname(__file__), "..", "catalogo.yml")

class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.cat = catalogo.cargar_catalogo(RAIZ)

    def test_carga_las_14_acciones(self):
        self.assertEqual(len(self.cat), 14)

    def test_impacto_de_bloquear_ip_es_localizado(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "BLOQUEAR_IP"), "localizado")

    def test_impacto_de_bloquear_puerto_es_alcanza_servicio(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "BLOQUEAR_PUERTO"), "alcanza_servicio")

    def test_observacion_es_impacto_ninguno(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "OBS_CONEXIONES"), "ninguno")
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_catalogo -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/catalogo.py
"""El catálogo de acciones como dato: impacto, reversión y comando por acción."""
import yaml

def cargar_catalogo(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def impacto_de(catalogo, accion_id):
    return catalogo[accion_id]["impacto"]
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_catalogo -v`
Expected: PASS (4)

- [ ] **Step 5: Commit**

```bash
git add prototipo/catalogo.py prototipo/tests/test_catalogo.py
git commit -m "Cargar el catalogo de acciones como dato

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Enriquecer con postura y criticidad

**Files:**
- Create: `prototipo/analisis.py`
- Test: `prototipo/tests/test_analisis.py`

**Interfaces:**
- Consumes: `lab.dataset.etiquetar.postura_de(hallazgos, activo, servicio)` (ya existe).
- Produces: `enriquecer(alerta, hallazgos, perfil) -> dict` con `{"postura": dict|None, "criticidad": str}`. La criticidad sale de `perfil["activos"][activo]["criticidad"]`, o `"media"` si el activo no está en el perfil.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_analisis.py
import json, os, unittest, yaml
from prototipo import analisis

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar_json(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read().strip())
def cargar_yaml(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return yaml.safe_load(f)

class TestEnriquecer(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")
        self.hallazgos = cargar_json("hallazgos.json")
        self.perfil = cargar_yaml("perfil.yml")

    def test_postura_expuesta_para_ssh_en_objetivo(self):
        ctx = analisis.enriquecer(self.alerta, self.hallazgos, self.perfil)
        self.assertTrue(ctx["postura"]["expuesto"])

    def test_criticidad_del_perfil(self):
        ctx = analisis.enriquecer(self.alerta, self.hallazgos, self.perfil)
        self.assertEqual(ctx["criticidad"], "alta")

    def test_activo_desconocido_criticidad_media(self):
        a = dict(self.alerta); a["activo"] = "fantasma"
        ctx = analisis.enriquecer(a, self.hallazgos, self.perfil)
        self.assertEqual(ctx["criticidad"], "media")
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_analisis.TestEnriquecer -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/analisis.py
"""Interfaz de análisis (clasificar/justificar) con implementación baseline determinista."""
from lab.dataset.etiquetar import postura_de

def enriquecer(alerta, hallazgos, perfil):
    activo = alerta.get("activo")
    postura = postura_de(hallazgos, activo, alerta.get("servicio"))
    criticidad = perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")
    return {"postura": postura, "criticidad": criticidad}
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_analisis.TestEnriquecer -v`
Expected: PASS (3)

- [ ] **Step 5: Commit**

```bash
git add prototipo/analisis.py prototipo/tests/test_analisis.py
git commit -m "Enriquecer la alerta con postura del auditor y criticidad del perfil

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Clasificador baseline

**Files:**
- Modify: `prototipo/analisis.py`
- Test: `prototipo/tests/test_analisis.py` (añadir clase)

**Interfaces:**
- Consumes: `enriquecer` (Task 3).
- Produces: `clasificar(alerta, contexto) -> {"clase": str, "prioridad": int, "confianza": float}`. Clases posibles: `no_soportada`, `vp_intento_acceso`, `fp_exposicion_inexistente`. `FAMILIAS_ATAQUE = {"acceso_credenciales","reconocimiento","servicio_expuesto","explotacion_conocida"}`.

- [ ] **Step 1: Test que falla**

```python
# añadir a prototipo/tests/test_analisis.py
class TestClasificar(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")

    def test_servicio_expuesto_es_vp_intento_confianza_alta(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 1.0)

    def test_servicio_no_expuesto_es_fp_exposicion_inexistente(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": False}, "criticidad": "media"})
        self.assertEqual(r["clase"], "fp_exposicion_inexistente")

    def test_postura_gris_es_vp_intento_confianza_baja(self):
        r = analisis.clasificar(self.alerta, {"postura": None, "criticidad": "media"})
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 0.5)

    def test_familia_plataforma_es_no_soportada(self):
        a = dict(self.alerta); a["familia"] = "plataforma"
        r = analisis.clasificar(a, {"postura": None, "criticidad": "media"})
        self.assertEqual(r["clase"], "no_soportada")

    def test_prioridad_es_entero_1_a_4(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertIn(r["prioridad"], (1, 2, 3, 4))
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_analisis.TestClasificar -v`
Expected: FAIL `AttributeError: ... 'clasificar'`

- [ ] **Step 3: Implementación** (añadir a `analisis.py`)

```python
FAMILIAS_ATAQUE = {"acceso_credenciales", "reconocimiento", "servicio_expuesto", "explotacion_conocida"}

_PRIORIDAD_BASE = {
    "vp_acceso_consumado": 4, "vp_intento_acceso": 3, "vp_exposicion_gestion": 2,
    "fp_actividad_legitima": 1, "fp_exposicion_inexistente": 1, "no_soportada": 1,
}

def _priorizar(clase, criticidad):
    base = _PRIORIDAD_BASE.get(clase, 1)
    if criticidad in ("alta", "critica"):
        base = min(4, base + 1)
    return base

def clasificar(alerta, contexto):
    postura = contexto.get("postura")
    if alerta.get("familia") not in FAMILIAS_ATAQUE:
        clase, confianza = "no_soportada", 1.0
    elif postura is None:                       # gris: el baseline sabe que no sabe
        clase, confianza = "vp_intento_acceso", 0.5
    elif postura.get("expuesto"):
        clase, confianza = "vp_intento_acceso", 1.0
    else:
        clase, confianza = "fp_exposicion_inexistente", 1.0
    return {"clase": clase, "prioridad": _priorizar(clase, contexto.get("criticidad")), "confianza": confianza}
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_analisis -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prototipo/analisis.py prototipo/tests/test_analisis.py
git commit -m "Clasificador baseline determinista detras de la interfaz

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Justificador baseline (plantilla anclada)

**Files:**
- Modify: `prototipo/analisis.py`
- Test: `prototipo/tests/test_analisis.py` (añadir clase)

**Interfaces:**
- Produces: `justificar(alerta, contexto, clase) -> str`. Cita campos concretos (RNF-02): regla, mitre, origen_ip, activo, servicio, y si el auditor confirma la exposición.

- [ ] **Step 1: Test que falla**

```python
# añadir a prototipo/tests/test_analisis.py
class TestJustificar(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")

    def test_cita_campos_reales(self):
        txt = analisis.justificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"}, "vp_intento_acceso")
        self.assertIn("5760", txt)            # regla_id
        self.assertIn("192.168.1.10", txt)     # origen_ip
        self.assertIn("objetivo-vuln", txt)    # activo
        self.assertIn("ssh", txt)              # servicio

    def test_menciona_confirmacion_del_auditor(self):
        txt = analisis.justificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"}, "vp_intento_acceso")
        self.assertIn("confirma", txt.lower())
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_analisis.TestJustificar -v`
Expected: FAIL `AttributeError`

- [ ] **Step 3: Implementación** (añadir a `analisis.py`)

```python
def justificar(alerta, contexto, clase):
    postura = contexto.get("postura")
    if postura is None:
        veredicto = "el auditor no tiene postura del activo (contexto incompleto)"
    elif postura.get("expuesto"):
        veredicto = f"el auditor confirma que {alerta.get('servicio')} está expuesto en {alerta.get('activo')}"
    else:
        veredicto = f"el auditor no confirma exposición de {alerta.get('servicio')} en {alerta.get('activo')}"
    mitre = ", ".join(alerta.get("mitre", []) or ["s/téc."])
    return (f"Alerta {alerta.get('regla_id')} (técnica {mitre}) desde {alerta.get('origen_ip')} "
            f"contra {alerta.get('activo')} ({alerta.get('servicio')}). {veredicto}. "
            f"Clasificada como {clase}. [justificación de plantilla — baseline, no modelo]")
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_analisis -v`
Expected: PASS (todo analisis)

- [ ] **Step 5: Commit**

```bash
git add prototipo/analisis.py prototipo/tests/test_analisis.py
git commit -m "Justificador baseline: plantilla que ancla a campos reales (RNF-02)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: La política de decisión

**Files:**
- Create: `prototipo/politica.py`
- Test: `prototipo/tests/test_politica.py`

**Interfaces:**
- Produces: `proponer(clase, alerta) -> (accion_id | None, params_dict)`. Mapea la clase a la acción candidata de mínimo impacto. Params: `{"ip": origen_ip}` para acciones sobre el atacante; `{"servicio": servicio}` para las de servicio.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_politica.py
import json, os, unittest
from prototipo import politica

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def alerta():
    with open(os.path.join(FX, "alerta_vp.json"), encoding="utf-8") as f:
        return json.loads(f.read().strip())

class TestProponer(unittest.TestCase):
    def test_vp_intento_propone_bloquear_ip_del_origen(self):
        acc, params = politica.proponer("vp_intento_acceso", alerta())
        self.assertEqual(acc, "BLOQUEAR_IP")
        self.assertEqual(params["ip"], "192.168.1.10")

    def test_no_soportada_no_propone_accion(self):
        acc, params = politica.proponer("no_soportada", alerta())
        self.assertIsNone(acc)

    def test_fp_exposicion_inexistente_no_propone(self):
        acc, _ = politica.proponer("fp_exposicion_inexistente", alerta())
        self.assertIsNone(acc)

    def test_nunca_propone_remediacion_de_alto_impacto(self):
        # ninguna clase mapea a REINICIAR_NODO ni RESTAURAR_CONFIG (principio de mínimo impacto)
        acciones = {politica.proponer(c, alerta())[0] for c in politica.ACCION_POR_CLASE}
        self.assertNotIn("REINICIAR_NODO", acciones)
        self.assertNotIn("RESTAURAR_CONFIG", acciones)
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_politica -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/politica.py
"""La regla clasificación -> acción candidata. Determinista; principio de mínimo impacto."""

ACCION_POR_CLASE = {
    "vp_acceso_consumado": "MATAR_CONEXION",
    "vp_intento_acceso": "BLOQUEAR_IP",
    "vp_exposicion_gestion": "CERRAR_SERVICIO",
    "fp_actividad_legitima": None,
    "fp_exposicion_inexistente": None,
    "no_soportada": None,
}

def proponer(clase, alerta):
    accion = ACCION_POR_CLASE.get(clase)
    if accion is None:
        return (None, {})
    if accion in ("BLOQUEAR_IP", "MATAR_CONEXION"):
        params = {"ip": alerta.get("origen_ip")}
    else:
        params = {"servicio": alerta.get("servicio")}
    return (accion, params)
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_politica -v`
Expected: PASS (4)

- [ ] **Step 5: Commit**

```bash
git add prototipo/politica.py prototipo/tests/test_politica.py
git commit -m "Politica de decision: clase -> accion candidata de minimo impacto

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: El perfil de cliente y el filtro

**Files:**
- Create: `prototipo/perfil.py`
- Test: `prototipo/tests/test_perfil.py`

**Interfaces:**
- Consumes: el catálogo (Task 2).
- Produces:
  - `cargar(ruta) -> dict`
  - `criticidad_de(perfil, activo) -> str` (default `"media"`)
  - `filtrar(perfil, accion_id, params, catalogo, activo, servicio, confianza) -> dict` con `{"resultado": "permite"|"degrada"|"veta"|"sin_accion", "accion_final": str|None, "requiere_humano": bool}`.
- Constantes: `UMBRAL_CONFIANZA = 0.7`; `DEGRADACION = {"BLOQUEAR_PUERTO": "BLOQUEAR_IP"}` (alcanza_servicio → localizado).

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_perfil.py
import os, unittest, yaml
from prototipo import perfil, catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
def perfil_fx():
    with open(os.path.join(FX, "perfil.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)

class TestFiltro(unittest.TestCase):
    def setUp(self):
        self.p = perfil_fx()

    def test_sin_accion(self):
        r = perfil.filtrar(self.p, None, {}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "sin_accion")

    def test_localizado_confianza_alta_permite(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "permite")
        self.assertFalse(r["requiere_humano"])

    def test_localizado_confianza_baja_veta(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 0.5)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])

    def test_alcanza_servicio_sin_alternativa_veta(self):
        r = perfil.filtrar(self.p, "AISLAR_NODO", {"ip_nodo":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])

    def test_bloquear_puerto_degrada_a_bloquear_ip(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_PUERTO", {"puerto":443,"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "degrada")
        self.assertEqual(r["accion_final"], "BLOQUEAR_IP")

    def test_no_cortar_gestion_veta_cerrar_ssh(self):
        r = perfil.filtrar(self.p, "CERRAR_SERVICIO", {"servicio":"ssh"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_perfil -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/perfil.py
"""El perfil de cliente (V3/V4) y el filtro permite/degrada/veta (RNF-14, RF-17/18/19)."""
import yaml
from prototipo import catalogo as _cat

UMBRAL_CONFIANZA = 0.7                       # recalibrable en la Fase 6
DEGRADACION = {"BLOQUEAR_PUERTO": "BLOQUEAR_IP"}   # alcanza_servicio -> localizado
_REVERSION_OK = {"definida", "auto", "transitoria"}

def cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def criticidad_de(perfil, activo):
    return perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")

def _res(resultado, accion_final, requiere_humano):
    return {"resultado": resultado, "accion_final": accion_final, "requiere_humano": requiere_humano}

def _corta_gestion(catalogo, accion_id, servicio):
    return catalogo.get(accion_id, {}).get("corta_gestion_si") == servicio

def _excepcion_nunca_automatica(perfil, activo, params):
    # La excepción del perfil marca un puerto/servicio de un activo como no-automatico.
    puerto = params.get("puerto")
    for ex in perfil.get("excepciones", []) or []:
        if (ex.get("activo") == activo and ex.get("regla") == "nunca_automatica"
                and ex.get("servicio") == puerto):
            return True
    return False

def _permite_localizado(perfil, confianza):
    # regla impacto_localizado del perfil aplicada a una acción ya localizada
    regla = perfil.get("continuidad", {}).get("impacto_localizado", "humano_siempre")
    if regla == "automatica":
        return True
    if regla == "automatica_si_confianza":
        return confianza >= UMBRAL_CONFIANZA
    return False

def filtrar(perfil, accion_id, params, catalogo, activo, servicio, confianza):
    if accion_id is None:
        return _res("sin_accion", None, False)
    acc = catalogo[accion_id]
    cont = perfil.get("continuidad", {})
    # Precondición dura RF-19: no cortar el plano de gestión.
    if cont.get("no_cortar_gestion") and _corta_gestion(catalogo, accion_id, servicio):
        return _res("veta", None, True)
    # Precondición dura RF-18: reversión definida y verificable.
    if cont.get("reversibilidad_obligatoria") and acc.get("reversion") not in _REVERSION_OK:
        return _res("veta", None, True)
    # Excepción por servicio/activo (más específica que la regla por impacto).
    if _excepcion_nunca_automatica(perfil, activo, params):
        alt = DEGRADACION.get(accion_id)
        if alt is not None:
            return _res("degrada", alt, not _permite_localizado(perfil, confianza))
        return _res("veta", accion_id, True)
    impacto = acc["impacto"]
    regla = cont.get(f"impacto_{impacto}", "humano_siempre")
    if regla == "automatica":
        return _res("permite", accion_id, False)
    if regla == "automatica_si_confianza":
        if confianza >= UMBRAL_CONFIANZA:
            return _res("permite", accion_id, False)
        return _res("veta", accion_id, True)
    # regla == "humano_siempre" (impacto alcanza_servicio): intentar degradar
    alt = DEGRADACION.get(accion_id)
    if alt is not None:
        if _permite_localizado(perfil, confianza):
            return _res("degrada", alt, False)
        return _res("degrada", alt, True)
    return _res("veta", accion_id, True)
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_perfil -v`
Expected: PASS (6)

- [ ] **Step 5: Commit**

```bash
git add prototipo/perfil.py prototipo/tests/test_perfil.py
git commit -m "Perfil de cliente y filtro permite/degrada/veta (RNF-14, RF-17/18/19)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: La traza de decisión

**Files:**
- Create: `prototipo/traza.py`
- Test: `prototipo/tests/test_traza.py`

**Interfaces:**
- Produces: `construir(id_decision, timestamp, alerta, analisis_out, accion_prop, impacto, perfil_nombre, filtro_out) -> dict` con los campos del registro de decisión (spec §7). `VERSION_BASELINE = "baseline-0"`.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_traza.py
import unittest
from prototipo import traza

class TestConstruir(unittest.TestCase):
    def test_registro_completo(self):
        r = traza.construir(
            id_decision="d1", timestamp="2026-08-31T00:00:00Z",
            alerta={"id_alerta":"a1","activo":"objetivo-vuln"},
            analisis_out={"clase":"vp_intento_acceso","prioridad":4,"confianza":1.0,"justificacion":"..."},
            accion_prop="BLOQUEAR_IP", impacto="localizado", perfil_nombre="empresarial",
            filtro_out={"resultado":"permite","accion_final":"BLOQUEAR_IP","requiere_humano":False})
        for k in ("id_decision","id_alerta","clase","confianza","justificacion","accion_propuesta",
                  "impacto","perfil_aplicado","resultado_filtro","accion_final","requiere_humano","version_baseline"):
            self.assertIn(k, r)
        self.assertEqual(r["id_alerta"], "a1")
        self.assertEqual(r["resultado_filtro"], "permite")
        self.assertEqual(r["version_baseline"], "baseline-0")
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_traza -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/traza.py
"""Construye el registro de decisión auditable (RF-09)."""

VERSION_BASELINE = "baseline-0"

def construir(id_decision, timestamp, alerta, analisis_out, accion_prop, impacto, perfil_nombre, filtro_out):
    return {
        "id_decision": id_decision,
        "timestamp": timestamp,
        "id_alerta": alerta.get("id_alerta"),
        "activo": alerta.get("activo"),
        "clase": analisis_out.get("clase"),
        "prioridad": analisis_out.get("prioridad"),
        "confianza": analisis_out.get("confianza"),
        "justificacion": analisis_out.get("justificacion"),
        "accion_propuesta": accion_prop,
        "impacto": impacto,
        "perfil_aplicado": perfil_nombre,
        "resultado_filtro": filtro_out.get("resultado"),
        "accion_final": filtro_out.get("accion_final"),
        "requiere_humano": filtro_out.get("requiere_humano"),
        "version_baseline": VERSION_BASELINE,
    }
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest prototipo.tests.test_traza -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prototipo/traza.py prototipo/tests/test_traza.py
git commit -m "Registro de decision auditable (RF-09)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: El orquestador y el CLI

**Files:**
- Create: `prototipo/triaje.py`
- Test: `prototipo/tests/test_triaje.py`

**Interfaces:**
- Consumes: `analisis`, `politica`, `perfil`, `catalogo`, `traza`.
- Produces: `procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo, id_decision, timestamp) -> dict` (una traza de decisión completa). Y `main(argv)` como CLI: `python3 -m prototipo.triaje <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl>`.

- [ ] **Step 1: Test que falla**

```python
# prototipo/tests/test_triaje.py
import json, os, unittest, yaml
from prototipo import triaje, catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
def j(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return json.loads(f.read().strip())
def y(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return yaml.safe_load(f)

class TestProcesar(unittest.TestCase):
    def test_lazo_completo_una_alerta(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="2026-08-31T00:00:00Z")
        # fuerza bruta SSH contra objetivo-vuln con SSH expuesto -> VP intento -> BLOQUEAR_IP localizado -> permite
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["accion_propuesta"], "BLOQUEAR_IP")
        self.assertEqual(r["resultado_filtro"], "permite")
        self.assertIn("192.168.1.10", r["justificacion"])
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest prototipo.tests.test_triaje -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# prototipo/triaje.py
"""Orquesta el lazo de decisión: ingesta -> análisis -> política -> perfil -> traza."""
import json, os, sys, yaml
from prototipo import analisis, politica, perfil as perfilm, traza, catalogo as catm

def procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo, id_decision, timestamp):
    ctx = analisis.enriquecer(alerta, hallazgos, perfil_dict)
    clas = analisis.clasificar(alerta, ctx)
    just = analisis.justificar(alerta, ctx, clas["clase"])
    accion, params = politica.proponer(clas["clase"], alerta)
    impacto = catalogo[accion]["impacto"] if accion else "ninguno"
    filtro = perfilm.filtrar(perfil_dict, accion, params, catalogo, alerta.get("activo"),
                             alerta.get("servicio"), clas["confianza"])
    analisis_out = {**clas, "justificacion": just}
    return traza.construir(id_decision, timestamp, alerta, analisis_out, accion, impacto, perfil_nombre, filtro)

def main(argv):
    alertas_path, perfil_path, hallazgos_path, salida = argv[1:5]
    perfil_dict = perfilm.cargar(perfil_path)
    perfil_nombre = perfil_path.split("/")[-1].replace(".yml", "")
    with open(hallazgos_path, encoding="utf-8") as f:
        hallazgos = json.load(f)
    catalogo = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
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
            ts = alerta.get("timestamp", "")
            r = procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo,
                         id_decision=f"d{i}", timestamp=ts)
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} decisiones -> {salida}")

if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Verificar que pasa + batería completa**

Run: `python3 -m unittest discover -s prototipo/tests -v`
Expected: PASS (todas)

- [ ] **Step 5: Commit**

```bash
git add prototipo/triaje.py prototipo/tests/test_triaje.py
git commit -m "Orquestador del lazo de decision y CLI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Perfiles de ejemplo, alertas ilustrativas y demostración de RNF-14

**Files:**
- Create: `prototipo/perfiles/residencial.yml`, `prototipo/perfiles/empresarial.yml`
- Create: `prototipo/ilustrativas.jsonl`
- Create: `prototipo/tests/test_rnf14.py`

**Interfaces:**
- Consumes: `triaje.procesar`.
- Produces: la prueba de que la MISMA alerta ilustrativa produce decisiones distintas con los dos perfiles.

- [ ] **Step 1: Crear `prototipo/perfiles/residencial.yml`**

```yaml
# Operador residencial: equipos de abonado, poca criticidad, continuidad permisiva.
activos:
  cpe-abonado:  { criticidad: media, servicios_prestados: [] }
  servidor-web: { criticidad: media, servicios_prestados: [] }
continuidad:
  impacto_ninguno:          automatica
  impacto_localizado:       automatica_si_confianza
  impacto_alcanza_servicio: automatica_si_confianza
  reversibilidad_obligatoria: true
  no_cortar_gestion: true
excepciones: []
```

- [ ] **Step 2: Crear `prototipo/perfiles/empresarial.yml`**

```yaml
# Cliente empresarial: servidores publicados, continuidad estricta.
activos:
  servidor-web:   { criticidad: alta, servicios_prestados: [443, 80] }
  controlador-ot: { criticidad: critica, servicios_prestados: [502] }
continuidad:
  impacto_ninguno:          automatica
  impacto_localizado:       automatica_si_confianza
  impacto_alcanza_servicio: humano_siempre
  reversibilidad_obligatoria: true
  no_cortar_gestion: true
excepciones:
  - { servicio: 443, activo: servidor-web, regla: nunca_automatica }
```

- [ ] **Step 3: Crear `prototipo/ilustrativas.jsonl`** (alertas que SÍ ejercitan acciones de impacto; declaradas ilustrativas)

```json
{"id_alerta":"ilu-1","timestamp":"2026-08-31T00:00:00Z","campaña":"ilustrativa","fuente":"ilustrativa","activo":"servidor-web","servicio":"https","familia":"servicio_expuesto","origen_ip":"203.0.113.9","mitre":["T1190"],"evento_crudo":"flood contra 443","nivel_wazuh":10,"regla_id":"ilu"}
```

- [ ] **Step 4: Escribir el test de RNF-14**

Nota: la alerta ilustrativa (`servicio_expuesto` sobre `servidor-web` con SSH... no) — para que la política proponga una acción `alcanza_servicio`, se clasifica como `vp_exposicion_gestion` forzando la clase en el test, ya que el baseline no la produce. El test demuestra el filtro, que es lo que divide a los perfiles.

```python
# prototipo/tests/test_rnf14.py
import os, unittest
from prototipo import perfil, catalogo

BASE = os.path.join(os.path.dirname(__file__), "..")
CAT = catalogo.cargar_catalogo(os.path.join(BASE, "catalogo.yml"))
RES = perfil.cargar(os.path.join(BASE, "perfiles", "residencial.yml"))
EMP = perfil.cargar(os.path.join(BASE, "perfiles", "empresarial.yml"))

class TestRNF14(unittest.TestCase):
    def test_misma_accion_alcanza_servicio_diverge_por_perfil(self):
        # BLOQUEAR_PUERTO (alcanza_servicio) contra servidor-web:443, confianza alta.
        # Residencial: impacto_alcanza_servicio=automatica_si_confianza -> permite BLOQUEAR_PUERTO.
        # Empresarial: excepción 443 nunca_automatica -> degrada a BLOQUEAR_IP.
        res = perfil.filtrar(RES, "BLOQUEAR_PUERTO", {"puerto":443,"ip":"203.0.113.9"}, CAT, "servidor-web", "https", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_PUERTO", {"puerto":443,"ip":"203.0.113.9"}, CAT, "servidor-web", "https", 1.0)
        self.assertNotEqual(
            (res["resultado"], res["accion_final"]),
            (emp["resultado"], emp["accion_final"]),
            f"los perfiles deberían divergir: res={res}, emp={emp}")

    def test_localizado_coincide_en_ambos(self):
        # sobre la acción localizada del laboratorio real, los perfiles COINCIDEN (honesto)
        res = perfil.filtrar(RES, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "servidor-web", "ssh", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "servidor-web", "ssh", 1.0)
        self.assertEqual(res["resultado"], emp["resultado"])
```

- [ ] **Step 5: Verificar y ajustar**

Run: `python3 -m unittest prototipo.tests.test_rnf14 -v`
Expected: PASS. El primer test demuestra la divergencia entre perfiles sobre una acción `alcanza_servicio`; el segundo, la coincidencia honesta sobre una acción localizada.

- [ ] **Step 6: Commit**

```bash
git add prototipo/perfiles/ prototipo/ilustrativas.jsonl prototipo/tests/test_rnf14.py
git commit -m "Perfiles de ejemplo y demostracion de RNF-14: misma alerta, decision distinta

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Ejecución de extremo a extremo y documentación

**Files:**
- Create: `prototipo/README.md`
- Modify: `documentacion/05-fase5-implementacion-del-prototipo/README.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: trazas de decisión reales sobre el dataset de la Fase 3, y la documentación de 5A.

- [ ] **Step 1: Correr el motor sobre el dataset real con un perfil**

Run:
```bash
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
  lab/campañas/2026-08-31-evaluacion/hallazgos.json /tmp/trazas-emp.jsonl
```
Expected: imprime cuántas decisiones. Verifica que hay trazas con `clase` y `resultado_filtro`:
```bash
python3 -c "import json,collections;r=[json.loads(l) for l in open('/tmp/trazas-emp.jsonl',encoding='utf-8')];print('clases',dict(collections.Counter(x['clase'] for x in r)));print('filtro',dict(collections.Counter(x['resultado_filtro'] for x in r)))"
```

- [ ] **Step 2: Comprobar el criterio de cierre de 5A**

Run:
```bash
python3 - <<'PY'
import json, collections
r=[json.loads(l) for l in open("/tmp/trazas-emp.jsonl",encoding="utf-8")]
assert len(r) > 0
assert all("clase" in x and "resultado_filtro" in x and "justificacion" in x for x in r)
assert all(x["resultado_filtro"] in ("permite","degrada","veta","sin_accion") for x in r)
print("5A CIERRE OK:", len(r), "decisiones;", dict(collections.Counter(x["resultado_filtro"] for x in r)))
PY
```
Expected: `5A CIERRE OK`.

- [ ] **Step 3: Escribir `prototipo/README.md`**

Documenta: qué es el núcleo de decisión (5A), el lazo (ingesta → análisis baseline → política → perfil → traza), que el clasificador es un **baseline determinista** placeholder (el ML es 5C), el esquema de la traza, cómo se corre el CLI, y la demostración de RNF-14 (perfiles coinciden en localizado, divergen en alcanza_servicio). Enlaza a la spec y a la política de decisión.

- [ ] **Step 4: Actualizar el README de la Fase 5**

En `documentacion/05-fase5-implementacion-del-prototipo/README.md`, marca en la tabla de piezas que **Ingesta** y el **núcleo de decisión (5A)** están hechos (con enlace a `prototipo/`), y que quedan 5B (lazo en vivo: conector SSH + validación humana TUI) y 5C (ML). Añade una nota de que el clasificador actual es baseline y el ML se enchufa detrás de la interfaz.

- [ ] **Step 5: Batería completa final**

Run: `python3 -m unittest discover -s prototipo/tests`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add prototipo/README.md documentacion/05-fase5-implementacion-del-prototipo/README.md
git commit -m "Cerrar la Fase 5A: nucleo de decision documentado y verificado e2e

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas de ejecución

- **Todo es Python puro con fixtures**; no necesita el laboratorio en marcha salvo el Task 11, que corre sobre ficheros ya congelados (`lab/dataset/etiquetado.jsonl`, `hallazgos.json`) — tampoco necesita el lab vivo.
- **Ejecutar desde la raíz del repo** para que `import prototipo...` y `from lab.dataset...` resuelvan. Requiere `lab/__init__.py` (ya existe) y `prototipo/__init__.py` (Task 1).
- **Batería completa:** `python3 -m unittest discover -s prototipo/tests`.
