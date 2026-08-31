# Dataset de alertas etiquetado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Producir `lab/dataset/etiquetado.jsonl` — el dataset de alertas etiquetado (VP/FP/PROPIA/no_soportada) y particionado que cierra la Fase 3 y desbloquea las Fases 5 y 6.

**Architecture:** Una tubería con los ficheros como frontera. Dos scripts de shell generan actividad real sobre el laboratorio Containerlab (`campana.sh`) y su postura (`auditar.sh`); un núcleo Python puro normaliza cada alerta a un esquema común y le asigna la etiqueta de ground truth cruzándola contra la postura del activo. El núcleo Python son funciones puras probadas con `unittest` sobre fixtures; los scripts de shell se validan ejecutándolos contra el laboratorio en vivo.

**Tech Stack:** Python 3.14 (stdlib: `json`, `unittest`; `pyyaml` del sistema). Shell POSIX (`sh`). Docker/Containerlab/Wazuh/Nmap ya desplegados. **Sin pip, sin venv, sin pytest** — el entorno es externally-managed y no hace falta ninguna dependencia externa.

**Spec:** [docs/superpowers/specs/2026-08-31-dataset-alertas-etiquetado-design.md](../specs/2026-08-31-dataset-alertas-etiquetado-design.md)

## Global Constraints

- **Sin dependencias externas.** Solo stdlib de Python 3.14 más `pyyaml` (ya instalado). Tests con `python3 -m unittest`, nunca pytest.
- **Ficheros como frontera** (spec §3): cada etapa lee y escribe ficheros; nada de tubería en memoria de una sola pasada.
- **El activo se resuelve por `predecoder.hostname`, nunca por `agent.id`** (RF-16): en Containerlab todo entra como `agent.id 000`.
- **`evento_crudo` es dato inerte** (RNF-08): se guarda tal cual, nunca se interpreta ni se ejecuta.
- **Esquema normalizado exacto** (spec §5): los 16 campos, con estos nombres literales — `id_alerta, timestamp, campaña, fuente, activo, servicio, familia, origen_ip, mitre, evento_crudo, nivel_wazuh, regla_id, etiqueta, etiqueta_por, postura_activo, particion`.
- **Prefijo de contenedor:** `clab-red-cliente-<nodo>`. Contenedor de Wazuh: `clab-red-cliente-wazuh`. Alertas en `/var/ossec/logs/alerts/alerts.json` dentro de ese contenedor.
- **Codificación UTF-8** en todos los ficheros; `ensure_ascii=False` al escribir JSON, para conservar `campaña` con ñ.
- **Commits frecuentes**, uno por tarea. Mensaje de commit en español, terminado con la línea `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Estructura de ficheros

```
lab/dataset/
├── __init__.py
├── esquema.py          construcción del registro normalizado + derivaciones (activo, servicio, familia)
├── etiquetar.py        el árbol de decisión de etiquetado (función pura)
├── normalizar.py       CLI: alerts.json crudo → normalizadas.jsonl
├── construir.py        CLI: orquesta normalizar + etiquetar → etiquetado.jsonl
├── particion.yml       reparto a priori de campañas (dato, versionado)
├── resoluciones.yml    decisiones humanas sobre dudosos (dato, versionado)
└── tests/
    ├── __init__.py
    ├── fixtures/
    │   ├── alerta_ssh_vp.json      alerta cruda real (fuerza bruta contra objetivo-vuln)
    │   ├── alerta_auditor.json     alerta cuya srcip es el auditor
    │   ├── hallazgos.json          postura de ejemplo
    │   └── campaña.yml             ficha de ejemplo
    ├── test_esquema.py
    └── test_etiquetar.py

lab/scripts/
├── campana.sh          genera actividad real, congela alerts.json + ficha
└── auditar.sh          nmap → hallazgos.json normalizado
```

Responsabilidades: `esquema.py` construye el registro y deriva sus campos (una responsabilidad: traducir cruda→normalizada). `etiquetar.py` decide la etiqueta (una responsabilidad: el ground truth). Los CLIs (`normalizar.py`, `construir.py`) solo hacen E/S de ficheros y llaman al núcleo. Los `.sh` solo hablan con el laboratorio.

---

## Task 1: Scaffolding del paquete y fixtures reales

**Files:**
- Create: `lab/dataset/__init__.py` (vacío)
- Create: `lab/dataset/tests/__init__.py` (vacío)
- Create: `lab/dataset/tests/fixtures/alerta_ssh_vp.json`
- Create: `lab/dataset/tests/fixtures/alerta_auditor.json`
- Create: `lab/dataset/tests/fixtures/hallazgos.json`
- Create: `lab/dataset/tests/fixtures/campaña.yml`

**Interfaces:**
- Produces: los ficheros fixture que todas las tareas de test consumen.

- [ ] **Step 1: Crear los paquetes vacíos**

```bash
mkdir -p lab/dataset/tests/fixtures
touch lab/__init__.py lab/dataset/__init__.py lab/dataset/tests/__init__.py
```

`lab/__init__.py` hace de `lab` un paquete para que `python3 -m lab.dataset.construir` y los imports `from lab.dataset import ...` resuelvan desde la raíz del repo.

- [ ] **Step 2: Capturar una alerta cruda real como fixture VP**

Con el laboratorio arriba (`sh lab/lab.sh up`), genera una alerta real y guárdala:

```bash
docker exec clab-red-cliente-wazuh sh -c 'grep -a "\"id\":\"5760\"" /var/ossec/logs/alerts/alerts.json | tail -1' \
  > lab/dataset/tests/fixtures/alerta_ssh_vp.json
```

**Importante:** el fixture VP representa un ataque desde el nodo atacante (`puesto`), no desde el auditor. Edítalo para que `data.srcip` sea `192.168.1.10` (la IP de `puesto`) — así el árbol de etiquetado lo trata como atacante real y no como actividad propia. Verifica:

```bash
python3 -c "import json;a=json.load(open('lab/dataset/tests/fixtures/alerta_ssh_vp.json'));a['data']['srcip']='192.168.1.10';json.dump(a,open('lab/dataset/tests/fixtures/alerta_ssh_vp.json','w'),ensure_ascii=False);assert a['predecoder']['hostname']=='objetivo-vuln';print('OK', a['rule']['id'], a['data']['srcip'])"
```

Si el fichero sale vacío, lanza antes un ataque (ver Task 8) y repite.

- [ ] **Step 3: Crear a mano el fixture de alerta del auditor**

Edita `lab/dataset/tests/fixtures/alerta_auditor.json` — copia la del paso 2 pero con `data.srcip` = `172.20.20.4` (la IP del auditor). Una sola línea JSON:

```json
{"timestamp":"2026-08-31T13:49:31.755+0000","rule":{"level":5,"description":"sshd: authentication failed.","id":"5760","mitre":{"id":["T1110.001"]},"groups":["syslog","sshd","authentication_failed"]},"agent":{"id":"000","name":"wazuh"},"id":"1788184171.9999","full_log":"Aug 31 13:49:31 objetivo-vuln sshd[708]: Failed password for root from 172.20.20.4 port 5008 ssh2","predecoder":{"program_name":"sshd","hostname":"objetivo-vuln"},"location":"172.20.20.2","data":{"srcip":"172.20.20.4","dstuser":"root"}}
```

- [ ] **Step 3b: Crear el fixture de admin legítimo (`alerta_admin_fp.json`)**

Misma alerta de fallo SSH, pero desde una IP de admin declarada (`192.168.1.1`). El etiquetado
debe marcarla FP (actividad administrativa legítima), no VP, aunque el SSH esté expuesto:

```json
{"timestamp":"2026-08-31T14:00:00.000+0000","rule":{"level":5,"description":"sshd: authentication failed.","id":"5760","mitre":{"id":["T1110.001"]},"groups":["syslog","sshd","authentication_failed"]},"agent":{"id":"000","name":"wazuh"},"id":"1788184171.7777","full_log":"Aug 31 14:00:00 objetivo-vuln sshd[900]: Failed password for admin from 192.168.1.1 port 6001 ssh2","predecoder":{"program_name":"sshd","hostname":"objetivo-vuln"},"location":"172.20.20.2","data":{"srcip":"192.168.1.1","dstuser":"admin"}}
```

Añádelo a la lista de fixtures del bloque **Files** de esta tarea.

- [ ] **Step 4: Crear el fixture de postura (`hallazgos.json`)**

```json
{"version_herramienta":"nmap 7.95","timestamp":"2026-08-31T13:00:00+0000","nodos":{"objetivo-vuln":[{"puerto":22,"servicio":"ssh","estado":"open"},{"puerto":23,"servicio":"telnet","estado":"open"}],"puesto":[]}}
```

- [ ] **Step 5: Crear el fixture de ficha de campaña (`campaña.yml`)**

```yaml
id: 2026-08-31-fuerzabruta
fecha: 2026-08-31
ataques:
  - escenario: fuerza bruta SSH
    objetivo: objetivo-vuln
    desde: puesto
auditor:
  ips: ["172.20.20.4"]
  cuando: "2026-08-31T13:00:00+0000"
legitimos:
  ips: ["192.168.1.1"]   # admin declarado: sus logins fallidos son FP, no ataque
```

- [ ] **Step 6: Commit**

```bash
git add lab/dataset/
git commit -m "Andamiaje del paquete dataset y fixtures de alerta reales

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Derivación de campos (activo, servicio, familia)

**Files:**
- Create: `lab/dataset/esquema.py`
- Test: `lab/dataset/tests/test_esquema.py`

**Interfaces:**
- Produces:
  - `resolver_activo(cruda: dict) -> str` — `predecoder.hostname`, o `location` si falta, o `"desconocido"`.
  - `servicio_de(cruda: dict) -> str` — `"ssh"`, `"telnet"`, el `program_name`, o `"desconocido"`.
  - `familia_de(rule: dict) -> str` — una de: `acceso_credenciales`, `reconocimiento`, `servicio_expuesto`, `explotacion_conocida`, `plataforma`, `otra`.

- [ ] **Step 1: Escribir el test que falla**

```python
# lab/dataset/tests/test_esquema.py
import json, os, unittest
from lab.dataset import esquema

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read().strip())

class TestDerivaciones(unittest.TestCase):
    def setUp(self):
        self.ssh = cargar("alerta_ssh_vp.json")

    def test_resolver_activo_usa_hostname(self):
        self.assertEqual(esquema.resolver_activo(self.ssh), "objetivo-vuln")

    def test_resolver_activo_ignora_agent_id(self):
        # agent.id es 000 e inútil; el activo NO debe salir de ahí
        self.assertNotEqual(esquema.resolver_activo(self.ssh), "000")

    def test_resolver_activo_sin_hostname_cae_a_location(self):
        self.assertEqual(esquema.resolver_activo({"location": "172.20.20.2"}), "172.20.20.2")

    def test_servicio_ssh(self):
        self.assertEqual(esquema.servicio_de(self.ssh), "ssh")

    def test_familia_fuerza_bruta_es_acceso_credenciales(self):
        self.assertEqual(esquema.familia_de(self.ssh["rule"]), "acceso_credenciales")

    def test_familia_desconocida_es_otra(self):
        self.assertEqual(esquema.familia_de({"groups": ["algo_raro"]}), "otra")
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `python3 -m unittest lab.dataset.tests.test_esquema -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'lab.dataset.esquema'`

- [ ] **Step 3: Implementación mínima**

```python
# lab/dataset/esquema.py
"""Traducción de una alerta cruda de Wazuh al esquema normalizado del proyecto."""

FUENTE = "wazuh"

def resolver_activo(cruda):
    # En Containerlab todo entra como agent.id 000: el activo se deduce del
    # hostname que decodifica Wazuh, no del id de agente (RF-16).
    pre = cruda.get("predecoder", {})
    if pre.get("hostname"):
        return pre["hostname"]
    return cruda.get("location", "desconocido")

def servicio_de(cruda):
    grupos = cruda.get("rule", {}).get("groups", [])
    prog = cruda.get("predecoder", {}).get("program_name", "")
    if "sshd" in grupos or prog == "sshd":
        return "ssh"
    if "telnetd" in grupos or "telnet" in grupos or prog == "telnetd":
        return "telnet"
    return prog or "desconocido"

def familia_de(rule):
    g = set(rule.get("groups", []))
    rid = rule.get("id")
    if g & {"authentication_failed", "authentication_failures", "invalid_login"}:
        return "acceso_credenciales"
    if "recon" in g or rid == "5706":
        return "reconocimiento"
    if g & {"telnetd", "telnet"}:
        return "servicio_expuesto"
    if g & {"exploit", "attack"}:
        return "explotacion_conocida"
    if g & {"rootcheck", "cis", "ossec"}:
        return "plataforma"
    return "otra"
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

Run: `python3 -m unittest lab.dataset.tests.test_esquema -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add lab/dataset/esquema.py lab/dataset/tests/test_esquema.py
git commit -m "Derivar activo, servicio y familia de una alerta cruda

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Construcción del registro normalizado

**Files:**
- Modify: `lab/dataset/esquema.py`
- Test: `lab/dataset/tests/test_esquema.py` (añadir clase)

**Interfaces:**
- Consumes: `resolver_activo`, `servicio_de`, `familia_de` (Task 2).
- Produces: `normalizar_alerta(cruda: dict, campaña: str) -> dict` — devuelve los 12 campos de identidad/activo/baseline del esquema (§5), **sin** el grupo de ground truth (lo añade Task 5).

- [ ] **Step 1: Escribir el test que falla**

```python
# añadir a lab/dataset/tests/test_esquema.py
class TestNormalizarAlerta(unittest.TestCase):
    def setUp(self):
        self.ssh = cargar("alerta_ssh_vp.json")
        self.reg = esquema.normalizar_alerta(self.ssh, "2026-08-31-fuerzabruta")

    def test_campos_de_identidad(self):
        self.assertEqual(self.reg["campaña"], "2026-08-31-fuerzabruta")
        self.assertEqual(self.reg["fuente"], "wazuh")
        self.assertEqual(self.reg["id_alerta"], self.ssh["id"])

    def test_baseline_conservado(self):
        self.assertEqual(self.reg["nivel_wazuh"], self.ssh["rule"]["level"])
        self.assertEqual(self.reg["regla_id"], self.ssh["rule"]["id"])

    def test_evento_crudo_intacto(self):
        self.assertEqual(self.reg["evento_crudo"], self.ssh["full_log"])

    def test_activo_y_servicio(self):
        self.assertEqual(self.reg["activo"], "objetivo-vuln")
        self.assertEqual(self.reg["servicio"], "ssh")

    def test_mitre_es_lista(self):
        self.assertIsInstance(self.reg["mitre"], list)
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `python3 -m unittest lab.dataset.tests.test_esquema.TestNormalizarAlerta -v`
Expected: FAIL con `AttributeError: module 'lab.dataset.esquema' has no attribute 'normalizar_alerta'`

- [ ] **Step 3: Implementación mínima**

```python
# añadir a lab/dataset/esquema.py
def normalizar_alerta(cruda, campaña):
    rule = cruda.get("rule", {})
    data = cruda.get("data", {})
    return {
        "id_alerta": cruda.get("id"),
        "timestamp": cruda.get("timestamp"),
        "campaña": campaña,
        "fuente": FUENTE,
        "activo": resolver_activo(cruda),
        "servicio": servicio_de(cruda),
        "familia": familia_de(rule),
        "origen_ip": data.get("srcip"),
        "mitre": rule.get("mitre", {}).get("id", []),
        "evento_crudo": cruda.get("full_log"),
        "nivel_wazuh": rule.get("level"),
        "regla_id": rule.get("id"),
    }
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

Run: `python3 -m unittest lab.dataset.tests.test_esquema -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add lab/dataset/esquema.py lab/dataset/tests/test_esquema.py
git commit -m "Construir el registro normalizado (12 campos sin ground truth)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Postura del activo (cruce con hallazgos)

**Files:**
- Create: `lab/dataset/etiquetar.py`
- Test: `lab/dataset/tests/test_etiquetar.py`

**Interfaces:**
- Produces: `postura_de(hallazgos: dict, activo: str, servicio: str) -> dict | None` — `{"expuesto": True/False, ...}` si el nodo se conoce; `None` si el nodo no está en `hallazgos` (caso gris → decisión humana).

- [ ] **Step 1: Escribir el test que falla**

```python
# lab/dataset/tests/test_etiquetar.py
import json, os, unittest
from lab.dataset import etiquetar

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar_json(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read())

class TestPostura(unittest.TestCase):
    def setUp(self):
        self.h = cargar_json("hallazgos.json")

    def test_servicio_expuesto(self):
        p = etiquetar.postura_de(self.h, "objetivo-vuln", "ssh")
        self.assertTrue(p["expuesto"])

    def test_servicio_no_expuesto(self):
        p = etiquetar.postura_de(self.h, "puesto", "ssh")
        self.assertFalse(p["expuesto"])

    def test_nodo_desconocido_es_gris(self):
        self.assertIsNone(etiquetar.postura_de(self.h, "nodo-fantasma", "ssh"))
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `python3 -m unittest lab.dataset.tests.test_etiquetar.TestPostura -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'lab.dataset.etiquetar'`

- [ ] **Step 3: Implementación mínima**

```python
# lab/dataset/etiquetar.py
"""Árbol de decisión del etiquetado: asigna el ground truth a cada alerta."""

def postura_de(hallazgos, activo, servicio):
    nodos = hallazgos.get("nodos", {})
    if activo not in nodos:
        return None  # nodo desconocido → caso gris, decide un humano
    servicios = {s.get("servicio") for s in nodos[activo] if s.get("estado") == "open"}
    return {"expuesto": servicio in servicios, "servicios_abiertos": sorted(servicios)}
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

Run: `python3 -m unittest lab.dataset.tests.test_etiquetar.TestPostura -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add lab/dataset/etiquetar.py lab/dataset/tests/test_etiquetar.py
git commit -m "Calcular la postura del activo cruzando contra los hallazgos

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: El árbol de decisión de etiquetado

**Files:**
- Modify: `lab/dataset/etiquetar.py`
- Test: `lab/dataset/tests/test_etiquetar.py` (añadir clase)

**Interfaces:**
- Consumes: `postura_de` (Task 4); `normalizar_alerta` (Task 3).
- Produces: `etiquetar(registro: dict, hallazgos: dict, ficha: dict, resoluciones: dict) -> dict` — el registro con los cuatro campos de ground truth añadidos (`etiqueta`, `etiqueta_por`, `postura_activo`, `particion=None`). `ficha` es la campaña.yml cargada (incluye `auditor.ips` y `legitimos.ips`); `resoluciones` es `{id_alerta: etiqueta}`.
- Constante: `FAMILIAS_SOPORTADAS = {"acceso_credenciales", "reconocimiento", "servicio_expuesto", "explotacion_conocida"}` (dentro del caso de uso; `plataforma` y `otra` no).

- [ ] **Step 1: Escribir el test que falla**

```python
# añadir a lab/dataset/tests/test_etiquetar.py
from lab.dataset import esquema

def cargar_texto(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return f.read()

class TestEtiquetar(unittest.TestCase):
    def setUp(self):
        import yaml
        self.h = cargar_json("hallazgos.json")
        self.ficha = yaml.safe_load(cargar_texto("campaña.yml"))
        self.ssh = json.loads(cargar_texto("alerta_ssh_vp.json").strip())
        self.auditor = json.loads(cargar_texto("alerta_auditor.json").strip())

    def _reg(self, cruda):
        return esquema.normalizar_alerta(cruda, "2026-08-31-fuerzabruta")

    def test_actividad_del_auditor_es_propia(self):
        r = etiquetar.etiquetar(self._reg(self.auditor), self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "PROPIA")

    def test_fuerza_bruta_contra_servicio_expuesto_es_vp(self):
        r = etiquetar.etiquetar(self._reg(self.ssh), self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "VP")
        self.assertEqual(r["etiqueta_por"], "regla")

    def test_login_de_admin_declarado_es_fp(self):
        # mismo servicio expuesto, pero origen legítimo declarado -> FP, no VP
        admin = json.loads(cargar_texto("alerta_admin_fp.json").strip())
        r = etiquetar.etiquetar(self._reg(admin), self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "FP")

    def test_familia_fuera_del_caso_de_uso_es_no_soportada(self):
        reg = self._reg(self.ssh)
        reg["familia"] = "plataforma"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "no_soportada")

    def test_nodo_gris_sin_resolucion_es_pendiente(self):
        reg = self._reg(self.ssh)
        reg["activo"] = "nodo-fantasma"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "PENDIENTE")

    def test_nodo_gris_con_resolucion_humana(self):
        reg = self._reg(self.ssh)
        reg["activo"] = "nodo-fantasma"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {reg["id_alerta"]: "FP"})
        self.assertEqual(r["etiqueta"], "FP")
        self.assertEqual(r["etiqueta_por"], "humano")
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `python3 -m unittest lab.dataset.tests.test_etiquetar.TestEtiquetar -v`
Expected: FAIL con `AttributeError: module 'lab.dataset.etiquetar' has no attribute 'etiquetar'`

- [ ] **Step 3: Implementación mínima**

```python
# añadir a lab/dataset/etiquetar.py
FAMILIAS_SOPORTADAS = {
    "acceso_credenciales", "reconocimiento", "servicio_expuesto", "explotacion_conocida",
}

def _ips_auditor(ficha):
    return set((ficha.get("auditor") or {}).get("ips", []))

def _ips_legitimas(ficha):
    return set((ficha.get("legitimos") or {}).get("ips", []))

def _con(registro, etiqueta, por, postura):
    r = dict(registro)
    r["etiqueta"] = etiqueta
    r["etiqueta_por"] = por
    r["postura_activo"] = postura
    r["particion"] = None  # la puebla Task 7 desde particion.yml
    return r

def etiquetar(registro, hallazgos, ficha, resoluciones):
    # 1. ¿Actividad de nuestro propio auditor?
    if registro.get("origen_ip") in _ips_auditor(ficha):
        return _con(registro, "PROPIA", "regla", None)
    # 2. ¿Dentro del caso de uso acotado?
    if registro.get("familia") not in FAMILIAS_SOPORTADAS:
        return _con(registro, "no_soportada", "regla", None)
    # 2b. ¿Origen administrativo legítimo declarado? -> falso positivo.
    # Es la misma señal que un ataque sobre un servicio expuesto; lo que la
    # separa es que el origen es administración normal (FP dominante del dominio).
    if registro.get("origen_ip") in _ips_legitimas(ficha):
        return _con(registro, "FP", "regla", None)
    # 3. ¿El servicio atacado existe en el nodo?
    postura = postura_de(hallazgos, registro.get("activo"), registro.get("servicio"))
    if postura is None:  # caso gris
        r = resoluciones.get(registro.get("id_alerta"))
        if r:
            return _con(registro, r, "humano", None)
        return _con(registro, "PENDIENTE", "regla", None)
    etq = "VP" if postura["expuesto"] else "FP"
    return _con(registro, etq, "regla", postura)
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

Run: `python3 -m unittest lab.dataset.tests.test_etiquetar -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add lab/dataset/etiquetar.py lab/dataset/tests/test_etiquetar.py
git commit -m "Implementar el arbol de decision de etiquetado (PROPIA/no_soportada/VP/FP/PENDIENTE)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: CLI de normalización

**Files:**
- Create: `lab/dataset/normalizar.py`
- Test: `lab/dataset/tests/test_normalizar.py`

**Interfaces:**
- Consumes: `normalizar_alerta` (Task 3).
- Produces: `normalizar_fichero(ruta_alerts: str, campaña: str) -> list[dict]` — lee un `alerts.json` (una alerta JSON por línea, tolera líneas vacías o corruptas saltándolas) y devuelve la lista de registros normalizados. Ejecutable como CLI: `python3 -m lab.dataset.normalizar <alerts.json> <campaña> <salida.jsonl>`.

- [ ] **Step 1: Escribir el test que falla**

```python
# lab/dataset/tests/test_normalizar.py
import os, tempfile, unittest
from lab.dataset import normalizar

FX = os.path.join(os.path.dirname(__file__), "fixtures")

class TestNormalizarFichero(unittest.TestCase):
    def test_lee_alertas_y_normaliza(self):
        # un fichero con la alerta VP y una línea basura que debe ignorarse
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(open(os.path.join(FX, "alerta_ssh_vp.json"), encoding="utf-8").read().strip() + "\n")
            f.write("línea corrupta no-json\n")
            ruta = f.name
        regs = normalizar.normalizar_fichero(ruta, "camp-x")
        os.unlink(ruta)
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["campaña"], "camp-x")
        self.assertEqual(regs[0]["activo"], "objetivo-vuln")
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `python3 -m unittest lab.dataset.tests.test_normalizar -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementación mínima**

```python
# lab/dataset/normalizar.py
"""CLI: alerts.json crudo -> registros normalizados (una etapa de la tubería)."""
import json, sys
from lab.dataset import esquema

def normalizar_fichero(ruta_alerts, campaña):
    regs = []
    with open(ruta_alerts, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                cruda = json.loads(linea)
            except json.JSONDecodeError:
                continue  # línea corrupta: se salta, no rompe el fichero (formato JSONL)
            regs.append(esquema.normalizar_alerta(cruda, campaña))
    return regs

def main(argv):
    ruta, campaña, salida = argv[1], argv[2], argv[3]
    regs = normalizar_fichero(ruta, campaña)
    with open(salida, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(regs)} alertas normalizadas -> {salida}")

if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

Run: `python3 -m unittest lab.dataset.tests.test_normalizar -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lab/dataset/normalizar.py lab/dataset/tests/test_normalizar.py
git commit -m "CLI de normalizacion: alerts.json crudo a JSONL normalizado

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Orquestador `construir` con partición

**Files:**
- Create: `lab/dataset/construir.py`
- Create: `lab/dataset/particion.yml`
- Create: `lab/dataset/resoluciones.yml`
- Test: `lab/dataset/tests/test_construir.py`

**Interfaces:**
- Consumes: `normalizar_alerta` (Task 3), `etiquetar` (Task 5).
- Produces: `construir(campañas: list[dict], particion_map: dict, resoluciones: dict) -> list[dict]` — donde cada elemento de `campañas` es `{"alertas": [cruda,...], "hallazgos": dict, "ficha": dict}`. Devuelve todos los registros etiquetados con el campo `particion` poblado desde `particion_map` (`{id_campaña: "entrenamiento"|"evaluacion"}`).

- [ ] **Step 1: Crear los ficheros de datos con su plantilla comentada**

`lab/dataset/particion.yml`:
```yaml
# Reparto A PRIORI de campañas. Se fija ANTES de entrenar y NO se toca al ver
# resultados: elegir la partición mirando los números contamina la evaluación.
# ~80/20 medido en alertas, no en número de campañas. Estratificado: cada familia
# y ambas etiquetas VP y FP presentes en los dos lados; evaluación DEBE tener FP.
entrenamiento: []
evaluacion: []
```

`lab/dataset/resoluciones.yml`:
```yaml
# Decisiones humanas sobre alertas que la regla marcó PENDIENTE (caso gris).
# Clave: id_alerta de Wazuh. Valor: VP | FP | PROPIA | no_soportada.
# Queda versionado para que el ground truth sea auditable (etiqueta_por=humano).
{}
```

- [ ] **Step 2: Escribir el test que falla**

```python
# lab/dataset/tests/test_construir.py
import json, os, unittest, yaml
from lab.dataset import construir

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def texto(n):
    return open(os.path.join(FX, n), encoding="utf-8").read()

class TestConstruir(unittest.TestCase):
    def test_puebla_particion_y_etiqueta(self):
        campaña = {
            "alertas": [json.loads(texto("alerta_ssh_vp.json").strip())],
            "hallazgos": json.loads(texto("hallazgos.json")),
            "ficha": yaml.safe_load(texto("campaña.yml")),
        }
        regs = construir.construir(
            [campaña],
            particion_map={"2026-08-31-fuerzabruta": "evaluacion"},
            resoluciones={},
        )
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["etiqueta"], "VP")
        self.assertEqual(regs[0]["particion"], "evaluacion")
```

- [ ] **Step 3: Ejecutar el test y verificar que falla**

Run: `python3 -m unittest lab.dataset.tests.test_construir -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 4: Implementación mínima**

```python
# lab/dataset/construir.py
"""Orquestador: normaliza + etiqueta + puebla la partición -> etiquetado.jsonl."""
import json, os, sys, yaml
from lab.dataset import esquema, etiquetar as etq

def construir(campañas, particion_map, resoluciones):
    salida = []
    for c in campañas:
        ficha = c["ficha"]
        cid = ficha.get("id")
        parte = particion_map.get(cid)
        for cruda in c["alertas"]:
            reg = esquema.normalizar_alerta(cruda, cid)
            reg = etq.etiquetar(reg, c["hallazgos"], ficha, resoluciones)
            reg["particion"] = parte
            salida.append(reg)
    return salida

def _cargar_campaña(dir_camp):
    with open(os.path.join(dir_camp, "campaña.yml"), encoding="utf-8") as f:
        ficha = yaml.safe_load(f)
    with open(os.path.join(dir_camp, "hallazgos.json"), encoding="utf-8") as f:
        hallazgos = json.load(f)
    alertas = []
    with open(os.path.join(dir_camp, "alerts.json"), encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if l:
                try:
                    alertas.append(json.loads(l))
                except json.JSONDecodeError:
                    continue
    return {"alertas": alertas, "hallazgos": hallazgos, "ficha": ficha}

def main(argv):
    raiz_campañas, particion_yml, resoluciones_yml, salida = argv[1:5]
    with open(particion_yml, encoding="utf-8") as f:
        pobj = yaml.safe_load(f) or {}
    particion_map = {}
    for cid in pobj.get("entrenamiento", []) or []:
        particion_map[cid] = "entrenamiento"
    for cid in pobj.get("evaluacion", []) or []:
        particion_map[cid] = "evaluacion"
    with open(resoluciones_yml, encoding="utf-8") as f:
        resoluciones = yaml.safe_load(f) or {}
    campañas = []
    for nombre in sorted(os.listdir(raiz_campañas)):
        d = os.path.join(raiz_campañas, nombre)
        if os.path.isdir(d):
            campañas.append(_cargar_campaña(d))
    regs = construir(campañas, particion_map, resoluciones)
    with open(salida, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    pend = sum(1 for r in regs if r["etiqueta"] == "PENDIENTE")
    print(f"{len(regs)} alertas etiquetadas -> {salida}  ({pend} PENDIENTE por resolver a mano)")

if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 5: Ejecutar el test y verificar que pasa**

Run: `python3 -m unittest lab.dataset.tests.test_construir -v`
Expected: PASS

- [ ] **Step 6: Ejecutar toda la batería**

Run: `python3 -m unittest discover -s lab/dataset/tests -v`
Expected: PASS (todas las clases)

- [ ] **Step 7: Commit**

```bash
git add lab/dataset/construir.py lab/dataset/particion.yml lab/dataset/resoluciones.yml lab/dataset/tests/test_construir.py
git commit -m "Orquestador construir: normaliza, etiqueta y puebla la particion

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Generador de campañas `campana.sh`

**Files:**
- Create: `lab/scripts/campana.sh`

**Interfaces:**
- Produces: un directorio `lab/campañas/<id>/` con `alerts.json` (congelado del contenedor), `campaña.yml` (ficha con ataques y datos del auditor) y `hallazgos.json` (invocando a `auditar.sh`, Task 9). Validado ejecutándolo contra el laboratorio en vivo, no con unittest (es E/S contra Docker).

- [ ] **Step 1: Escribir el script**

```sh
#!/bin/sh
# Genera una campaña de actividad REAL contra el laboratorio y la congela en disco.
#
#   sh lab/scripts/campana.sh <id-campaña>
#
# Lanza ataques reales (no inyección sintética) que dejan rastro en auth.log y
# llegan a Wazuh por el reenvío. Congela alerts.json fuera del contenedor ANTES
# de cualquier destroy, porque en Containerlab el contenedor es efímero.
set -e
ID="${1:?uso: sh lab/scripts/campana.sh <id-campaña>}"
HERE=$(dirname "$0")
DEST="$HERE/../campañas/$ID"
WZ=clab-red-cliente-wazuh
AUDITOR=clab-red-cliente-auditor
ATACANTE=clab-red-cliente-puesto
AUDITOR_IP=$(docker inspect $AUDITOR --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
mkdir -p "$DEST"

# Marca temporal de inicio, para la ficha
INICIO=$(date -u +%Y-%m-%dT%H:%M:%S+0000)

# El ATAQUE se lanza desde 'puesto' (un nodo de la LAN comprometido), NO desde el
# auditor. Es deliberado: el auditor es nuestro instrumento de medida y su tráfico
# se etiqueta PROPIA; si atacara desde él, todos los ataques reales caerían como
# PROPIA y se descartarían. 'puesto' representa un atacante interno legítimo.
echo "== Preparando el nodo atacante (puesto) =="
docker exec $ATACANTE sh -c 'command -v ssh >/dev/null 2>&1 || apk add --no-cache openssh-client >/dev/null 2>&1' || true

echo "== Fuerza bruta SSH real desde puesto contra objetivo-vuln =="
# El sshd de Metasploitable es de 2007: hay que rebajar los algoritmos del
# cliente o la conexión muere antes de la fase de contraseña y no deja rastro.
docker exec $ATACANTE sh -c '
  for i in $(seq 1 10); do
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
        -o PreferredAuthentications=password \
        root@192.168.1.30 true 2>/dev/null || true
  done'

echo "== Logins fallidos BENIGNOS desde el admin declarado (borde) -> FP =="
# Un administrador legitimo que se equivoca de contrasena produce la MISMA senal
# que un ataque contra un servicio expuesto. Lo que lo separa es el origen. Su IP
# se declara en la ficha (legitimos), y el etiquetado lo marca FP.
ADMIN=clab-red-cliente-borde
docker exec $ADMIN sh -c 'command -v ssh >/dev/null 2>&1 || apk add --no-cache openssh-client >/dev/null 2>&1' || true
docker exec $ADMIN sh -c '
  for i in 1 2 3; do
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
        -o PreferredAuthentications=password \
        admin@192.168.1.30 true 2>/dev/null || true
  done'
ADMIN_IP=192.168.1.1

echo "== Escaneo de puertos (desde el auditor: sera PROPIA) =="
docker exec $AUDITOR nmap -Pn --top-ports 50 192.168.1.30 >/dev/null 2>&1 || true

echo "== esperando a que Wazuh procese =="
sleep 6

echo "== Congelando alerts.json =="
docker exec $WZ sh -c 'cat /var/ossec/logs/alerts/alerts.json' > "$DEST/alerts.json"

echo "== Escribiendo la ficha de campaña =="
cat > "$DEST/campaña.yml" <<YML
id: $ID
fecha: $(date -u +%Y-%m-%d)
ataques:
  - escenario: fuerza bruta SSH
    objetivo: objetivo-vuln
    desde: puesto
  - escenario: logins fallidos benignos (admin legitimo)
    objetivo: objetivo-vuln
    desde: borde
  - escenario: escaneo de puertos
    objetivo: objetivo-vuln
    desde: auditor
auditor:
  ips: ["$AUDITOR_IP"]
  cuando: "$INICIO"
legitimos:
  ips: ["$ADMIN_IP"]
YML

echo "== Auditando la postura (hallazgos.json) =="
sh "$HERE/auditar.sh" "$DEST/hallazgos.json"

N=$(grep -c . "$DEST/alerts.json" 2>/dev/null || echo 0)
echo "== Campaña '$ID' congelada en $DEST ($N alertas) =="
```

- [ ] **Step 2: Hacerlo ejecutable**

```bash
chmod +x lab/scripts/campana.sh
```

- [ ] **Step 3: Ejecutar contra el laboratorio en vivo y verificar la salida**

Run:
```bash
sh lab/lab.sh up
sh lab/scripts/campana.sh prueba-01
```
Expected: crea `lab/campañas/prueba-01/` con `alerts.json` no vacío, `campaña.yml` y `hallazgos.json`. Verifica:
```bash
test -s lab/campañas/prueba-01/alerts.json && echo "alerts OK"
python3 -c "import yaml;d=yaml.safe_load(open('lab/campañas/prueba-01/campaña.yml'));assert d['auditor']['ips'];print('ficha OK', d['id'])"
```

- [ ] **Step 4: Ignorar las campañas de prueba en git (pero versionar las reales luego a mano)**

Añade a `.gitignore`:
```
lab/campañas/prueba-*/
```

- [ ] **Step 5: Commit**

```bash
git add lab/scripts/campana.sh .gitignore
git commit -m "Generador de campanas: ataques reales congelados en disco

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Auditor normalizado `auditar.sh`

**Files:**
- Create: `lab/scripts/auditar.sh`

**Interfaces:**
- Consumes: nada.
- Produces: escribe en la ruta que recibe como argumento un `hallazgos.json` con el esquema `{"version_herramienta", "timestamp", "nodos": {nodo: [{"puerto","servicio","estado"}]}}` — el mismo que consume `postura_de` (Task 4) y el fixture de Task 1. Validado ejecutándolo contra el laboratorio.

- [ ] **Step 1: Escribir el script**

```sh
#!/bin/sh
# Escanea los nodos del plano de datos con Nmap y emite hallazgos.json normalizado.
#
#   sh lab/scripts/auditar.sh <salida.json>
#
# Registra la versión de Nmap: si el escáner cambia entre campañas, los
# resultados dejan de ser comparables (RF-09).
set -e
SALIDA="${1:?uso: sh lab/scripts/auditar.sh <salida.json>}"
AUDITOR=clab-red-cliente-auditor
VER=$(docker exec $AUDITOR nmap --version 2>/dev/null | head -1 | sed 's/ (.*//')
TS=$(date -u +%Y-%m-%dT%H:%M:%S+0000)

# Nodos del plano de datos y su IP
NODOS="objetivo-vuln:192.168.1.30 puesto:192.168.1.10 iot:192.168.1.20 borde:192.168.1.1"

python3 - "$SALIDA" "$VER" "$TS" $NODOS <<'PY'
import subprocess, sys, json, re
salida, ver, ts = sys.argv[1], sys.argv[2], sys.argv[3]
nodos = {}
for par in sys.argv[4:]:
    nombre, ip = par.split(":")
    out = subprocess.run(
        ["docker","exec","clab-red-cliente-auditor","nmap","-Pn","--top-ports","100",ip],
        capture_output=True, text=True).stdout
    puertos = []
    for m in re.finditer(r"^(\d+)/tcp\s+(\S+)\s+(\S+)", out, re.M):
        puertos.append({"puerto": int(m.group(1)), "servicio": m.group(3), "estado": m.group(2)})
    nodos[nombre] = puertos
json.dump({"version_herramienta": ver, "timestamp": ts, "nodos": nodos},
          open(salida,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"hallazgos -> {salida} ({sum(len(v) for v in nodos.values())} servicios)")
PY
```

- [ ] **Step 2: Hacerlo ejecutable**

```bash
chmod +x lab/scripts/auditar.sh
```

- [ ] **Step 3: Ejecutar contra el laboratorio y verificar**

Run:
```bash
sh lab/scripts/auditar.sh /tmp/hallazgos-prueba.json
python3 -c "import json;h=json.load(open('/tmp/hallazgos-prueba.json'));assert any(s['servicio']=='ssh' for s in h['nodos']['objetivo-vuln']);print('OK ssh en objetivo-vuln, nmap', h['version_herramienta'])"
```
Expected: `objetivo-vuln` lista `ssh` abierto y la versión de Nmap está registrada.

- [ ] **Step 4: Commit**

```bash
git add lab/scripts/auditar.sh
git commit -m "Auditor normalizado: nmap a hallazgos.json con version registrada

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Ejecución de extremo a extremo y documentación del dataset

**Files:**
- Create: `lab/docs/dataset.md`
- Modify: `lab/README.md` (añadir `dataset/` y los dos scripts al índice)
- Modify: `documentacion/03-fase3-entorno-de-pruebas/README.md` (marcar el entregable de datos)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: `lab/dataset/etiquetado.jsonl` real y su documentación (origen, volumen, distribución).

- [ ] **Step 1: Generar dos campañas reales y construir el dataset**

Run:
```bash
sh lab/lab.sh up
sh lab/scripts/campana.sh 2026-08-31-entrenamiento
# reinicia el estado para que la segunda campaña sea distinta
sh lab/lab.sh down && sh lab/lab.sh up
sh lab/scripts/campana.sh 2026-08-31-evaluacion
```

- [ ] **Step 2: Rellenar `particion.yml` a priori**

Edita `lab/dataset/particion.yml`:
```yaml
entrenamiento:
  - 2026-08-31-entrenamiento
evaluacion:
  - 2026-08-31-evaluacion
```

- [ ] **Step 3: Construir el dataset**

Run:
```bash
python3 -m lab.dataset.construir lab/campañas lab/dataset/particion.yml lab/dataset/resoluciones.yml lab/dataset/etiquetado.jsonl
```
Expected: imprime cuántas alertas etiquetadas y cuántas `PENDIENTE`.

- [ ] **Step 4: Resolver los PENDIENTE a mano (si los hay)**

Lista los pendientes y decide cada uno:
```bash
python3 -c "import json;[print(r['id_alerta'], r['activo'], r['servicio'], r['evento_crudo'][:60]) for r in map(json.loads, open('lab/dataset/etiquetado.jsonl',encoding='utf-8')) if r['etiqueta']=='PENDIENTE']"
```
Añade cada decisión a `lab/dataset/resoluciones.yml` (`id_alerta: VP|FP|PROPIA|no_soportada`) y reconstruye (Step 3). Repite hasta que no queden `PENDIENTE`.

- [ ] **Step 5: Verificar que el dataset cumple el criterio de cierre**

Run:
```bash
python3 - <<'PY'
import json, collections
regs = [json.loads(l) for l in open("lab/dataset/etiquetado.jsonl", encoding="utf-8")]
et = collections.Counter(r["etiqueta"] for r in regs)
pa = collections.Counter(r["particion"] for r in regs)
print("total:", len(regs)); print("etiquetas:", dict(et)); print("partición:", dict(pa))
assert et["PENDIENTE"] == 0, "quedan PENDIENTE sin resolver"
assert et["VP"] > 0 and et["FP"] > 0, "faltan VP o FP; evaluación necesita ambos"
assert pa.get("evaluacion", 0) > 0 and pa.get("entrenamiento", 0) > 0, "partición vacía"
print("CIERRE OK")
PY
```
Expected: `CIERRE OK`. Si `FP == 0`, los logins benignos del admin declarado (`borde` → `192.168.1.1`) no llegaron a Wazuh: comprueba que `borde` tiene cliente SSH y que su IP está en `legitimos` de la ficha, y regenera la campaña.

- [ ] **Step 6: Documentar el dataset**

Crea `lab/docs/dataset.md` con: qué es, cómo se genera (`campana.sh` → `construir`), el esquema de los 16 campos (enlazando a la spec §5), la distribución de etiquetas que imprimió el Step 5, y la política de partición. Enlaza desde `lab/README.md` (sección Documentos) y actualiza el estado en `documentacion/03-fase3-entorno-de-pruebas/README.md` marcando el dataset como entregado.

- [ ] **Step 7: Commit**

```bash
git add lab/dataset/etiquetado.jsonl lab/dataset/particion.yml lab/dataset/resoluciones.yml lab/campañas/ lab/docs/dataset.md lab/README.md documentacion/03-fase3-entorno-de-pruebas/README.md
git commit -m "Cerrar la Fase 3: dataset de alertas etiquetado y documentado

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas de ejecución

- **El laboratorio debe estar arriba** (`sh lab/lab.sh up`, plano de datos OK) para las tareas 1, 8, 9 y 10. Las tareas 2–7 son Python puro con fixtures y no necesitan el laboratorio.
- **Ejecutar los módulos desde la raíz del repo** (`python3 -m lab.dataset.construir ...`), no desde dentro de `lab/dataset/`, para que los imports `lab.dataset.*` resuelvan. Requiere que exista `lab/__init__.py` — si no está, créalo vacío en la Task 1.
- **Toda la batería de tests:** `python3 -m unittest discover -s lab/dataset/tests`.
