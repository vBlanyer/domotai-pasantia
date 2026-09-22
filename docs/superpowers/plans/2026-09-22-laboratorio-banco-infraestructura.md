# Laboratorio del banco — Plan 1: infraestructura

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levantar en Containerlab la red del banco de `bancario.yml`. Tendrá servicios con dependencias reales, un monitor de salud, syslog hacia Wazuh y un conector que ejecuta desde el nodo de gestión del banco. También se verificarán en vivo los supuestos del catálogo (fase 0).

**Architecture:** Una única fuente de verdad (`lab/banco/red.py`) describe los nodos, las IPs, los servicios y sus dependencias reales. De ella salen:
- los comandos de arranque;
- los argumentos del monitor;
- los tests de coherencia con el perfil y la topología.

Tres módulos Python autónomos (solo biblioteca estándar) se copian a la imagen `banco-nodo`:
- `servicio.py`: servicio HTTP con `/salud` transitiva;
- `monitor.py`: línea de tiempo de salud;
- `reenviador.py`: logs a syslog para Wazuh.

`banco.sh` orquesta el despliegue. El prototipo solo cambia en un punto: el conector se parametriza por entorno.

**Tech Stack:** Python 3 (biblioteca estándar; PyYAML solo en los tests), `unittest`, Containerlab, Docker, Alpine, Wazuh 4.14.7 (`lab/scripts/wazuh-run.sh`).

**Spec:** `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md` (§5, §7, §8 plan 1).

## Global Constraints

- Python 3 con la biblioteca estándar y PyYAML; tests con `unittest`: `PYTHONPATH=. python3 -m unittest discover -s <dir> -t .`. Sin pip, venv ni pytest.
- Suites que siempre deben seguir en verde: `prototipo/tests`, `evaluacion/tests` y `lab/dataset/tests`, más la nueva `lab/banco/tests`.
- Commits que terminan exactamente en `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. Rama `feature/laboratorio-banco`. Nunca push.
- Ataques solo dentro del laboratorio aislado de Containerlab; todo local (RNF-01). El nodo `internet` no tiene salida real.
- No se modifican el plan de trabajo, el roadmap, el informe `.tex`, los documentos de las Fases 1–4 ni `informe-evaluacion.md`.
- La red pequeña (`red-cliente`) y su conector siguen funcionando igual: todo parámetro nuevo tiene como valor por defecto el comportamiento actual.
- Los nombres de los nodos son los del perfil: `web-banking`, `api-movil`, `swift-alliance`, `middleware`, `core-db`, `hsm`, `mdr-siem`, `atm`, `taquilla`, más `fw-core`, `fw-edge`, `internet`, `auditor` y `sw-soc`. Los contenedores quedan como `clab-banco-<nodo>`.
- **Puertos nominales** (servicios HTTP que imitan el puerto real): `core-db` 1521, `hsm` 9000, `middleware` 8443, `web-banking` 443 y 80, `api-movil` 443, `swift-alliance` 48002, `atm` 8080.
- **Dependencias reales:**
  - `web-banking` → `middleware`;
  - `api-movil` → `middleware`;
  - `middleware` → `core-db`, `hsm`;
  - `swift-alliance` → `hsm`;
  - `atm` → `middleware`, **no declarada en el perfil, a propósito** (caso K3).

## Decisiones del plan (rulings sobre el spec)

- **R1.** La fase 0 del spec («verificaciones previas») depende de que el laboratorio exista. Se ejecuta como **Task 8**, después de construirlo. Solo el conector (H3) va primero, en la Task 1. Las verificaciones no cambian el prototipo: registran resultados en `lab/banco/verificaciones.md`. (22/09/2026: el plan 2, que iba a consumir ese registro, no se ejecutó — decisión del usuario; ver spec §8/§10.)
- **R2.** El auditor escanea hoy `--top-ports 100`, que no incluye el 1521. Se parametriza la lista de puertos (Task 1) y el banco la pasa explícita.
- **R3.** El formato con el que Wazuh decodifica los logs web por syslog no está verificado. `reenviador.py` construye la línea syslog con una función pura y probada. La Task 8 comprueba qué detecta Wazuh; si no detecta el web, D5 queda marcado con su límite (el spec lo permite).

## File Structure

| Fichero | Responsabilidad |
|---|---|
| `prototipo/conector.py` (modificar) | Nodo de gestión configurable: `TRIAJE_NODO_GESTION` |
| `prototipo/tests/test_conector.py` (modificar) | Tests del parámetro |
| `lab/scripts/auditor.py` (modificar) | `argumentos_nmap(ip, puertos)` y puertos configurables |
| `lab/scripts/auditar.sh` (modificar) | Auditor, nodos y puertos por entorno |
| `lab/scripts/aprovisionar-minimo-privilegio.sh` (modificar) | Nodo de gestión por entorno |
| `lab/dataset/tests/test_auditor.py` (modificar o crear) | Test de `argumentos_nmap` |
| `lab/banco/__init__.py`, `lab/banco/tests/__init__.py` | Paquetes |
| `lab/banco/red.py` | Fuente única: nodos, IPs, servicios y dependencias; CLI para `banco.sh` |
| `lab/banco/servicio.py` | Servicio HTTP genérico con `/salud` transitiva y registro de accesos |
| `lab/banco/monitor.py` | Sondeo de salud y línea de tiempo JSONL |
| `lab/banco/reenviador.py` | Sigue ficheros de log y los envía como syslog UDP a Wazuh |
| `lab/banco/Dockerfile`, `lab/banco/construir-imagen.sh` | Imagen `banco-nodo:1` |
| `lab/topologias/banco.clab.yml` | La red del banco |
| `lab/banco/banco.sh` | `up`, `down`, `status`, `test` y `cascada` del banco |
| `lab/lab.sh` (modificar) | `sh lab/lab.sh up banco` delega en `banco.sh`; guarda contra dos redes a la vez |
| `lab/banco/tests/test_*.py` | Tests de los módulos y de coherencia red ↔ perfil ↔ topología |
| `prototipo/perfiles/bancario.yml` (modificar) | Puertos de `hsm` y `swift-alliance`; omisión de `atm` documentada |
| `lab/banco/verificaciones.md` | Resultado de la fase 0, caso por caso |
| `lab/banco/README.md` | Cómo levantar y usar el banco |

---

### Task 1: Conector y auditor parametrizables (H3, R2)

**Files:**
- Modify: `prototipo/conector.py:60-64` y `:96-101`
- Modify: `prototipo/tests/test_conector.py` (añadir la clase `TestNodoGestion` al final)
- Modify: `lab/scripts/auditor.py:45-50`
- Modify: `lab/scripts/auditar.sh:13-19`
- Modify: `lab/scripts/aprovisionar-minimo-privilegio.sh:22`
- Modify: `lab/dataset/tests/test_auditor.py` (import del módulo y nueva clase)

**Interfaces:**
- Produces: `conector.nodo_gestion() -> str` (el valor de `TRIAJE_NODO_GESTION` o `"clab-red-cliente-auditor"`); `auditor.argumentos_nmap(ip: str, puertos: str | None) -> list[str]`. Entorno: `TRIAJE_NODO_GESTION`, `TRIAJE_AUDITOR`, `AUDITOR_NODOS`, `AUDITOR_PUERTOS`.

- [ ] **Step 1: Tests que fallan**

Al final de `prototipo/tests/test_conector.py`:

```python
class TestNodoGestion(unittest.TestCase):
    """H3: el nodo desde el que ejecuta el conector es configurable; por defecto, el de la red pequeña."""
    def test_por_defecto_el_auditor_de_la_red_pequena(self):
        import os
        from unittest import mock
        from prototipo import conector
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_NODO_GESTION", None)
            self.assertEqual(conector.nodo_gestion(), "clab-red-cliente-auditor")

    def test_configurable_por_entorno(self):
        import os
        from unittest import mock
        from prototipo import conector
        with mock.patch.dict(os.environ, {"TRIAJE_NODO_GESTION": "clab-banco-mdr-siem"}):
            self.assertEqual(conector.nodo_gestion(), "clab-banco-mdr-siem")

    def test_el_ssh_se_lanza_en_el_nodo_configurado(self):
        import os, subprocess
        from unittest import mock
        from prototipo import conector
        visto = {}
        def falso_run(args, **kw):
            visto["args"] = args
            return subprocess.CompletedProcess(args, 0, "ok", "")
        with mock.patch.dict(os.environ, {"TRIAJE_NODO_GESTION": "clab-banco-mdr-siem"}), \
             mock.patch("subprocess.run", falso_run):
            conector._ssh_en_auditor("true")
        self.assertEqual(visto["args"][:3], ["docker", "exec", "clab-banco-mdr-siem"])
```

`lab/dataset/tests/test_auditor.py` ya existe: añade la línea `from lab.scripts import auditor` junto a sus imports y la clase `TestArgumentosNmap` antes del bloque `if __name__`:

```python
import unittest
from lab.scripts import auditor


class TestArgumentosNmap(unittest.TestCase):
    def test_por_defecto_top_100(self):
        self.assertEqual(auditor.argumentos_nmap("10.0.0.1", None),
                         ["nmap", "-Pn", "--top-ports", "100", "10.0.0.1"])

    def test_lista_explicita_de_puertos(self):
        # R2: el 1521 no esta en el top-100; el banco pasa la lista.
        self.assertEqual(auditor.argumentos_nmap("10.50.0.10", "22,1521"),
                         ["nmap", "-Pn", "-p", "22,1521", "10.50.0.10"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Comprobar que fallan**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_conector lab.dataset.tests.test_auditor 2>&1 | tail -3`
Expected: FAILED (errores por `nodo_gestion` y `argumentos_nmap` inexistentes).

- [ ] **Step 3: Implementar**

En `prototipo/conector.py`, sustituye la línea `_AUDITOR = "clab-red-cliente-auditor"` y la función `_ssh_en_auditor` por:

```python
_AUDITOR = "clab-red-cliente-auditor"   # valor por defecto: la red pequena

def nodo_gestion():
    """Contenedor desde el que el conector lanza el SSH (el nodo de gestion del cliente). Por defecto
    el auditor de la red pequena; el banco usa TRIAJE_NODO_GESTION=clab-banco-mdr-siem (H3)."""
    return os.environ.get("TRIAJE_NODO_GESTION", _AUDITOR)

def _ssh_en_auditor(linea):
    import subprocess
    cp = subprocess.run(["docker", "exec", nodo_gestion(), "sh", "-c", linea], capture_output=True, text=True)
    return (cp.returncode, cp.stdout + cp.stderr)
```

Y en `_clave_aprovisionada`, cambia `_AUDITOR` por `nodo_gestion()`:

```python
        return subprocess.run(["docker", "exec", nodo_gestion(), "test", "-f", SSH_CLAVE],
                              capture_output=True).returncode == 0
```

En `lab/scripts/auditor.py`, sustituye `escanear_nodo` por:

```python
def argumentos_nmap(ip, puertos=None):
    """Orden de nmap para un nodo. Sin `puertos`, el top-100 de siempre; con ellos (p. ej. "22,1521"),
    exactamente esos: el top-100 no incluye puertos del banco como el 1521 (R2)."""
    if puertos:
        return ["nmap", "-Pn", "-p", puertos, ip]
    return ["nmap", "-Pn", "--top-ports", "100", ip]


def escanear_nodo(auditor, ip, puertos=None):
    r = subprocess.run(["docker", "exec", auditor] + argumentos_nmap(ip, puertos),
                       capture_output=True, text=True)
    return resultado_nodo(r.returncode, r.stdout)
```

y, en `main`, la llamada a `escanear_nodo` pasa a leer el entorno. Localiza `escanear_nodo(auditor, ip)` y cámbiala por:

```python
escanear_nodo(auditor, ip, os.environ.get("AUDITOR_PUERTOS"))
```

Añade `import os` a los imports de `auditor.py`.

En `lab/scripts/auditar.sh`, sustituye las líneas de `AUDITOR=` y `NODOS=` por:

```sh
AUDITOR="${TRIAJE_AUDITOR:-clab-red-cliente-auditor}"
# Nodos del plano de datos y su IP (el banco los pasa por AUDITOR_NODOS; ver lab/banco/banco.sh)
NODOS="${AUDITOR_NODOS:-objetivo-vuln:192.168.1.30 puesto:192.168.1.10 iot:192.168.1.20 borde:192.168.1.1}"
```

En `lab/scripts/aprovisionar-minimo-privilegio.sh`, sustituye `AUDITOR=clab-red-cliente-auditor` por:

```sh
AUDITOR="${TRIAJE_NODO_GESTION:-clab-red-cliente-auditor}"
```

- [ ] **Step 4: Comprobar que pasan y que no hay regresión**

Run: `for d in prototipo/tests evaluacion/tests lab/dataset/tests; do PYTHONPATH=. python3 -m unittest discover -s $d -t . 2>&1 | tail -1; done`
Expected: `OK` en las tres (prototipo 430, dataset 39 o más).

- [ ] **Step 5: Commit**

```bash
git add prototipo/conector.py prototipo/tests/test_conector.py lab/scripts/auditor.py lab/scripts/auditar.sh lab/scripts/aprovisionar-minimo-privilegio.sh lab/dataset/tests/test_auditor.py
git commit -m "feat(conector): nodo de gestion y auditor configurables por entorno (H3, R2)

Por defecto, la red pequena; el laboratorio del banco ejecuta desde clab-banco-mdr-siem y
escanea sus puertos nominales (el top-100 no incluye el 1521).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Fuente única de la red (`red.py`) y coherencia con el perfil

**Files:**
- Create: `lab/banco/__init__.py` (vacío), `lab/banco/tests/__init__.py` (vacío)
- Create: `lab/banco/red.py`
- Test: `lab/banco/tests/test_red.py`

**Interfaces:**
- Produces:
  - `red.NODOS: dict[str, dict]`, con `{"ip": str, "gw": str}` por nodo del plano de datos;
  - `red.SERVICIOS: dict[str, dict]`, con `{"puertos": list[int], "depende": list[str]}` (los nombres de nodo de los que depende);
  - `red.NO_DECLARADAS: set[tuple[str, str]]`, que es `{("atm", "middleware")}`;
  - `red.comando_servicio(nodo) -> str`;
  - `red.args_monitor() -> list[str]`, con elementos `"nombre=ip:puerto"`;
  - `red.nodos_auditor() -> str`, en formato `"nombre:ip ..."`;
  - `red.puertos_auditor() -> str`, en formato `"22,80,..."`.
  - CLI: `python3 -m lab.banco.red servicio <nodo>` | `monitor` | `nodos` | `puertos`.

- [ ] **Step 1: Test que falla**

`lab/banco/tests/test_red.py`:

```python
import os
import unittest
import yaml
from lab.banco import red

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PERFIL = yaml.safe_load(open(os.path.join(RAIZ, "prototipo", "perfiles", "bancario.yml"), encoding="utf-8"))


class TestCoherenciaConElPerfil(unittest.TestCase):
    def test_las_ips_del_laboratorio_son_las_del_perfil(self):
        for nombre, activo in PERFIL["activos"].items():
            self.assertIn(nombre, red.NODOS, nombre)
            self.assertEqual(red.NODOS[nombre]["ip"], activo["ip"], nombre)

    def test_toda_dependencia_declarada_existe_en_el_laboratorio(self):
        for nombre, activo in PERFIL["activos"].items():
            for dep in activo.get("depende_de") or []:
                self.assertIn(dep, red.SERVICIOS[nombre]["depende"], f"{nombre} -> {dep}")

    def test_la_unica_dependencia_no_declarada_es_la_de_k3(self):
        reales = {(n, d) for n, s in red.SERVICIOS.items() for d in s["depende"]}
        declaradas = {(n, d) for n, a in PERFIL["activos"].items() for d in (a.get("depende_de") or [])}
        self.assertEqual(reales - declaradas, red.NO_DECLARADAS)
        self.assertEqual(red.NO_DECLARADAS, {("atm", "middleware")})


class TestDerivados(unittest.TestCase):
    def test_comando_de_servicio_con_dependencias_por_ip(self):
        cmd = red.comando_servicio("middleware")
        self.assertIn("--nombre middleware", cmd)
        self.assertIn("--puerto 8443", cmd)
        self.assertIn("--depende 10.50.0.10:1521", cmd)
        self.assertIn("--depende 10.60.0.10:9000", cmd)

    def test_nodo_sin_servicio_no_tiene_comando(self):
        self.assertIsNone(red.comando_servicio("taquilla"))

    def test_monitor_vigila_todos_los_servicios(self):
        self.assertEqual(sorted(a.split("=")[0] for a in red.args_monitor()), sorted(red.SERVICIOS))
        self.assertIn("core-db=10.50.0.10:1521", red.args_monitor())

    def test_el_auditor_escanea_ssh_y_los_puertos_nominales(self):
        puertos = red.puertos_auditor().split(",")
        for p in ("22", "80", "443", "1521", "8080", "8443", "9000", "48002"):
            self.assertIn(p, puertos)
        self.assertIn("core-db:10.50.0.10", red.nodos_auditor().split())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Comprobar que falla**

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/banco/tests -t . 2>&1 | tail -3`
Expected: FAILED (ImportError de `lab.banco.red`).

- [ ] **Step 3: Implementar `lab/banco/red.py`**

```python
"""Fuente unica de la red del banco: nodos, IPs, servicios y dependencias REALES.

La topologia (lab/topologias/banco.clab.yml), el arranque (banco.sh), el monitor y el auditor salen
de aqui, y los tests comprueban que coincide con prototipo/perfiles/bancario.yml. La dependencia
atm -> middleware existe en el laboratorio y NO en el perfil, a proposito: es el caso K3
(dependencia no declarada) del catalogo.
"""
import sys

# Plano de datos: IP y puerta de enlace (fw-core en cada segmento). Mismas IPs que bancario.yml.
NODOS = {
    "web-banking":    {"ip": "10.10.0.10",  "gw": "10.10.0.1"},
    "api-movil":      {"ip": "10.20.0.10",  "gw": "10.20.0.1"},
    "swift-alliance": {"ip": "10.30.0.10",  "gw": "10.30.0.1"},
    "middleware":     {"ip": "10.40.0.10",  "gw": "10.40.0.1"},
    "core-db":        {"ip": "10.50.0.10",  "gw": "10.50.0.1"},
    "hsm":            {"ip": "10.60.0.10",  "gw": "10.60.0.1"},
    "mdr-siem":       {"ip": "10.100.0.10", "gw": "10.100.0.1"},
    "auditor":        {"ip": "10.100.0.20", "gw": "10.100.0.1"},
    "taquilla":       {"ip": "10.200.0.10", "gw": "10.200.0.1"},
    "atm":            {"ip": "10.210.0.10", "gw": "10.210.0.1"},
}

# Servicios HTTP nominales (el puerto imita el del servicio real) y de quien dependen DE VERDAD.
SERVICIOS = {
    "core-db":        {"puertos": [1521],     "depende": []},
    "hsm":            {"puertos": [9000],     "depende": []},
    "middleware":     {"puertos": [8443],     "depende": ["core-db", "hsm"]},
    "web-banking":    {"puertos": [443, 80],  "depende": ["middleware"]},
    "api-movil":      {"puertos": [443],      "depende": ["middleware"]},
    "swift-alliance": {"puertos": [48002],    "depende": ["hsm"]},
    "atm":            {"puertos": [8080],     "depende": ["middleware"]},
}

NO_DECLARADAS = {("atm", "middleware")}


def _destino(nodo):
    return f"{NODOS[nodo]['ip']}:{SERVICIOS[nodo]['puertos'][0]}"


def comando_servicio(nodo):
    """Linea que arranca el servicio del nodo, o None si el nodo no presta servicio."""
    s = SERVICIOS.get(nodo)
    if s is None:
        return None
    partes = ["python3 /opt/banco/servicio.py", f"--nombre {nodo}"]
    partes += [f"--puerto {p}" for p in s["puertos"]]
    partes += [f"--depende {_destino(d)}" for d in s["depende"]]
    partes.append("--registro /var/log/banco/access.log")
    return " ".join(partes)


def args_monitor():
    return [f"{n}={_destino(n)}" for n in sorted(SERVICIOS)]


def nodos_auditor():
    return " ".join(f"{n}:{NODOS[n]['ip']}" for n in sorted(NODOS) if n not in ("mdr-siem", "auditor"))


def puertos_auditor():
    puertos = {22} | {p for s in SERVICIOS.values() for p in s["puertos"]}
    return ",".join(str(p) for p in sorted(puertos))


def main(argv):
    orden = argv[0] if argv else ""
    if orden == "servicio" and len(argv) == 2:
        print(comando_servicio(argv[1]) or "")
    elif orden == "monitor":
        print(" ".join(args_monitor()))
    elif orden == "nodos":
        print(nodos_auditor())
    elif orden == "puertos":
        print(puertos_auditor())
    elif orden == "servicios":
        print(" ".join(sorted(SERVICIOS)))
    else:
        print("uso: python3 -m lab.banco.red servicio <nodo> | monitor | nodos | puertos | servicios")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Comprobar que pasa**

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/banco/tests -t . 2>&1 | tail -1`
Expected: `OK`.

Si `test_las_ips_del_laboratorio_son_las_del_perfil` falla porque el perfil no tiene la IP del auditor (10.100.0.20): es correcto que el test solo recorra `PERFIL["activos"]`, y el auditor no es un activo. No cambies el test.

- [ ] **Step 5: Commit**

```bash
git add lab/banco/__init__.py lab/banco/tests/__init__.py lab/banco/red.py lab/banco/tests/test_red.py
git commit -m "feat(banco): fuente unica de la red del banco, coherente con el perfil bancario

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Servicio con salud transitiva (`servicio.py`)

**Files:**
- Create: `lab/banco/servicio.py`
- Test: `lab/banco/tests/test_servicio.py`

**Interfaces:**
- Produces:
  - `servicio.comprobar_dependencias(dependencias: list[str], abrir=urllib.request.urlopen, plazo=1.0) -> list[str]`: las que fallan, en formato `"host:puerto"`;
  - `servicio.linea_acceso(ip, metodo, ruta, estado, tamano, agente, instante) -> str`: formato Apache *combined*;
  - `servicio.crear_servidor(nombre, puerto, dependencias, registrar) -> ThreadingHTTPServer`;
  - CLI: `python3 servicio.py --nombre N --puerto P [--puerto P2] [--depende host:puerto]... [--registro fichero]`.
- `/salud` responde 200 con `{"servicio", "estado": "ok", "falla": []}` o 503 con `"estado": "degradado"` y la lista de las dependencias que fallan. Como cada dependencia consulta a su vez su `/salud`, **la cascada es transitiva**. `/salud` no se registra en el log de accesos, para no inundar Wazuh con el sondeo del monitor. Cualquier otra ruta responde 200 y se registra.
- **Sin ciclos:** una dependencia circular haría que `/salud` se llamase a sí mismo indefinidamente. `red.py` no tiene ciclos y el test de coherencia del perfil lo cubre.

- [ ] **Step 1: Test que falla**

`lab/banco/tests/test_servicio.py`:

```python
import json
import threading
import unittest
import urllib.error
import urllib.request
from lab.banco import servicio


def _arrancar(nombre, dependencias, registro):
    srv = servicio.crear_servidor(nombre, 0, dependencias, registro.append)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"127.0.0.1:{srv.server_address[1]}"


def _salud(destino):
    try:
        with urllib.request.urlopen(f"http://{destino}/salud", timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class TestSaludTransitiva(unittest.TestCase):
    def setUp(self):
        self.registro, self.servidores = [], []

    def tearDown(self):
        for s in self.servidores:
            s.shutdown(); s.server_close()

    def _nuevo(self, nombre, deps=()):
        srv, destino = _arrancar(nombre, list(deps), self.registro)
        self.servidores.append(srv)
        return srv, destino

    def test_sin_dependencias_esta_sano(self):
        _, a = self._nuevo("core-db")
        self.assertEqual(_salud(a), (200, {"servicio": "core-db", "estado": "ok", "falla": []}))

    def test_la_caida_se_propaga_en_cadena(self):
        db, a = self._nuevo("core-db")
        _, b = self._nuevo("middleware", [a])
        _, c = self._nuevo("web-banking", [b])
        self.assertEqual(_salud(c)[0], 200)
        db.shutdown(); db.server_close(); self.servidores.remove(db)
        codigo, cuerpo = _salud(c)
        self.assertEqual(codigo, 503)
        self.assertEqual(cuerpo["falla"], [b])          # web-banking ve caer a middleware
        self.assertEqual(_salud(b)[1]["falla"], [a])   # y middleware, a core-db

    def test_salud_no_se_registra_y_lo_demas_si(self):
        _, a = self._nuevo("web-banking")
        _salud(a)
        urllib.request.urlopen(f"http://{a}/login", timeout=3).read()
        self.assertEqual(len(self.registro), 1)
        self.assertIn('"GET /login HTTP/1.1" 200', self.registro[0])


class TestFunciones(unittest.TestCase):
    def test_comprobar_dependencias_con_fallo_de_red(self):
        def abrir(url, timeout):
            raise OSError("sin ruta")
        self.assertEqual(servicio.comprobar_dependencias(["10.0.0.9:1"], abrir=abrir), ["10.0.0.9:1"])

    def test_linea_de_acceso_formato_combined(self):
        l = servicio.linea_acceso("198.51.100.10", "GET", "/x?id=1", 200, 42, "curl/8", 0)
        self.assertEqual(l, '198.51.100.10 - - [01/Jan/1970:00:00:00 +0000] "GET /x?id=1 HTTP/1.1" 200 42 "-" "curl/8"')


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Comprobar que falla**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_servicio 2>&1 | tail -3`
Expected: FAILED (ImportError).

- [ ] **Step 3: Implementar `lab/banco/servicio.py`**

```python
"""Servicio minimo del laboratorio del banco: responde HTTP en su puerto nominal y expone /salud,
que solo esta sano si el servicio Y todas sus dependencias lo estan. Como cada dependencia consulta a
su vez su /salud, una caida se propaga en cascada de verdad (spec §5.2). Autonomo: solo biblioteca
estandar, porque se copia tal cual a la imagen banco-nodo.
"""
import argparse
import http.server
import json
import threading
import time
import urllib.request


def comprobar_dependencias(dependencias, abrir=urllib.request.urlopen, plazo=1.0):
    """Las dependencias ("host:puerto") cuyo /salud no responde 200."""
    fallan = []
    for dep in dependencias:
        try:
            with abrir(f"http://{dep}/salud", timeout=plazo) as r:
                if r.status != 200:
                    fallan.append(dep)
        except Exception:
            fallan.append(dep)
    return fallan


def linea_acceso(ip, metodo, ruta, estado, tamano, agente, instante):
    """Registro de accesos en formato Apache combined (el que decodifica Wazuh)."""
    fecha = time.strftime("%d/%b/%Y:%H:%M:%S +0000", time.gmtime(instante))
    return f'{ip} - - [{fecha}] "{metodo} {ruta} HTTP/1.1" {estado} {tamano} "-" "{agente}"'


def crear_servidor(nombre, puerto, dependencias, registrar):
    class Manejador(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/salud":
                fallan = comprobar_dependencias(dependencias)
                cuerpo = {"servicio": nombre, "estado": "degradado" if fallan else "ok", "falla": fallan}
                estado = 503 if fallan else 200
            else:
                cuerpo, estado = {"servicio": nombre}, 200
            datos = json.dumps(cuerpo).encode()
            self.send_response(estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)
            if self.path != "/salud":
                registrar(linea_acceso(self.client_address[0], "GET", self.path, estado, len(datos),
                                       self.headers.get("User-Agent", "-"), time.time()))

        def log_message(self, *args):   # el registro propio sustituye al de stderr
            pass

    return http.server.ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Servicio minimo del laboratorio del banco")
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--puerto", type=int, action="append", required=True)
    ap.add_argument("--depende", action="append", default=[])
    ap.add_argument("--registro", default=None, help="fichero del registro de accesos")
    a = ap.parse_args(argv)
    cerrojo = threading.Lock()

    def registrar(linea):
        if not a.registro:
            return
        with cerrojo, open(a.registro, "a", encoding="utf-8") as f:
            f.write(linea + "\n")

    servidores = [crear_servidor(a.nombre, p, a.depende, registrar) for p in a.puerto]
    for s in servidores[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    servidores[0].serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Comprobar que pasa**

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/banco/tests -t . 2>&1 | tail -1`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add lab/banco/servicio.py lab/banco/tests/test_servicio.py
git commit -m "feat(banco): servicio minimo con salud transitiva y registro de accesos

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Monitor de salud (`monitor.py`)

**Files:**
- Create: `lab/banco/monitor.py`
- Test: `lab/banco/tests/test_monitor.py`

**Interfaces:**
- Produces:
  - `monitor.parsear_servicios(args: list[str]) -> dict[str, str]`: convierte `"nombre=ip:puerto"` en `{nombre: "ip:puerto"}`;
  - `monitor.sondear(servicios: dict, abrir=urlopen, plazo=1.0) -> dict[str, str]`: cada nombre vale `"ok"` o `"caido"`;
  - `monitor.cambios(anterior: dict, actual: dict) -> {"caen": list, "vuelven": list}`;
  - `monitor.registro(estados, instante) -> str`: una línea JSON `{"t": ISO-UTC, "estados": {...}}`;
  - CLI: `python3 monitor.py --intervalo 2 --salida /var/log/banco/salud.jsonl nombre=ip:puerto ...`.
- La línea de tiempo la consume el plan 2 (el juez de continuidad y cascada).

- [ ] **Step 1: Test que falla**

`lab/banco/tests/test_monitor.py`:

```python
import json
import unittest
from lab.banco import monitor


class _Resp:
    def __init__(self, status): self.status = status
    def __enter__(self): return self
    def __exit__(self, *a): return False


class TestMonitor(unittest.TestCase):
    def test_parsear_servicios(self):
        self.assertEqual(monitor.parsear_servicios(["core-db=10.50.0.10:1521", "hsm=10.60.0.10:9000"]),
                         {"core-db": "10.50.0.10:1521", "hsm": "10.60.0.10:9000"})

    def test_sondear_distingue_sano_503_y_sin_respuesta(self):
        def abrir(url, timeout):
            if "10.0.0.1" in url:
                return _Resp(200)
            if "10.0.0.2" in url:
                import urllib.error
                raise urllib.error.HTTPError(url, 503, "degradado", None, None)
            raise OSError("sin ruta")
        estados = monitor.sondear({"a": "10.0.0.1:1", "b": "10.0.0.2:1", "c": "10.0.0.3:1"}, abrir=abrir)
        self.assertEqual(estados, {"a": "ok", "b": "caido", "c": "caido"})

    def test_cambios(self):
        self.assertEqual(monitor.cambios({"a": "ok", "b": "ok", "c": "caido"}, {"a": "caido", "b": "ok", "c": "ok"}),
                         {"caen": ["a"], "vuelven": ["c"]})

    def test_registro_es_json_con_instante_utc(self):
        d = json.loads(monitor.registro({"a": "ok"}, 0))
        self.assertEqual(d, {"t": "1970-01-01T00:00:00Z", "estados": {"a": "ok"}})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Comprobar que falla**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_monitor 2>&1 | tail -3`
Expected: FAILED (ImportError).

- [ ] **Step 3: Implementar `lab/banco/monitor.py`**

```python
"""Monitor de salud del laboratorio del banco: consulta /salud de cada servicio cada pocos segundos y
escribe una linea de tiempo JSONL. Es el juez de los casos de continuidad y cascada (spec §5.2):
lo que la prediccion avisa se compara con lo que el monitor ve caer. Autonomo (biblioteca estandar).
"""
import argparse
import json
import time
import urllib.request


def parsear_servicios(args):
    return dict(a.split("=", 1) for a in args)


def sondear(servicios, abrir=urllib.request.urlopen, plazo=1.0):
    estados = {}
    for nombre, destino in servicios.items():
        try:
            with abrir(f"http://{destino}/salud", timeout=plazo) as r:
                estados[nombre] = "ok" if r.status == 200 else "caido"
        except Exception:
            estados[nombre] = "caido"
    return estados


def cambios(anterior, actual):
    return {"caen": sorted(n for n, e in actual.items() if e == "caido" and anterior.get(n) == "ok"),
            "vuelven": sorted(n for n, e in actual.items() if e == "ok" and anterior.get(n) == "caido")}


def registro(estados, instante):
    return json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(instante)), "estados": estados},
                      sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Monitor de salud del laboratorio del banco")
    ap.add_argument("--intervalo", type=float, default=2.0)
    ap.add_argument("--salida", required=True)
    ap.add_argument("servicios", nargs="+", help="nombre=ip:puerto")
    a = ap.parse_args(argv)
    servicios = parsear_servicios(a.servicios)
    while True:
        with open(a.salida, "a", encoding="utf-8") as f:
            f.write(registro(sondear(servicios), time.time()) + "\n")
        time.sleep(a.intervalo)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Comprobar que pasa**

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/banco/tests -t . 2>&1 | tail -1`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add lab/banco/monitor.py lab/banco/tests/test_monitor.py
git commit -m "feat(banco): monitor de salud con linea de tiempo JSONL

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Reenviador de logs a Wazuh (`reenviador.py`)

**Files:**
- Create: `lab/banco/reenviador.py`
- Test: `lab/banco/tests/test_reenviador.py`

**Interfaces:**
- Produces:
  - `reenviador.linea_syslog(prioridad: int, nodo: str, programa: str | None, mensaje: str, instante: float) -> str`: `"<PRI>Mmm DD HH:MM:SS nodo programa: mensaje"`, o sin `programa:` si es None;
  - `reenviador.desde_sshd(nodo, linea, instante) -> str`: extrae `sshd[pid]: msg` si está y, si no, usa la línea entera con pid 0;
  - `reenviador.desde_web(nodo, linea, instante) -> str`;
  - CLI: `python3 reenviador.py --nodo N --destino host:puerto [--sshd fichero] [--web fichero]`.
- Es el mismo formato que ya usa `lab/lab.sh test`: `<38>` + una cabecera `%b %d %H:%M:%S` + host + `sshd[pid]: ...`. Wazuh lo decodifica, está medido en la red pequeña. El nombre del nodo va como host, y así Wazuh deriva el `activo` (RF-16).

- [ ] **Step 1: Test que falla**

`lab/banco/tests/test_reenviador.py`:

```python
import unittest
from lab.banco import reenviador


class TestLineas(unittest.TestCase):
    def test_linea_syslog_con_programa(self):
        self.assertEqual(reenviador.linea_syslog(38, "web-banking", "sshd[7]", "hola", 0),
                         "<38>Jan 01 00:00:00 web-banking sshd[7]: hola")

    def test_linea_syslog_sin_programa(self):
        self.assertEqual(reenviador.linea_syslog(30, "atm", None, "x", 0), "<30>Jan 01 00:00:00 atm x")

    def test_sshd_conserva_pid_y_mensaje(self):
        l = "Sep 22 10:00:00 web-banking sshd[123]: Failed password for root from 198.51.100.10 port 5 ssh2"
        self.assertEqual(reenviador.desde_sshd("web-banking", l, 0),
                         "<38>Jan 01 00:00:00 web-banking sshd[123]: "
                         "Failed password for root from 198.51.100.10 port 5 ssh2")

    def test_sshd_sin_prefijo_usa_la_linea_entera(self):
        self.assertEqual(reenviador.desde_sshd("hsm", "Failed password for x from 1.2.3.4 port 1 ssh2\n", 0),
                         "<38>Jan 01 00:00:00 hsm sshd[0]: Failed password for x from 1.2.3.4 port 1 ssh2")

    def test_web_como_apache(self):
        l = '198.51.100.10 - - [01/Jan/1970:00:00:00 +0000] "GET / HTTP/1.1" 200 2 "-" "curl"'
        self.assertEqual(reenviador.desde_web("web-banking", l, 0),
                         "<30>Jan 01 00:00:00 web-banking apache: " + l)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Comprobar que falla**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_reenviador 2>&1 | tail -3`
Expected: FAILED (ImportError).

- [ ] **Step 3: Implementar `lab/banco/reenviador.py`**

```python
"""Sigue los logs de un nodo del banco (sshd y accesos web) y los envia por syslog UDP al manager de
Wazuh, con el nombre del nodo como host (Wazuh deriva de ahi el activo, RF-16). El formato es el que
Wazuh ya decodifica en la red pequena (lab/lab.sh test). Autonomo (biblioteca estandar).

Si Wazuh no decodifica el web por syslog, D5 queda marcado con su limite (plan, R3).
"""
import argparse
import re
import socket
import time

_SSHD = re.compile(r"sshd\[(\d+)\]:\s?(.*)$")


def linea_syslog(prioridad, nodo, programa, mensaje, instante):
    cabecera = time.strftime("%b %d %H:%M:%S", time.gmtime(instante))
    cuerpo = f"{programa}: {mensaje}" if programa else mensaje
    return f"<{prioridad}>{cabecera} {nodo} {cuerpo}"


def desde_sshd(nodo, linea, instante):
    linea = linea.rstrip("\n")
    m = _SSHD.search(linea)
    pid, msg = (m.group(1), m.group(2)) if m else ("0", linea.strip())
    return linea_syslog(38, nodo, f"sshd[{pid}]", msg, instante)


def desde_web(nodo, linea, instante):
    return linea_syslog(30, nodo, "apache", linea.rstrip("\n"), instante)


def seguir(rutas_y_formateadores, enviar, dormir=time.sleep, parar=lambda: False):
    """Como tail -F sobre varios ficheros: desde el final, envia cada linea nueva formateada."""
    abiertos = []
    for ruta, fmt in rutas_y_formateadores:
        while True:
            try:
                f = open(ruta, encoding="utf-8", errors="replace")
                break
            except FileNotFoundError:
                dormir(0.5)
        f.seek(0, 2)
        abiertos.append((f, fmt))
    while not parar():
        nada = True
        for f, fmt in abiertos:
            linea = f.readline()
            if linea:
                nada = False
                enviar(fmt(linea, time.time()))
        if nada:
            dormir(0.2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reenvia los logs de un nodo del banco a Wazuh")
    ap.add_argument("--nodo", required=True)
    ap.add_argument("--destino", required=True, help="host:puerto del syslog de Wazuh")
    ap.add_argument("--sshd", default=None)
    ap.add_argument("--web", default=None)
    a = ap.parse_args(argv)
    host, puerto = a.destino.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fuentes = []
    if a.sshd:
        fuentes.append((a.sshd, lambda l, t: desde_sshd(a.nodo, l, t)))
    if a.web:
        fuentes.append((a.web, lambda l, t: desde_web(a.nodo, l, t)))
    seguir(fuentes, lambda linea: sock.sendto(linea.encode(), (host, int(puerto))))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Comprobar que pasa**

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/banco/tests -t . 2>&1 | tail -1`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add lab/banco/reenviador.py lab/banco/tests/test_reenviador.py
git commit -m "feat(banco): reenviador de logs sshd y web a Wazuh por syslog

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Imagen `banco-nodo` y topología `banco.clab.yml`

**Files:**
- Create: `lab/banco/Dockerfile`, `lab/banco/construir-imagen.sh`
- Create: `lab/topologias/banco.clab.yml`
- Test: `lab/banco/tests/test_topologia.py`

**Interfaces:**
- Consumes: `red.NODOS` (Task 2).
- Produces:
  - la imagen `banco-nodo:1`, con `/opt/banco/{servicio,monitor,reenviador}.py`, `python3`, `sshd`, `sudo`, `iptables`, `sshpass`, `nmap`, `curl` y `nc`;
  - el laboratorio `name: banco`, con contenedores `clab-banco-<nodo>`.
  - Direccionamiento de enlaces: `internet` 198.51.100.10/24 ↔ `fw-edge` 198.51.100.1/24; `fw-edge` 10.0.0.254/24 ↔ `fw-core` 10.0.0.1/24; `fw-core` es `.1` en cada segmento.

- [ ] **Step 1: Test de coherencia que falla**

`lab/banco/tests/test_topologia.py`:

```python
import os
import unittest
import yaml
from lab.banco import red

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOPO = os.path.join(RAIZ, "lab", "topologias", "banco.clab.yml")


class TestTopologia(unittest.TestCase):
    def setUp(self):
        self.t = yaml.safe_load(open(TOPO, encoding="utf-8"))
        self.nodos = self.t["topology"]["nodes"]

    def test_nombre_del_laboratorio(self):
        self.assertEqual(self.t["name"], "banco")

    def test_cada_nodo_de_la_red_tiene_su_ip_y_su_puerta(self):
        for nombre, n in red.NODOS.items():
            self.assertIn(nombre, self.nodos, nombre)
            execs = " ".join(self.nodos[nombre].get("exec", []))
            self.assertIn(f"{n['ip']}/24", execs, nombre)
            self.assertIn(f"via {n['gw']}", execs, nombre)

    def test_fw_core_es_la_puerta_de_cada_segmento(self):
        execs = " ".join(self.nodos["fw-core"]["exec"])
        for nombre, n in red.NODOS.items():
            if nombre in ("mdr-siem", "auditor"):
                continue
            self.assertIn(f"{n['gw']}/24", execs, nombre)
        self.assertIn("10.100.0.1/24", execs)
        self.assertIn("10.0.0.1/24", execs)

    def test_internet_no_tiene_ruta_por_defecto_propia(self):
        # Aislamiento: el atacante solo sabe llegar al banco, no a una salida real.
        execs = " ".join(self.nodos["internet"]["exec"])
        self.assertNotIn("default", execs)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Comprobar que falla**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_topologia 2>&1 | tail -3`
Expected: FAILED (no existe `banco.clab.yml`).

- [ ] **Step 3: Crear la imagen**

`lab/banco/Dockerfile`:

```dockerfile
# Imagen comun de los nodos del laboratorio del banco: servicio, monitor, reenviador, sshd para el
# conector (minimo privilegio: lab/scripts/aprovisionar-minimo-privilegio.sh) e iptables para la
# contencion. Se construye una vez: sh lab/banco/construir-imagen.sh
FROM alpine:3.20
RUN apk add --no-cache python3 openssh sudo iptables sshpass nmap curl busybox-extras \
 && ssh-keygen -A \
 && mkdir -p /opt/banco /var/log/banco \
 && sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
 && adduser -D cliente && echo 'cliente:Cliente2026' | chpasswd
COPY servicio.py monitor.py reenviador.py /opt/banco/
```

`lab/banco/construir-imagen.sh`:

```sh
#!/bin/sh
# Construye la imagen banco-nodo:1 (una vez; despues el laboratorio se despliega sin descargar nada).
set -e
cd "$(dirname "$0")"
docker build -t banco-nodo:1 .
docker run --rm banco-nodo:1 sh -c 'python3 -c "import sys; print(sys.version.split()[0])" && ls /opt/banco'
```

- [ ] **Step 4: Crear `lab/topologias/banco.clab.yml`**

```yaml
# Laboratorio del banco (spec docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md §5).
# Misma red que prototipo/perfiles/bancario.yml; la fuente unica de IPs y servicios es lab/banco/red.py
# (lab/banco/tests/test_topologia.py comprueba que coinciden).
#
#   internet ── fw-edge ── fw-core ─┬─ web-banking 10.10 · api-movil 10.20 · swift-alliance 10.30
#                                   ├─ middleware 10.40 · core-db 10.50 · hsm 10.60
#                                   ├─ taquilla 10.200 · atm 10.210
#                                   └─ sw-soc ─┬─ mdr-siem 10.100.0.10 (MDR y conector; ip_gestion)
#                                              └─ auditor  10.100.0.20
#
# Las rutas de datos son especificas (10.0.0.0/8, 198.51.100.0/24): la ruta por defecto es la de
# gestion (eth0), como en red-cliente. 'internet' no tiene salida real: es un nodo mas del laboratorio.
# Se levanta con: sh lab/lab.sh up banco   (no convive con red-cliente: misma red de gestion)

name: banco

topology:
  defaults:
    kind: linux
    image: banco-nodo:1

  nodes:
    internet:
      exec:
        - ip addr add 198.51.100.10/24 dev eth1
        - ip route add 10.0.0.0/8 via 198.51.100.1

    fw-edge:
      sysctls: {net.ipv4.ip_forward: 1}
      exec:
        - ip addr add 198.51.100.1/24 dev eth1
        - ip addr add 10.0.0.254/24 dev eth2
        - ip route add 10.0.0.0/8 via 10.0.0.1

    fw-core:
      sysctls: {net.ipv4.ip_forward: 1}
      exec:
        - ip addr add 10.0.0.1/24 dev eth1
        - ip addr add 10.10.0.1/24 dev eth2
        - ip addr add 10.20.0.1/24 dev eth3
        - ip addr add 10.30.0.1/24 dev eth4
        - ip addr add 10.40.0.1/24 dev eth5
        - ip addr add 10.50.0.1/24 dev eth6
        - ip addr add 10.60.0.1/24 dev eth7
        - ip addr add 10.100.0.1/24 dev eth8
        - ip addr add 10.200.0.1/24 dev eth9
        - ip addr add 10.210.0.1/24 dev eth10
        - ip route add 198.51.100.0/24 via 10.0.0.254

    sw-soc:
      exec:
        - ip link add br0 type bridge
        - ip link set eth1 master br0
        - ip link set eth2 master br0
        - ip link set eth3 master br0
        - ip link set br0 up

    web-banking:
      exec: ["ip addr add 10.10.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.10.0.1", "ip route add 198.51.100.0/24 via 10.10.0.1"]
    api-movil:
      exec: ["ip addr add 10.20.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.20.0.1", "ip route add 198.51.100.0/24 via 10.20.0.1"]
    swift-alliance:
      exec: ["ip addr add 10.30.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.30.0.1", "ip route add 198.51.100.0/24 via 10.30.0.1"]
    middleware:
      exec: ["ip addr add 10.40.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.40.0.1", "ip route add 198.51.100.0/24 via 10.40.0.1"]
    core-db:
      exec: ["ip addr add 10.50.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.50.0.1", "ip route add 198.51.100.0/24 via 10.50.0.1"]
    hsm:
      exec: ["ip addr add 10.60.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.60.0.1", "ip route add 198.51.100.0/24 via 10.60.0.1"]
    mdr-siem:
      exec: ["ip addr add 10.100.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.100.0.1", "ip route add 198.51.100.0/24 via 10.100.0.1"]
    auditor:
      exec: ["ip addr add 10.100.0.20/24 dev eth1", "ip route add 10.0.0.0/8 via 10.100.0.1", "ip route add 198.51.100.0/24 via 10.100.0.1"]
    taquilla:
      exec: ["ip addr add 10.200.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.200.0.1", "ip route add 198.51.100.0/24 via 10.200.0.1"]
    atm:
      exec: ["ip addr add 10.210.0.10/24 dev eth1", "ip route add 10.0.0.0/8 via 10.210.0.1", "ip route add 198.51.100.0/24 via 10.210.0.1"]

  links:
    - endpoints: ["internet:eth1", "fw-edge:eth1"]
    - endpoints: ["fw-edge:eth2", "fw-core:eth1"]
    - endpoints: ["fw-core:eth2", "web-banking:eth1"]
    - endpoints: ["fw-core:eth3", "api-movil:eth1"]
    - endpoints: ["fw-core:eth4", "swift-alliance:eth1"]
    - endpoints: ["fw-core:eth5", "middleware:eth1"]
    - endpoints: ["fw-core:eth6", "core-db:eth1"]
    - endpoints: ["fw-core:eth7", "hsm:eth1"]
    - endpoints: ["fw-core:eth8", "sw-soc:eth1"]
    - endpoints: ["sw-soc:eth2", "mdr-siem:eth1"]
    - endpoints: ["sw-soc:eth3", "auditor:eth1"]
    - endpoints: ["fw-core:eth9", "taquilla:eth1"]
    - endpoints: ["fw-core:eth10", "atm:eth1"]
```

- [ ] **Step 5: Test en verde y construcción**

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/banco/tests -t . 2>&1 | tail -1`
Expected: `OK`.

Run: `sh lab/banco/construir-imagen.sh`
Expected: la versión de Python y `monitor.py reenviador.py servicio.py`.

- [ ] **Step 6: Commit**

```bash
git add lab/banco/Dockerfile lab/banco/construir-imagen.sh lab/topologias/banco.clab.yml lab/banco/tests/test_topologia.py
git commit -m "feat(banco): imagen banco-nodo y topologia del banco en containerlab

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Orquestación (`banco.sh`, selector en `lab.sh`) y prueba de humo

**Files:**
- Create: `lab/banco/banco.sh`
- Modify: `lab/lab.sh` (delegar `banco` y proteger contra dos redes a la vez)

**Interfaces:**
- Consumes: la CLI de `red.py` (`servicio`, `monitor`, `nodos`, `puertos`, `servicios`), `lab/scripts/wazuh-run.sh up` y `lab/scripts/aprovisionar-minimo-privilegio.sh`.
- Produces:
  - `sh lab/banco/banco.sh up|down|status|test|cascada <servicio>`;
  - `sh lab/lab.sh up banco` delega en `banco.sh`;
  - la línea de tiempo del monitor en `clab-banco-mdr-siem:/var/log/banco/salud.jsonl`.

- [ ] **Step 1: Crear `lab/banco/banco.sh`**

```sh
#!/bin/sh
# Control del laboratorio del banco (spec 2026-09-21-laboratorio-banco-design.md §5).
#
#   sh lab/banco/banco.sh up              despliega, arranca servicios/sshd/reenviadores/monitor y Wazuh
#   sh lab/banco/banco.sh down            lo baja
#   sh lab/banco/banco.sh status          estado de nodos y salud
#   sh lab/banco/banco.sh test            prueba de humo: conectividad y todos los servicios sanos
#   sh lab/banco/banco.sh cascada core-db tumba un servicio, muestra que cae y lo restaura
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$HERE/../.." && pwd)
TOPO="$RAIZ/lab/topologias/banco.clab.yml"
P=clab-banco
red() { (cd "$RAIZ" && python3 -m lab.banco.red "$@"); }

salud() {
  docker exec $P-mdr-siem sh -c "tail -n1 /var/log/banco/salud.jsonl 2>/dev/null" || true
}

case "${1:-up}" in
  up)
    if docker ps --format '{{.Names}}' | grep -q '^clab-red-cliente-puesto$'; then
      echo "La red pequena (red-cliente) esta levantada: bajala antes (sh lab/lab.sh down)."; exit 1
    fi
    docker image inspect banco-nodo:1 >/dev/null 2>&1 || sh "$HERE/construir-imagen.sh"
    echo "== 1. Desplegando el banco =="
    containerlab deploy -t "$TOPO"
    echo "== 2. Wazuh =="
    sh "$RAIZ/lab/scripts/wazuh-run.sh" up
    W=$(docker inspect clab-red-cliente-wazuh --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    echo "== 3. sshd, servicios y reenviadores =="
    for n in web-banking api-movil swift-alliance middleware core-db hsm atm taquilla fw-core fw-edge mdr-siem auditor; do
      docker exec $P-$n sh -c 'pgrep -x sshd >/dev/null || /usr/sbin/sshd -E /var/log/banco/sshd.log; touch /var/log/banco/access.log'
      CMD=$(red servicio $n)
      if [ -n "$CMD" ]; then docker exec -d $P-$n sh -c "$CMD"; fi
      docker exec -d $P-$n python3 /opt/banco/reenviador.py --nodo $n --destino "$W:514" \
        --sshd /var/log/banco/sshd.log --web /var/log/banco/access.log
    done
    echo "== 4. Monitor de salud en mdr-siem =="
    docker exec -d $P-mdr-siem sh -c "python3 /opt/banco/monitor.py --intervalo 2 --salida /var/log/banco/salud.jsonl $(red monitor)"
    sleep 5
    echo "== Banco en marcha. Prueba: sh lab/banco/banco.sh test =="
    ;;
  down)
    containerlab destroy -t "$TOPO" 2>/dev/null || true
    sh "$RAIZ/lab/scripts/wazuh-run.sh" down 2>/dev/null || true
    echo "Banco detenido."
    ;;
  status)
    docker ps --filter name=$P --format '  {{.Names}}: {{.Status}}'
    echo "== Salud (ultima muestra) =="; salud
    ;;
  test)
    echo "-- 1. internet -> web-banking (a traves de fw-edge y fw-core)"
    docker exec $P-internet curl -s -m 3 -o /dev/null -w '   HTTP %{http_code}\n' http://10.10.0.10:443/ || echo "   FALLO"
    echo "-- 2. mdr-siem llega a los dos cortafuegos"
    for ip in 10.0.0.1 10.0.0.254; do docker exec $P-mdr-siem ping -c1 -W2 $ip >/dev/null 2>&1 && echo "   $ip OK" || echo "   $ip FALLO"; done
    echo "-- 3. Todos los servicios sanos"
    sleep 3
    salud | python3 -c "import sys,json; d=json.loads(sys.stdin.read() or '{}').get('estados',{}); m=[k for k,v in d.items() if v!='ok']; print('   OK' if d and not m else f'   CAIDOS: {m or \"sin datos\"}')"
    ;;
  cascada)
    S="${2:?uso: banco.sh cascada <servicio>}"
    echo "Tumbando $S (su servicio HTTP)..."
    docker exec $P-$S sh -c "pkill -f 'servicio.py --nombre $S'" || true
    sleep 6; echo "Salud con $S caido:"; salud
    CMD=$(red servicio $S); docker exec -d $P-$S sh -c "$CMD"
    sleep 6; echo "Salud tras restaurar:"; salud
    ;;
  *) echo "uso: $0 up|down|status|test|cascada <servicio>" ;;
esac
```

- [ ] **Step 2: Selector en `lab/lab.sh`**

Justo después de `TOPO="$HERE/topologias/${TOPOLOGIA}.clab.yml"`, añade:

```sh
# El banco tiene su propio orquestador (servicios, monitor, reenviadores): lab/banco/banco.sh
if [ "$TOPOLOGIA" = "banco" ]; then exec sh "$HERE/banco/banco.sh" "${1:-up}"; fi
```

Y en la rama `up)`, antes de `echo "== 1. Desplegando la red del cliente =="`, añade la guarda:

```sh
    if docker ps --format '{{.Names}}' | grep -q '^clab-banco-fw-core$'; then
      echo "El banco esta levantado: bajalo antes (sh lab/lab.sh down banco)."; exit 1
    fi
```

- [ ] **Step 3: Levantar y prueba de humo (en vivo)**

Run: `sh lab/lab.sh down; sh lab/lab.sh up banco && sh lab/banco/banco.sh test`
Expected:
- `HTTP 200` desde `internet`;
- los dos cortafuegos `OK`;
- `OK` en salud.

Si el paso 1 falla: comprueba `docker exec clab-banco-fw-core ip route` y `iptables -L FORWARD` (debe estar vacío y con política ACCEPT).

- [ ] **Step 4: Cascada manual (el criterio de la fase 2 del spec)**

Run: `sh lab/banco/banco.sh cascada core-db`
Expected:
- con `core-db` caído, los estados `caido` son **exactamente** `api-movil`, `atm`, `core-db`, `middleware` y `web-banking`, y siguen `ok` `hsm` y `swift-alliance`;
- tras restaurar, todo vuelve a `ok`.

Anota la salida literal: va a `lab/banco/verificaciones.md` (Task 8).

- [ ] **Step 5: La red pequeña sigue funcionando**

Run: `sh lab/lab.sh down banco && sh lab/lab.sh up && sh lab/lab.sh test && sh lab/lab.sh down`
Expected: la prueba de humo de siempre (conectividad OK y fuerza bruta correlacionada).

- [ ] **Step 6: Commit**

```bash
git add lab/banco/banco.sh lab/lab.sh
git commit -m "feat(banco): orquestacion del laboratorio del banco y selector en lab.sh

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Fase 0 — verificaciones en vivo

Sin código nuevo en el prototipo. Resultado: `lab/banco/verificaciones.md`, con una sección por verificación en el formato **comando exacto → salida literal (recortada) → conclusión → casos afectados**. El plan 2 lo consume para fijar el ataque y lo esperado de cada caso.

**Files:**
- Create: `lab/banco/verificaciones.md`

**Interfaces:**
- Consumes: el banco levantado (Task 7), `TRIAJE_NODO_GESTION` (Task 1) y `red.nodos_auditor()` / `red.puertos_auditor()` (Task 2).
- Produces: `lab/banco/verificaciones.md`, con las secciones V1–V7 y una tabla final «caso → estado (confirmado / límite / fallo esperado)».

- [ ] **Step 1 (V1): minimo privilegio desde `mdr-siem`**

Run:

```sh
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
for n in web-banking:10.10.0.10 api-movil:10.20.0.10 atm:10.210.0.10 fw-core:10.0.0.1 fw-edge:10.0.0.254 middleware:10.40.0.10 core-db:10.50.0.10 hsm:10.60.0.10 swift-alliance:10.30.0.10 taquilla:10.200.0.10; do
  sh lab/scripts/aprovisionar-minimo-privilegio.sh clab-banco-${n%%:*} ${n##*:} || echo "FALLO en $n"
done
```

Expected: en cada nodo, `permitido (del catalogo)`, `denegado` para `/etc/shadow` y `denegado` para `iptables -F`. Anota los que fallen.

- [ ] **Step 2 (V2): detección de fuerza bruta SSH (D1, A1, K1)**

Run (el atacante externo contra `web-banking`; después, `taquilla` y `middleware` como atacantes internos):

```sh
for i in $(seq 1 10); do docker exec clab-banco-internet sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.10.0.10 id" 2>/dev/null; done
for i in $(seq 1 10); do docker exec clab-banco-taquilla sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.50.0.10 id" 2>/dev/null; done
for i in $(seq 1 10); do docker exec clab-banco-middleware sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 -o PubkeyAuthentication=no -o PreferredAuthentications=password cliente@10.50.0.10 id" 2>/dev/null; done
sleep 8
docker exec clab-red-cliente-wazuh sh -c "grep -a '\"srcip\":\"198.51.100.10\"\|\"srcip\":\"10.200.0.10\"\|\"srcip\":\"10.40.0.10\"' /var/ossec/logs/alerts/alerts.json" | python3 -c "
import sys,json,collections
c=collections.Counter()
for l in sys.stdin:
    a=json.loads(l); c[(a['data'].get('srcip'), a.get('predecoder',{}).get('hostname'), a['rule']['id'], a['rule']['level'])]+=1
for k,v in sorted(c.items()): print(v,k)"
```

Expected: alertas `5760` y `5763` (fuerza bruta correlacionada) con `hostname` = `web-banking` o `core-db`. Si no aparecen, comprueba primero `docker exec clab-banco-web-banking cat /var/log/banco/sshd.log` para ver qué escribe `sshd -E`, y ajusta la expresión regular de `reenviador.desde_sshd`, con su test, antes de seguir.

- [ ] **Step 3 (V3): ataque web (D5) y reconocimiento (D7)**

Run:

```sh
docker exec clab-banco-internet sh -c "for p in \"/?id=1'%20OR%20'1'='1\" '/../../etc/passwd' '/?q=<script>alert(1)</script>'; do curl -s -m3 -o /dev/null \"http://10.10.0.10:443\$p\"; done"
docker exec clab-banco-internet nmap -Pn -sT -p 1-2000 10.10.0.10 >/dev/null
sleep 8
docker exec clab-red-cliente-wazuh sh -c "grep -a '198.51.100.10' /var/ossec/logs/alerts/alerts.json | tail -n 40" | python3 -c "
import sys,json
for l in sys.stdin:
    a=json.loads(l); print(a['rule']['id'], a['rule']['level'], a['rule'].get('groups'), a['rule']['description'][:70])"
```

Expected: anota qué reglas saltan. Si ninguna del grupo `web`/`attack` aparece para las peticiones, **D5 queda como límite de detección** (R3): anótalo así, sin inventar alertas.

- [ ] **Step 4 (V4): el auditor y la reconciliación del inventario**

Run:

```sh
AUDITOR_NODOS="$(python3 -m lab.banco.red nodos)" AUDITOR_PUERTOS="$(python3 -m lab.banco.red puertos)" \
TRIAJE_AUDITOR=clab-banco-auditor sh lab/scripts/auditar.sh lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json
python3 -m prototipo.inventario prototipo/perfiles/bancario.yml lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json
```

Expected:
- hallazgos de los diez nodos;
- la reconciliación muestra el `22` abierto y no declarado en todos (el sshd del conector: exposición conocida del laboratorio) y los puertos nominales de `hsm` y `swift-alliance` como no declarados **hasta la Task 9**. Anótalo.

- [ ] **Step 5 (V5): qué hace el lazo con una víctima que es una joya de la corona (C4)**

Run (sin red: ejecutor simulado que registra a quién contacta):

```sh
PYTHONPATH=. python3 - <<'EOF'
from prototipo import lazo, catalogo as catm, perfil as perfilm
p = perfilm.cargar("prototipo/perfiles/bancario.yml"); c = catm.cargar_catalogo("prototipo/catalogo.yml")
toc = []
def ej(ip, cmd): toc.append(ip); return (0, "DROP") if "grep" in cmd and len(toc) > 1 else (1, "")
a = {"id_alerta": "v5", "regla_id": "5763", "origen_ip": "198.51.100.10", "activo": "hsm", "servicio": "ssh",
     "familia": "acceso_credenciales", "mitre": ["T1110"], "timestamp": "2026-09-22T00:00:00Z"}
h = {"nodos": {"hsm": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
r = lazo.procesar_lazo(a, h, p, "bancario", c, ej, "v5", a["timestamp"], leer=lambda _: "1")
print("accion_final:", r["accion_final"], "| filtro:", r["resultado_filtro"])
print("orden sobre:", (r.get("orden") or {}).get("nodo_ip"), "| IPs contactadas:", toc)
EOF
```

Expected: anota si la primera IP contactada es `10.60.0.10` (el propio HSM). Si lo es, **C4 queda como fallo esperado**: el lazo intenta primero la víctima y solo escala si falla. Lo documentado en el perfil («nunca tocar el activo crítico») no lo garantiza el código. Queda como tarea aparte, igual que H2.

- [ ] **Step 6 (V6): escalada real entre cortafuegos (E1, E2)**

Run (con V1 hecho; bloqueo de una IP de prueba en `fw-core` y en `fw-edge` por el conector real):

```sh
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
PYTHONPATH=. python3 - <<'EOF'
from prototipo import conector, catalogo as catm
c = catm.cargar_catalogo("prototipo/catalogo.yml"); ej = conector.ejecutor_por_defecto()
for nodo, ip in (("fw-core", "10.0.0.1"), ("fw-edge", "10.0.0.254")):
    o = {"decision_id": "v6", "accion_id": "BLOQUEAR_IP_FIREWALL", "nodo_objetivo": nodo, "nodo_ip": ip,
         "params": {"ip": "192.0.2.99"}}
    print(nodo, conector.ejecutar_orden(o, c, ej, "v6")["exito"])
    print("  revertir:", ej(ip, "iptables -D FORWARD -s 192.0.2.99 -j DROP")[0])
EOF
```

Expected: `True` en los dos y reversión `0`. Si falla, anota la salida del conector.

- [ ] **Step 7 (V7): K1 en crudo (H2)**

Run (bloqueo aprobado de la IP de `middleware` en `fw-core`, y lo que ve el monitor):

```sh
export TRIAJE_NODO_GESTION=clab-banco-mdr-siem
PYTHONPATH=. python3 -c "
from prototipo import conector
ej = conector.ejecutor_por_defecto(); print(ej('10.0.0.1', 'iptables -A FORWARD -s 10.40.0.10 -j DROP')[0])"
sleep 8; docker exec clab-banco-mdr-siem tail -n1 /var/log/banco/salud.jsonl
PYTHONPATH=. python3 -c "
from prototipo import conector
ej = conector.ejecutor_por_defecto(); print(ej('10.0.0.1', 'iptables -D FORWARD -s 10.40.0.10 -j DROP')[0])"
PYTHONPATH=. python3 -c "
from prototipo import impacto, perfil, catalogo
p = perfil.cargar('prototipo/perfiles/bancario.yml'); c = catalogo.cargar_catalogo('prototipo/catalogo.yml')
d = impacto.determinar('BLOQUEAR_IP_FIREWALL', {'ip': '10.40.0.10'}, 'core-db', p, c)
print('prediccion:', d['activos_afectados_en_cascada'], '|', d['motivo'])"
```

Expected (H2):
- el monitor muestra caídos `web-banking`, `api-movil`, `atm` y `middleware`;
- la predicción muestra `[]` y un motivo sin «en cascada».

Anota las dos salidas: son la evidencia de K1.

- [ ] **Step 8: Escribir `lab/banco/verificaciones.md`**

Con las secciones V1–V7 (comando, salida literal recortada, conclusión, casos afectados) y la tabla final:

| Caso | Estado tras la fase 0 |
|---|---|
| D1, A1, K1 | confirmado / no detectado (según V2) |
| D5 | confirmado / límite de detección (según V3) |
| D7 | según V3 |
| C4 | fallo esperado (según V5) |
| E1, E2 | confirmado / fallo (según V6) |
| K1 | fallo esperado (H2), con la evidencia de V7 |

- [ ] **Step 9: Commit**

```bash
git add lab/banco/verificaciones.md lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json
git commit -m "docs(banco): verificaciones en vivo de la fase 0 (deteccion, conector, escalada, C4, K1)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Perfil bancario alineado con la red real

**Files:**
- Modify: `prototipo/perfiles/bancario.yml` (líneas de `swift-alliance`, `hsm` y `atm`)
- Test: `lab/banco/tests/test_red.py` (añadir un test)

**Interfaces:**
- Consumes: `red.SERVICIOS` (Task 2) y la reconciliación de V4 (Task 8).
- Produces: el perfil con `hsm.servicios_prestados: [9000]` y `swift-alliance.servicios_prestados: [48002]`, y la omisión deliberada de `atm → middleware` comentada en el propio perfil.

- [ ] **Step 1: Test que falla**

Añade a la clase `TestCoherenciaConElPerfil` de `lab/banco/tests/test_red.py`:

```python
    def test_cada_servicio_del_laboratorio_esta_declarado_en_el_perfil(self):
        for nombre, s in red.SERVICIOS.items():
            declarados = set(PERFIL["activos"][nombre].get("servicios_prestados") or [])
            self.assertTrue(set(s["puertos"]) <= declarados, f"{nombre}: {s['puertos']} vs {declarados}")
```

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_red 2>&1 | tail -3`
Expected: FAIL (`hsm`, `swift-alliance` y `atm` no declaran sus puertos).

- [ ] **Step 2: Editar el perfil**

En `prototipo/perfiles/bancario.yml`, en `activos:`, sustituye las líneas de `swift-alliance`, `hsm` y `atm` por:

```yaml
  swift-alliance: { ip: 10.30.0.10,  funcion: "pasarela SWIFT Alliance (transferencias)",      criticidad: critica, servicios_prestados: [48002], depende_de: [hsm] }     # DMZ SWIFT
  hsm:            { ip: 10.60.0.10,  funcion: "modulo de seguridad de hardware (cifrado)",     criticidad: critica, servicios_prestados: [9000] }       # Core VLAN 60
  # atm depende DE VERDAD de middleware en el laboratorio del banco, y aqui NO se declara a proposito:
  # es el caso K3 (dependencia no declarada -> falso "sin cascada"). Ver lab/banco/red.py.
  atm:            { ip: 10.210.0.10, funcion: "cajero automatico de sucursal",                 criticidad: alta,    servicios_prestados: [8080] }       # Sucursal VLAN 210
```

Los puertos son nominales (spec §5.2): imitan el servicio real en el laboratorio.

- [ ] **Step 3: Las suites en verde**

Run: `for d in prototipo/tests evaluacion/tests lab/dataset/tests lab/banco/tests; do PYTHONPATH=. python3 -m unittest discover -s $d -t . 2>&1 | tail -1; done`
Expected: `OK` en las cuatro. Si falla algún test de `prototipo/tests/test_perfil.py` que asumía `servicios_prestados: []` en `hsm`, **para e informa**: significa que el cambio altera el comportamiento del perfil y hay que decidirlo, no ajustar el test a ciegas.

- [ ] **Step 4: Reconciliación de nuevo**

Run: `python3 -m prototipo.inventario prototipo/perfiles/bancario.yml lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json`
Expected: solo queda el `22` como no declarado (el sshd del laboratorio). Añade una línea con este resultado al final de `lab/banco/verificaciones.md`, en V4.

- [ ] **Step 5: Commit**

```bash
git add prototipo/perfiles/bancario.yml lab/banco/tests/test_red.py lab/banco/verificaciones.md
git commit -m "feat(bancario): el perfil describe la red real del laboratorio del banco

Puertos nominales de hsm, swift-alliance y atm; la dependencia atm -> middleware se omite a
proposito (caso K3) y queda comentada en el propio perfil.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Documentación del banco

**Files:**
- Create: `lab/banco/README.md`
- Modify: `lab/README.md` (un párrafo que apunte al banco)
- Modify: `documentacion/00-general/estado-y-riesgos.md` (fila de la Fase 3: una frase sobre el banco, y el recuento de tests)

**Interfaces:**
- Consumes: todo lo anterior y `lab/banco/verificaciones.md`.

- [ ] **Step 1: `lab/banco/README.md`**

```markdown
# Laboratorio del banco

La red de `prototipo/perfiles/bancario.yml`, montada de verdad en Containerlab: servicios con
dependencias reales, un monitor de salud que ve las cascadas y cortafuegos sobre los que el conector
actúa. Diseño: `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md`.

## Levantar

    sh lab/banco/construir-imagen.sh      # una vez
    sh lab/lab.sh up banco                # no convive con la red pequeña
    sh lab/banco/banco.sh test            # conectividad y salud
    sh lab/banco/banco.sh cascada core-db # ver una cascada real y su recuperación
    sh lab/lab.sh down banco

El conector ejecuta desde `mdr-siem` (la IP de gestión del perfil):

    export TRIAJE_NODO_GESTION=clab-banco-mdr-siem

## Qué hay

| Pieza | Dónde |
|---|---|
| Nodos, IPs, servicios y dependencias (fuente única) | `lab/banco/red.py` |
| Servicio con salud transitiva | `lab/banco/servicio.py` |
| Monitor (línea de tiempo en `mdr-siem:/var/log/banco/salud.jsonl`) | `lab/banco/monitor.py` |
| Logs a Wazuh | `lab/banco/reenviador.py` |
| Resultados de la fase 0 | `lab/banco/verificaciones.md` |

La dependencia `atm → middleware` existe aquí y **no** en el perfil, a propósito (caso K3).
Los puertos de los servicios son nominales: servicios HTTP que imitan el puerto del servicio real.
```

- [ ] **Step 2: Puntero en `lab/README.md` y estado**

- En `lab/README.md`, añade al final una sección `## Laboratorio del banco` con una frase y el enlace `banco/README.md`.
- En `documentacion/00-general/estado-y-riesgos.md`, en la fila «3 — Entorno de pruebas», añade: «Laboratorio del banco (22/09): la red de `bancario.yml` con servicios y dependencias reales y monitor de salud; ver `lab/banco/`.»
- Actualiza el recuento de tests del prototipo en esa tabla y en `README.md` con el número que dé la suite.

- [ ] **Step 3: Suites y commit**

Run: `for d in prototipo/tests evaluacion/tests lab/dataset/tests lab/banco/tests; do PYTHONPATH=. python3 -m unittest discover -s $d -t . 2>&1 | tail -1; done`
Expected: `OK` en las cuatro.

```bash
git add lab/banco/README.md lab/README.md documentacion/00-general/estado-y-riesgos.md README.md
git commit -m "docs(banco): como levantar y usar el laboratorio del banco

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
