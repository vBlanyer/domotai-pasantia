# Conciencia de impacto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que cada decisión de contención **determine** su impacto desde el inventario del perfil —a quién bloquea y qué servicios detiene—, que ese conocimiento gobierne el filtro (bloquear lo propio exige humano por defecto; el canal de gestión es intocable), quede en la traza y lo vean el analista y el agente (RF-17, RF-19).

**Architecture:** Dos módulos puros nuevos: `actores.py` (¿quién es esta IP para el cliente?) e `impacto.py` (impacto determinado de una acción). `perfil.filtrar` los usa por dentro (C5), así que el conocimiento llega a todos los puntos de decisión, incluidos los saltos de la escalada. `inventario.py` reconcilia lo declarado con lo que ve el auditor. El perfil `empresarial` pasa a describir la red real del laboratorio.

**Tech Stack:** Python 3 (biblioteca estándar: `ipaddress`, `unittest`) + PyYAML. Sin pip, sin venv, sin pytest.

**Spec:** [`docs/superpowers/specs/2026-09-21-conciencia-de-impacto-design.md`](../specs/2026-09-21-conciencia-de-impacto-design.md). Leer entero antes de empezar; las decisiones C1–C6 son vinculantes.

## Global Constraints

- **C1:** por defecto, bloquear un `activo_interno` o un `dispositivo_red` exige humano: `POLITICA_POR_DEFECTO = "humano_siempre"`. Se configura por perfil en `continuidad.actores`; un valor desconocido también cae a `humano_siempre`.
- **C2:** el nivel de impacto determinado **nunca queda por debajo** del nivel del catálogo; solo lo mantiene o lo sube.
- **C3:** `actores.quien_es` resuelve **solo desde el perfil**; no lee `orden.IP_DE_NODO`.
- **C4:** bloquear la `ip_gestion` es **veto duro** (`accion_final=None`, `requiere_humano=True`).
- **C5:** la conciencia de actores vive **dentro de `perfil.filtrar`**.
- **C6:** un nombre por IP (la `.1` del laboratorio se llama `borde` en todas partes); criticidad `media` para los cuatro nodos del laboratorio.
- **No-objetivos:** la clasificación **no cambia** (recall, tasa de FP y priorización idénticos a `evaluacion/resultados/campana-2026-09-11.json`); no se amplía el catálogo; no se hacen alcanzables acciones hoy inalcanzables.
- **Valores fijados:** `empresarial` → `ip_gestion: 172.20.20.4`, `redes_internas: ["192.168.1.0/24"]`; `bancario` → `redes_internas: ["10.0.0.0/8"]`.
- **Efecto esperado (Tarea 10 lo mide):** contenciones automáticas 69 → **0**; escalado 20/300 → **89/300**; bloqueos automáticos indebidos 2 → **0**.
- **Tests:** `unittest` con TDD estricto. Suites: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .`, `PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests -t .` y `PYTHONPATH=. python3 -m unittest discover -s lab/dataset/tests -t .`. Punto de partida: 306 / 39 / 37 en verde.
- **Estilo:** comentarios y textos en español, con la densidad de comentarios del fichero que se toca. `agente_mitigacion.py` escribe sus cadenas sin tildes («gestion», «segun»); se respeta.
- **Git:**
  - Rama `feature/conciencia-impacto` desde `main`; un commit por tarea.
  - Cada mensaje de commit termina con `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
  - Al final, fusión `--no-ff` a `main` local. **Nunca `push`**.
- **Documentos que no se tocan:** el plan de trabajo, el roadmap y el `.tex`; los documentos históricos de fase (Fases 1–4, como `politica-decision-continuidad.md`); y el `informe-evaluacion.md` de la Fase 6, que describe la campaña del 11/09.

## Refinamientos sobre el spec (decididos al planificar)

1. **La comprobación de actor se aplica a la acción FINAL** (después de las reglas y de una posible degradación), no a la propuesta. Así cubre `BLOQUEAR_PUERTO → BLOQUEAR_IP` cuando esa IP es un activo interno. En todos los demás casos el resultado es el mismo que con el orden de §4.4.
2. **El veto de gestión es incondicional** si el perfil declara `ip_gestion`, igual que `agente_mitigacion.validar_comando`. Declarar la IP ya es la opción del cliente.
3. **La cadena de §4.1 para la IP de ejecución se reparte en dos módulos:**
   - `perfil.ip_de` busca en `activos` y después en `topologia`;
   - `orden.construir` añade el respaldo `IP_DE_NODO`.

   Así no hay una importación circular `perfil ↔ orden`.
4. **La línea para el analista es `det["motivo"]`**, sin una función `describir` aparte, con la etiqueta **«Consecuencia:»**. «Impacto:» ya existe en el prompt con el nivel del catálogo, y dos etiquetas iguales confundirían.
5. **`quien_es` devuelve además `funcion`, `ip` y `por`**, que es la declaración de la que sale la resolución. Sirve para explicar por qué una IP se consideró interna.
6. **Los hallazgos llegan al agente ReAct** (`bucle_react`, `stream.construir_mitigar_fn`). No llegan a la escalada determinista, que no describe la topología a nadie.
7. **SWIFT sin VLAN:** `bancario.yml` no numera la VLAN de `swift-alliance`. Se usa `10.30.0.10` (VLAN 30, libre entre la DMZ 20 y el Core 40). **El usuario lo revisa** si tiene la topología original.

## File Structure

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `prototipo/actores.py` | Crear | `quien_es(ip, perfil)` y `politica(perfil, tipo)`: quién es una IP para el cliente |
| `prototipo/impacto.py` | Crear | `determinar(...)`, `puertos_abiertos(...)` (Nivel 2: `afectados_en_cascada`) |
| `prototipo/inventario.py` | Crear | `reconciliar(perfil, hallazgos)`, `formatear`, CLI |
| `prototipo/perfil.py` | Modificar | `filtrar(..., hallazgos=None)` = reglas + actor + clave `impacto`; `ip_de` |
| `prototipo/triaje.py` | Modificar | pasa `hallazgos` al filtro |
| `prototipo/traza.py` | Modificar | campo `impacto_determinado` |
| `prototipo/validacion.py` | Modificar | línea «Consecuencia:» |
| `prototipo/stream.py` | Modificar | línea «Consecuencia:» en el daemon; `construir_mitigar_fn(..., hallazgos=None)` |
| `prototipo/orden.py` | Modificar | `construir(decision, alerta, perfil=None)` |
| `prototipo/lazo.py` | Modificar | pasa el perfil a `orden.construir` |
| `prototipo/agente_mitigacion.py` | Modificar | topología enriquecida, `consultar_topologia`, prompt con la IP de gestión, `bucle_react(..., hallazgos=None)` |
| `evaluacion/metricas.py` · `evaluacion/campana.py` | Modificar | `bloqueos_automaticos_indebidos`; sección `automatizacion` |
| `prototipo/perfiles/empresarial.yml` · `bancario.yml` | Modificar | inventario con `ip`/`funcion`, `redes_internas`, `continuidad.actores` |
| `lab/scripts/demo-agente-escalado.py` · `demo-escalada-determinista.py` | Modificar | `gateway` → `borde` |
| Tests `prototipo/tests/test_{actores,impacto,inventario}.py` | Crear | |
| Tests `test_{perfil,rnf14,triaje,traza,validacion,stream,orden,lazo,agente_mitigacion}.py`, `evaluacion/tests/test_{metricas,campana}.py` | Modificar | |
| Documentación (Tarea 10) | Modificar | resultados, estado, requisitos, READMEs, `docs/pruebas`, guía de operación |

## Antes de la Tarea 1

- [ ] **Crear la rama y comprobar el punto de partida**

```bash
git checkout main && git checkout -b feature/conciencia-impacto
PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t . 2>&1 | tail -1   # OK (306)
PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests -t . 2>&1 | tail -1  # OK (39)
PYTHONPATH=. python3 -m unittest discover -s lab/dataset/tests -t . 2>&1 | tail -1 # OK
```

---

## NIVEL 1 (obligatorio)

### Task 1: `actores.py` — ¿quién es esta IP para el cliente?

**Files:**
- Create: `prototipo/actores.py`
- Test: `prototipo/tests/test_actores.py`

**Interfaces:**
- Produces:
  - `actores.quien_es(ip: str|None, perfil: dict) -> dict|None`: devuelve `{"tipo": "gestion"|"dispositivo_red"|"activo_interno"|"desconocido", "nombre": str|None, "funcion": str|None, "ip": str, "por": "ip_gestion"|"topologia"|"inventario"|"redes_internas"|"origenes_legitimos"|None}`, o `None` si no hay IP.
  - `actores.politica(perfil: dict, tipo: str) -> "humano_siempre"|"automatica_si_confianza"`.
  - Constantes: `actores.TIPOS_CON_POLITICA = ("activo_interno", "dispositivo_red")` y `actores.POLITICA_POR_DEFECTO = "humano_siempre"`.

- [ ] **Step 1: Write the failing test** — `prototipo/tests/test_actores.py`

```python
import unittest
from prototipo import actores

PERFIL = {
    "ip_gestion": "172.20.20.4",
    "activos": {
        "puesto": {"ip": "192.168.1.10", "funcion": "puesto de trabajo de un empleado"},
        "borde": {"ip": "192.168.1.1", "funcion": "equipo de borde: enruta la LAN"},
    },
    "topologia": {
        "objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
        "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"},
    },
    "redes_internas": ["10.0.0.0/8"],
    "origenes_legitimos": ["198.51.100.7"],
}


class TestQuienEs(unittest.TestCase):
    def test_canal_de_gestion(self):
        a = actores.quien_es("172.20.20.4", PERFIL)
        self.assertEqual((a["tipo"], a["por"]), ("gestion", "ip_gestion"))

    def test_dispositivo_de_red_por_su_rol_en_la_topologia(self):
        a = actores.quien_es("192.168.1.1", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"]), ("dispositivo_red", "borde"))
        self.assertEqual(a["funcion"], "equipo de borde: enruta la LAN")   # la función sale del inventario

    def test_activo_del_inventario(self):
        a = actores.quien_es("192.168.1.10", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"]), ("activo_interno", "puesto", "inventario"))
        self.assertEqual(a["funcion"], "puesto de trabajo de un empleado")

    def test_otro_nodo_de_la_topologia_es_interno(self):
        a = actores.quien_es("192.168.1.30", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"]), ("activo_interno", "objetivo-vuln", "topologia"))

    def test_ip_dentro_de_las_redes_internas(self):
        a = actores.quien_es("10.40.0.99", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"]), ("activo_interno", None, "redes_internas"))

    def test_origen_legitimo_es_interno(self):
        a = actores.quien_es("198.51.100.7", PERFIL)
        self.assertEqual((a["tipo"], a["por"]), ("activo_interno", "origenes_legitimos"))

    def test_lo_no_declarado_es_desconocido(self):
        a = actores.quien_es("203.0.113.9", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"], a["ip"]), ("desconocido", None, None, "203.0.113.9"))

    def test_la_gestion_gana_a_todo(self):
        # la IP de gestión también es un activo inventariado: manda la gestión (precedencia 1)
        p = {**PERFIL, "activos": {"auditor": {"ip": "172.20.20.4"}}}
        self.assertEqual(actores.quien_es("172.20.20.4", p)["tipo"], "gestion")

    def test_el_rol_de_red_gana_al_inventario(self):
        # borde está en el inventario Y es cortafuegos en la topología: es dispositivo de red
        self.assertEqual(actores.quien_es("192.168.1.1", PERFIL)["tipo"], "dispositivo_red")

    def test_perfil_sin_ips_resuelve_todo_a_desconocido(self):
        # las fixtures actuales no declaran IPs: su comportamiento no cambia
        p = {"activos": {"puesto": {"criticidad": "media"}}, "continuidad": {}}
        for ip in ("192.168.1.10", "192.168.1.1", "10.0.0.1"):
            self.assertEqual(actores.quien_es(ip, p)["tipo"], "desconocido")

    def test_sin_ip_no_hay_actor(self):
        self.assertIsNone(actores.quien_es(None, PERFIL))
        self.assertIsNone(actores.quien_es("", PERFIL))

    def test_una_ip_mal_formada_no_rompe_y_es_desconocida(self):
        self.assertEqual(actores.quien_es("no-es-una-ip", PERFIL)["tipo"], "desconocido")

    def test_un_cidr_invalido_en_el_perfil_es_error_de_configuracion(self):
        # tratarlo como «fuera de las redes internas» desprotegería esas IPs: debe verse
        with self.assertRaises(ValueError):
            actores.quien_es("10.0.0.1", {"redes_internas": ["10.0.0.0/33"]})


class TestPolitica(unittest.TestCase):
    def test_por_defecto_humano_siempre(self):   # C1
        self.assertEqual(actores.politica({}, "activo_interno"), "humano_siempre")
        self.assertEqual(actores.politica({"continuidad": {}}, "dispositivo_red"), "humano_siempre")

    def test_configurable_por_perfil(self):
        p = {"continuidad": {"actores": {"activo_interno": "automatica_si_confianza"}}}
        self.assertEqual(actores.politica(p, "activo_interno"), "automatica_si_confianza")
        self.assertEqual(actores.politica(p, "dispositivo_red"), "humano_siempre")

    def test_un_valor_desconocido_no_desprotege(self):
        # una errata en el perfil no puede volver automático el bloqueo de lo propio
        p = {"continuidad": {"actores": {"activo_interno": "automatico"}}}
        self.assertEqual(actores.politica(p, "activo_interno"), "humano_siempre")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_actores -v`
Expected: ERROR — `ImportError: cannot import name 'actores' from 'prototipo'`.

- [ ] **Step 3: Write minimal implementation** — `prototipo/actores.py`

```python
"""¿Quién es esta IP para el cliente? Resolución de actores desde el perfil (RF-17, RF-19).

Lo que el MDR sabe de una IP lo declara el cliente en su perfil (C3): el canal de gestión
(`ip_gestion`), la topología de contención, el inventario (`activos`), sus redes internas y sus
orígenes legítimos. Nada se adivina: una IP que no aparece en ninguna de esas fuentes es
`desconocido`, y un perfil sin IPs en el inventario resuelve todo a `desconocido` (comportamiento
idéntico al de antes de existir este módulo).
"""
import ipaddress

POLITICA_POR_DEFECTO = "humano_siempre"          # C1: bloquear lo propio exige humano
POLITICAS = ("humano_siempre", "automatica_si_confianza")
TIPOS_CON_POLITICA = ("activo_interno", "dispositivo_red")
_ROL_RED = "firewall_perimetral"


def _actor(tipo, ip, por, nombre=None, funcion=None):
    return {"tipo": tipo, "nombre": nombre, "funcion": funcion, "ip": ip, "por": por}


def _en_redes(ip, redes):
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False                 # no es una IP (p. ej. un nombre): no está en ninguna red
    # Un CIDR mal escrito lanza ValueError: es un error de configuración y debe verse; tratarlo
    # como «fuera de las redes internas» desprotegería esas IPs.
    return any(direccion in ipaddress.ip_network(red, strict=False) for red in redes or [])


def quien_es(ip, perfil):
    """Actor al que afecta bloquear `ip`: {tipo, nombre, funcion, ip, por}, o None si no hay IP.

    Precedencia (la primera que encaja): gestion > dispositivo_red (nodo de `topologia` con rol
    firewall_perimetral) > activo_interno (activo del inventario, otro nodo de `topologia`, IP de
    `redes_internas` u origen legítimo) > desconocido. `por` dice de qué declaración sale."""
    if not ip:
        return None
    perfil = perfil or {}
    if ip == perfil.get("ip_gestion"):
        return _actor("gestion", ip, "ip_gestion")
    activos = perfil.get("activos") or {}
    topologia = perfil.get("topologia") or {}

    def _funcion(nombre):
        return (activos.get(nombre) or {}).get("funcion")

    for nombre, nodo in topologia.items():
        if isinstance(nodo, dict) and nodo.get("ip") == ip and nodo.get("rol") == _ROL_RED:
            return _actor("dispositivo_red", ip, "topologia", nombre, _funcion(nombre))
    for nombre, activo in activos.items():
        if isinstance(activo, dict) and activo.get("ip") == ip:
            return _actor("activo_interno", ip, "inventario", nombre, activo.get("funcion"))
    for nombre, nodo in topologia.items():
        if isinstance(nodo, dict) and nodo.get("ip") == ip:
            return _actor("activo_interno", ip, "topologia", nombre, _funcion(nombre))
    if _en_redes(ip, perfil.get("redes_internas")):
        return _actor("activo_interno", ip, "redes_internas")
    if ip in (perfil.get("origenes_legitimos") or []):
        return _actor("activo_interno", ip, "origenes_legitimos")
    return _actor("desconocido", ip, None)


def politica(perfil, tipo):
    """Política del perfil para bloquear un actor de `tipo` (`continuidad.actores`). Por defecto
    `humano_siempre` (C1). Un valor que no es una política conocida también cae a
    `humano_siempre`: una errata no puede volver automático el bloqueo de lo propio."""
    valor = (((perfil or {}).get("continuidad") or {}).get("actores") or {}).get(tipo)
    return valor if valor in POLITICAS else POLITICA_POR_DEFECTO
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_actores -v`
Expected: PASS (16 tests).

- [ ] **Step 5: Commit**

```bash
git add prototipo/actores.py prototipo/tests/test_actores.py
git commit -m "feat(actores): quien es una IP para el cliente, resuelto solo desde el perfil (RF-17/19)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `impacto.py` — impacto determinado de una acción

**Files:**
- Create: `prototipo/impacto.py`
- Test: `prototipo/tests/test_impacto.py`

**Interfaces:**
- Consumes: `actores.quien_es(ip, perfil)` (Task 1).
- Produces:
  - `impacto.determinar(accion_id, params, activo, perfil, catalogo, hallazgos=None) -> dict`: devuelve `{"nivel", "nivel_catalogo", "servicios_afectados": [{"puerto", "servicio", "declarado": bool, "abierto": bool|None}], "actor": dict|None, "activo", "accion_id", "motivo": str}`.
  - `impacto.puertos_abiertos(hallazgos, activo) -> dict[int, str] | None` (`None` = nodo no escaneado).
  - Constantes: `impacto.NIVELES`, `ACCIONES_SOBRE_IP`, `ACCIONES_SOBRE_PUERTO` y `ACCIONES_SOBRE_NODO`.

Formato del hallazgo del auditor (`lab/campañas/2026-08-31-evaluacion/hallazgos.json`): `{"nodos": {"objetivo-vuln": [{"puerto": 21, "servicio": "ftp", "estado": "open"}, …], "puesto": []}}`. Un nodo **ausente** de `nodos` es «no escaneado»; `[]` es «escaneado, sin servicios».

- [ ] **Step 1: Write the failing test** — `prototipo/tests/test_impacto.py`

```python
import os, unittest
from prototipo import impacto, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
PERFIL = {
    "ip_gestion": "172.20.20.4",
    "activos": {
        "objetivo-vuln": {"ip": "192.168.1.30", "funcion": "servidor con servicios expuestos",
                          "criticidad": "media", "servicios_prestados": [22, 80]},
        "puesto": {"ip": "192.168.1.10", "funcion": "puesto de trabajo de un empleado",
                   "criticidad": "media", "servicios_prestados": []},
        "borde": {"ip": "192.168.1.1", "funcion": "equipo de borde: enruta la LAN",
                  "criticidad": "media", "servicios_prestados": []},
    },
    "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                  "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
}
HALLAZGOS = {"nodos": {
    "objetivo-vuln": [{"puerto": 21, "servicio": "ftp", "estado": "open"},
                      {"puerto": 22, "servicio": "ssh", "estado": "open"},
                      {"puerto": 3306, "servicio": "mysql", "estado": "open"},
                      {"puerto": 8080, "servicio": "http-proxy", "estado": "closed"}],
    "puesto": []}}


class TestAccionesSobreIP(unittest.TestCase):
    def test_bloquear_un_activo_interno_nombra_a_quien(self):
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "192.168.1.10"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["nombre"], "puesto")
        self.assertEqual(d["nivel"], "localizado")            # un host interno no sube el nivel
        self.assertEqual(d["servicios_afectados"], [])
        self.assertEqual(d["motivo"],
                         "bloquea a puesto (activo interno: puesto de trabajo de un empleado) · 0 servicios detenidos")

    def test_bloquear_un_dispositivo_de_red_sube_a_alcanza_servicio(self):
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "192.168.1.1"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["tipo"], "dispositivo_red")
        self.assertEqual((d["nivel_catalogo"], d["nivel"]), ("localizado", "alcanza_servicio"))
        self.assertIn("todo lo que enruta", d["motivo"])

    def test_un_origen_externo_queda_como_en_el_catalogo(self):
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "203.0.113.9"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["tipo"], "desconocido")
        self.assertEqual(d["nivel"], "localizado")
        self.assertEqual(d["motivo"], "bloquea a 203.0.113.9 (origen no inventariado) · 0 servicios detenidos")

    def test_matar_conexion_tambien_resuelve_el_actor(self):
        d = impacto.determinar("MATAR_CONEXION", {"ip": "192.168.1.10"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["nombre"], "puesto")

    def test_nunca_por_debajo_del_catalogo(self):   # C2
        d = impacto.determinar("BLOQUEAR_IP_FIREWALL", {"ip": "203.0.113.9"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["nivel"], "alcanza_servicio")      # el catálogo ya dice alcanza_servicio

    def test_sin_ip_no_hay_actor(self):
        d = impacto.determinar("BLOQUEAR_IP", {}, "objetivo-vuln", PERFIL, CAT)
        self.assertIsNone(d["actor"])


class TestAccionesSobrePuerto(unittest.TestCase):
    def test_bloquear_puerto_declarado_y_abierto(self):
        d = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": 22}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        self.assertEqual(d["servicios_afectados"],
                         [{"puerto": 22, "servicio": "ssh", "declarado": True, "abierto": True}])
        self.assertEqual(d["nivel"], "alcanza_servicio")
        self.assertIsNone(d["actor"])

    def test_el_cruce_es_por_puerto_aunque_llegue_como_texto(self):
        d = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": "80"}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        s = d["servicios_afectados"][0]
        self.assertEqual((s["puerto"], s["declarado"], s["abierto"]), (80, True, False))

    def test_cerrar_servicio_empareja_por_nombre(self):
        d = impacto.determinar("CERRAR_SERVICIO", {"servicio": "mysql"}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        self.assertEqual(d["servicios_afectados"],
                         [{"puerto": 3306, "servicio": "mysql", "declarado": False, "abierto": True}])
        self.assertIn("no declarado", d["motivo"])

    def test_sin_hallazgos_no_se_inventa_el_estado(self):   # RNF-07
        d = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": 22}, "objetivo-vuln", PERFIL, CAT)
        self.assertIsNone(d["servicios_afectados"][0]["abierto"])
        self.assertIn("sin datos del auditor", d["motivo"])


class TestAccionesSobreNodo(unittest.TestCase):
    def test_aislar_nodo_da_el_radio_de_impacto(self):
        d = impacto.determinar("AISLAR_NODO", {"ip_nodo": "192.168.1.30"}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        # declarados ∪ abiertos; el 8080 está cerrado y no cuenta
        self.assertEqual([s["puerto"] for s in d["servicios_afectados"]], [21, 22, 80, 3306])
        self.assertIn("detendría 4 servicio(s) de objetivo-vuln (criticidad media)", d["motivo"])

    def test_nodo_sin_servicios_conocidos(self):
        d = impacto.determinar("AISLAR_NODO", {}, "puesto", PERFIL, CAT, HALLAZGOS)
        self.assertEqual(d["servicios_afectados"], [])
        self.assertIn("sin servicios conocidos", d["motivo"])


class TestObservacion(unittest.TestCase):
    def test_observar_no_tiene_impacto(self):
        d = impacto.determinar("OBS_CONEXIONES", {}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        self.assertEqual((d["nivel"], d["servicios_afectados"], d["actor"]), ("ninguno", [], None))


class TestPuertosAbiertos(unittest.TestCase):
    def test_no_escaneado_es_none_y_escaneado_sin_servicios_es_vacio(self):   # RNF-07
        self.assertIsNone(impacto.puertos_abiertos(HALLAZGOS, "iot"))
        self.assertEqual(impacto.puertos_abiertos(HALLAZGOS, "puesto"), {})
        self.assertIsNone(impacto.puertos_abiertos(None, "puesto"))

    def test_solo_los_abiertos_con_puerto(self):
        self.assertEqual(impacto.puertos_abiertos(HALLAZGOS, "objetivo-vuln"),
                         {21: "ftp", 22: "ssh", 3306: "mysql"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_impacto -v`
Expected: ERROR — `ImportError: cannot import name 'impacto' from 'prototipo'`.

- [ ] **Step 3: Write minimal implementation** — `prototipo/impacto.py`

```python
"""Impacto DETERMINADO de una acción (RF-17): qué servicios toca y a quién bloquea.

El catálogo declara un impacto fijo por tipo de acción (`BLOQUEAR_IP` siempre «localizado», bloquee
a quien bloquee). Aquí se determina a partir del inventario del perfil y de los hallazgos del
auditor: a quién afecta bloquear una IP (`actores.quien_es`), qué servicio detiene cerrar un puerto
y cuántos servicios caen al aislar un nodo (el radio de impacto: una cota superior, porque un
puerto abierto no implica que alguien lo use).

C2: el nivel determinado nunca queda por debajo del catálogo; solo lo mantiene o lo sube. Un
inventario incompleto no puede rebajar una protección.
"""
from prototipo import actores

NIVELES = ("ninguno", "localizado", "alcanza_servicio")
ACCIONES_SOBRE_IP = frozenset({"BLOQUEAR_IP", "BLOQUEAR_IP_FIREWALL", "MATAR_CONEXION"})
ACCIONES_SOBRE_PUERTO = frozenset({"BLOQUEAR_PUERTO", "CERRAR_SERVICIO"})
ACCIONES_SOBRE_NODO = frozenset({"AISLAR_NODO", "REINICIAR_NODO"})
_TOPE_LISTA = 4
_TIPO_LEGIBLE = {"gestion": "canal de gestión del MDR", "dispositivo_red": "dispositivo de red",
                 "activo_interno": "activo interno", "desconocido": "origen no inventariado"}
_POR_LEGIBLE = {"redes_internas": "IP de las redes internas del cliente",
                "origenes_legitimos": "origen legítimo declarado"}


def _max_nivel(a, b):
    return a if NIVELES.index(a) >= NIVELES.index(b) else b


def _activo(perfil, nombre):
    return ((perfil or {}).get("activos") or {}).get(nombre) or {}


def _puerto(valor):
    # Los hallazgos y servicios_prestados son enteros; un puerto puede llegar como texto ("80").
    try:
        return int(valor)
    except (TypeError, ValueError):
        return valor


def puertos_abiertos(hallazgos, activo):
    """{puerto: servicio} abiertos del activo según el auditor, o None si el nodo no se escaneó:
    no escaneado no es «sin servicios» (RNF-07)."""
    nodos = (hallazgos or {}).get("nodos")
    if not isinstance(nodos, dict) or activo not in nodos:
        return None
    return {s["puerto"]: s.get("servicio") for s in nodos[activo] or []
            if s.get("estado") == "open" and s.get("puerto") is not None}


def _servicio(puerto, nombre, declarados, abiertos):
    return {"puerto": puerto,
            "servicio": nombre if nombre else (abiertos or {}).get(puerto),
            "declarado": puerto in declarados,
            "abierto": None if abiertos is None else puerto in abiertos}


def _declarados(perfil, activo):
    return {_puerto(p) for p in _activo(perfil, activo).get("servicios_prestados") or []}


def _servicios_de_puerto(accion_id, params, activo, perfil, hallazgos):
    declarados, abiertos = _declarados(perfil, activo), puertos_abiertos(hallazgos, activo)
    if accion_id == "BLOQUEAR_PUERTO":
        return [_servicio(_puerto(params.get("puerto")), None, declarados, abiertos)]
    # CERRAR_SERVICIO llega por nombre: el puerto sale de los hallazgos.
    nombre = params.get("servicio")
    puertos = sorted(p for p, s in (abiertos or {}).items() if s == nombre)
    return ([_servicio(p, nombre, declarados, abiertos) for p in puertos]
            or [_servicio(None, nombre, declarados, abiertos)])


def _servicios_del_nodo(activo, perfil, hallazgos):
    declarados, abiertos = _declarados(perfil, activo), puertos_abiertos(hallazgos, activo)
    return [_servicio(p, None, declarados, abiertos) for p in sorted(declarados | set(abiertos or {}))]


def _quien(actor):
    nombre = actor["nombre"] or actor["ip"]
    detalle = actor["funcion"] or _POR_LEGIBLE.get(actor["por"])
    tipo = _TIPO_LEGIBLE[actor["tipo"]]
    return f"{nombre} ({tipo}: {detalle})" if detalle else f"{nombre} ({tipo})"


def _etiqueta(s):
    if s["servicio"] and s["puerto"] is not None:
        return f"{s['servicio']}/{s['puerto']}"
    return str(s["servicio"] or s["puerto"])


def _estado(s):
    abierto = {True: "abierto según el auditor", False: "no abierto según el auditor",
               None: "sin datos del auditor"}[s["abierto"]]
    return f"{'declarado' if s['declarado'] else 'no declarado'} · {abierto}"


def _lista(servicios):
    etiquetas = [_etiqueta(s) for s in servicios]
    if len(etiquetas) <= _TOPE_LISTA:
        return ", ".join(etiquetas)
    return ", ".join(etiquetas[:_TOPE_LISTA]) + f" y {len(etiquetas) - _TOPE_LISTA} más"


def _motivo(det, perfil):
    """Una línea para el analista y el daemon: la consecuencia de ejecutar la acción."""
    accion, actor, servicios = det["accion_id"], det["actor"], det["servicios_afectados"]
    if accion in ACCIONES_SOBRE_IP:
        if actor is None:
            return "sin IP que bloquear"
        texto = f"bloquea a {_quien(actor)} · 0 servicios detenidos"
        if det["nivel"] != det["nivel_catalogo"]:
            texto += (f" · sube de {det['nivel_catalogo']} a {det['nivel']}: "
                      "un dispositivo de red puede cortar todo lo que enruta")
        return texto
    if accion in ACCIONES_SOBRE_PUERTO:
        return "; ".join(f"detendría {_etiqueta(s)} en {det['activo']} ({_estado(s)})" for s in servicios)
    if accion in ACCIONES_SOBRE_NODO:
        criticidad = _activo(perfil, det["activo"]).get("criticidad", "media")
        if not servicios:
            return f"detendría {det['activo']} (criticidad {criticidad}): sin servicios conocidos"
        return (f"detendría {len(servicios)} servicio(s) de {det['activo']} (criticidad {criticidad}): "
                f"{_lista(servicios)}")
    return f"impacto del catálogo: {det['nivel']}"


def determinar(accion_id, params, activo, perfil, catalogo, hallazgos=None):
    """Impacto determinado de `accion_id` sobre `activo`: {nivel, nivel_catalogo,
    servicios_afectados, actor, activo, accion_id, motivo}."""
    params = params or {}
    nivel_catalogo = (catalogo.get(accion_id) or {}).get("impacto", "ninguno")
    nivel, servicios, actor = nivel_catalogo, [], None
    if accion_id in ACCIONES_SOBRE_IP:
        actor = actores.quien_es(params.get("ip"), perfil)
        if actor and actor["tipo"] == "dispositivo_red":
            # Bloquear un gateway puede cortar todo lo que enruta (con NAT, todo).
            nivel = _max_nivel(nivel, "alcanza_servicio")
    elif accion_id in ACCIONES_SOBRE_PUERTO:
        servicios = _servicios_de_puerto(accion_id, params, activo, perfil, hallazgos)
    elif accion_id in ACCIONES_SOBRE_NODO:
        servicios = _servicios_del_nodo(activo, perfil, hallazgos)
    det = {"nivel": nivel, "nivel_catalogo": nivel_catalogo, "servicios_afectados": servicios,
           "actor": actor, "activo": activo, "accion_id": accion_id}
    det["motivo"] = _motivo(det, perfil)
    return det
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_impacto -v`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add prototipo/impacto.py prototipo/tests/test_impacto.py
git commit -m "feat(impacto): impacto determinado desde el inventario, nunca por debajo del catalogo (RF-17, C2)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `perfil.filtrar` con conciencia de actores (C1, C4, C5)

**Files:**
- Modify: `prototipo/perfil.py` (imports, `UMBRAL_CONFIANZA` comment, `filtrar` → `_filtrar_reglas` + `_aplicar_actor` + nuevo `filtrar`)
- Test: `prototipo/tests/test_perfil.py` (nueva clase `TestConcienciaDeActores`)

**Interfaces:**
- Consumes:
  - `actores.politica`, `actores.TIPOS_CON_POLITICA` (Task 1);
  - `impacto.determinar` (Task 2).
- Produces: `perfil.filtrar(perfil, accion_id, params, catalogo, activo, servicio, confianza, hallazgos=None) -> {"resultado", "accion_final", "requiere_humano", "impacto": dict}`.
  - La clave `impacto` falta cuando la acción es `None` o no está en el catálogo.
  - Los llamadores actuales (siete argumentos posicionales) no cambian.

- [ ] **Step 1: Write the failing test** — añadir al final de `prototipo/tests/test_perfil.py`

```python
PERFIL_INV = {
    "ip_gestion": "172.20.20.4",
    "activos": {"puesto": {"ip": "192.168.1.10", "funcion": "puesto de trabajo de un empleado"},
                "borde": {"ip": "192.168.1.1", "funcion": "equipo de borde"}},
    "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                  "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
    "continuidad": {"impacto_ninguno": "automatica", "impacto_localizado": "automatica_si_confianza",
                    "impacto_alcanza_servicio": "humano_siempre", "reversibilidad_obligatoria": True,
                    "no_cortar_gestion": True},
}


class TestConcienciaDeActores(unittest.TestCase):
    """Spec de conciencia de impacto §4.4: a quién bloquea la acción FINAL gobierna el filtro."""

    def _filtrar(self, accion, params, p=PERFIL_INV, **kw):
        return perfil.filtrar(p, accion, params, CAT, "objetivo-vuln", "ssh", 1.0, **kw)

    def test_bloquear_la_gestion_es_veto_duro(self):   # RF-19, C4
        r = self._filtrar("BLOQUEAR_IP", {"ip": "172.20.20.4"})
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]), ("veta", None, True))

    def test_bloquear_un_activo_interno_se_retiene_para_el_humano(self):   # C1
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.10"})
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]), ("veta", "BLOQUEAR_IP", True))

    def test_bloquear_un_dispositivo_de_red_se_retiene(self):
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.1"})
        self.assertEqual((r["accion_final"], r["requiere_humano"]), ("BLOQUEAR_IP", True))
        self.assertEqual(r["impacto"]["nivel"], "alcanza_servicio")

    def test_un_origen_externo_sigue_automatico(self):
        r = self._filtrar("BLOQUEAR_IP", {"ip": "203.0.113.9"})
        self.assertEqual((r["resultado"], r["requiere_humano"]), ("permite", False))

    def test_la_politica_por_actor_es_configurable(self):
        p = {**PERFIL_INV, "continuidad": {**PERFIL_INV["continuidad"],
                                            "actores": {"activo_interno": "automatica_si_confianza"}}}
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.10"}, p=p)
        self.assertEqual((r["resultado"], r["requiere_humano"]), ("permite", False))

    def test_con_politica_permisiva_el_dispositivo_de_red_sigue_protegido_por_su_nivel(self):   # C2
        p = {**PERFIL_INV, "continuidad": {**PERFIL_INV["continuidad"],
                                            "actores": {"dispositivo_red": "automatica_si_confianza"}}}
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.1"}, p=p)
        self.assertTrue(r["requiere_humano"])      # alcanza_servicio -> humano_siempre en este perfil

    def test_la_retencion_mira_la_accion_final_tras_degradar(self):
        # BLOQUEAR_PUERTO degrada a BLOQUEAR_IP; si esa IP es un activo interno, pide humano
        r = self._filtrar("BLOQUEAR_PUERTO", {"puerto": 22, "ip": "192.168.1.10"})
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]),
                         ("degrada", "BLOQUEAR_IP", True))
        self.assertEqual(r["impacto"]["accion_id"], "BLOQUEAR_IP")

    def test_el_resultado_lleva_el_impacto_determinado(self):
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.10"})
        self.assertEqual(r["impacto"]["actor"]["nombre"], "puesto")
        self.assertIn("puesto", r["impacto"]["motivo"])

    def test_los_hallazgos_llegan_al_impacto(self):
        h = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        r = self._filtrar("CERRAR_SERVICIO", {"servicio": "ssh"}, hallazgos=h)
        self.assertIsNone(r["accion_final"])       # corta_gestion_si: ssh -> veto duro (RF-19), como siempre
        self.assertTrue(r["impacto"]["servicios_afectados"][0]["abierto"])

    def test_perfil_sin_ips_se_comporta_como_antes(self):   # regresión: las fixtures no declaran IPs
        r = perfil.filtrar(perfil_fx(), "BLOQUEAR_IP", {"ip": "192.168.1.10"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]), ("permite", "BLOQUEAR_IP", False))
        self.assertEqual(r["impacto"]["actor"]["tipo"], "desconocido")

    def test_sin_accion_no_lleva_impacto(self):
        self.assertNotIn("impacto", self._filtrar(None, {}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_perfil -v`
Expected: FAIL/ERROR in `TestConcienciaDeActores`:
- `KeyError: 'impacto'`;
- `TypeError: filtrar() got an unexpected keyword argument 'hallazgos'`;
- `permite` where `veta` was expected.

The rest of the suite must still pass.

- [ ] **Step 3: Write minimal implementation** — `prototipo/perfil.py`

Replace the import block and the constant line (lines 1–5) with:

```python
"""El perfil de cliente (V3/V4) y el filtro permite/degrada/veta (RNF-14, RF-17/18/19)."""
import yaml
from prototipo import actores, impacto as impactom
from prototipo import catalogo as _cat

UMBRAL_CONFIANZA = 0.7   # default; configurable por perfil en continuidad.umbral_confianza (RF-07). Sin calibrar aún (barrido pendiente)
```

Replace the whole `def filtrar(...)` (lines 51–84) with:

```python
def _filtrar_reglas(perfil, accion_id, params, catalogo, activo, servicio, confianza, nivel):
    """Las reglas de continuidad de siempre (RF-17 a RF-19), aplicadas con el nivel de impacto
    DETERMINADO (`nivel`, nunca por debajo del catálogo: C2)."""
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
    regla = cont.get(f"impacto_{nivel}", "humano_siempre")
    if regla == "automatica":
        return _res("permite", accion_id, False)
    if regla == "automatica_si_confianza":
        if confianza >= _umbral(perfil):
            return _res("permite", accion_id, False)
        return _res("veta", accion_id, True)
    # regla == "humano_siempre" (impacto alcanza_servicio): intentar degradar
    alt = DEGRADACION.get(accion_id)
    if alt is not None:
        if _permite_localizado(perfil, confianza):
            return _res("degrada", alt, False)
        return _res("degrada", alt, True)
    return _res("veta", accion_id, True)

def _aplicar_actor(res, perfil, det):
    """A quién bloquea la acción FINAL (C1, C4). El canal de gestión es veto duro (RF-19): cortarlo
    impide la siguiente respuesta y la verificación. Un activo interno o un dispositivo de red con
    política `humano_siempre` queda retenido para validación humana (el analista puede aprobarlo)."""
    actor = det.get("actor")
    if not res["accion_final"] or not actor:
        return res
    if actor["tipo"] == "gestion":
        return _res("veta", None, True)
    if (actor["tipo"] in actores.TIPOS_CON_POLITICA
            and actores.politica(perfil, actor["tipo"]) == "humano_siempre"):
        return _res("degrada" if res["resultado"] == "degrada" else "veta", res["accion_final"], True)
    return res

def filtrar(perfil, accion_id, params, catalogo, activo, servicio, confianza, hallazgos=None):
    """permite / degrada / veta. El resultado lleva `impacto`: el impacto DETERMINADO de la acción
    final (a quién bloquea y qué servicios detiene, `impacto.determinar`). Quien no lo use sigue
    funcionando igual. La conciencia de actores vive aquí (C5) para que ningún punto de decisión
    —tampoco un salto de la escalada— pueda saltársela."""
    if accion_id is None:
        return _res("sin_accion", None, False)
    if accion_id not in catalogo:
        return _res("veta", None, True)
    det = impactom.determinar(accion_id, params, activo, perfil, catalogo, hallazgos)
    res = _filtrar_reglas(perfil, accion_id, params, catalogo, activo, servicio, confianza, det["nivel"])
    if res["accion_final"] and res["accion_final"] != accion_id:   # degradada: se ejecuta otra acción
        det = impactom.determinar(res["accion_final"], params, activo, perfil, catalogo, hallazgos)
    return {**_aplicar_actor(res, perfil, det), "impacto": det}
```

- [ ] **Step 4: Run tests to verify they pass (full suite: nothing else may change)**

Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .`
Expected: OK (306 + 16 + 15 + 11 = 348 tests).

- [ ] **Step 5: Commit**

```bash
git add prototipo/perfil.py prototipo/tests/test_perfil.py
git commit -m "feat(perfil): el filtro sabe a quien bloquea: gestion veto duro, lo propio al humano (C1/C4/C5)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: la consecuencia llega a la traza, al analista y al daemon

**Files:**
- Modify:
  - `prototipo/triaje.py:19-20` (pasar `hallazgos`);
  - `prototipo/traza.py:207-231` (campo `impacto_determinado`);
  - `prototipo/validacion.py:14-25` (línea «Consecuencia:»);
  - `prototipo/stream.py:33-47` (línea «Consecuencia:»).
- Test:
  - `prototipo/tests/test_triaje.py`;
  - `prototipo/tests/test_traza.py`;
  - `prototipo/tests/test_validacion.py`;
  - `prototipo/tests/test_stream.py`.

**Interfaces:**
- Consumes: `perfil.filtrar(..., hallazgos=...)` con la clave `impacto` (Task 3).
- Produces: la traza tiene `impacto_determinado: dict|None` (el dict de `impacto.determinar`). `validacion.mostrar` y `stream._linea_decision` muestran `impacto_determinado["motivo"]` tras la etiqueta «Consecuencia:».

- [ ] **Step 1: Write the failing tests**

Add to `prototipo/tests/test_traza.py`, inside `class TestConstruir`:

```python
    def test_registra_el_impacto_determinado(self):
        det = {"nivel": "localizado", "actor": {"tipo": "activo_interno", "nombre": "puesto"},
               "motivo": "bloquea a puesto (activo interno) · 0 servicios detenidos"}
        r = traza.construir("d1", "t", {"id_alerta": "a1"}, {"clase": "vp_intento_acceso"},
                            "BLOQUEAR_IP", "localizado", "empresarial",
                            {"resultado": "veta", "accion_final": "BLOQUEAR_IP", "requiere_humano": True,
                             "impacto": det}, "v0")
        self.assertEqual(r["impacto_determinado"], det)

    def test_sin_impacto_determinado_queda_none(self):
        r = traza.construir("d1", "t", {"id_alerta": "a1"}, {"clase": "no_soportada"}, None, "ninguno",
                            "empresarial", {"resultado": "sin_accion", "accion_final": None,
                                            "requiere_humano": False}, "v0")
        self.assertIsNone(r["impacto_determinado"])
```

Add to `prototipo/tests/test_triaje.py` (new class at the end of the file):

```python
class TestImpactoDeterminado(unittest.TestCase):
    def test_la_traza_lleva_el_impacto_determinado(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["impacto_determinado"]["accion_id"], "BLOQUEAR_IP")
        self.assertEqual(r["impacto_determinado"]["actor"]["tipo"], "desconocido")   # la fixture no declara IPs

    def test_con_inventario_el_bloqueo_del_puesto_va_al_humano(self):
        p = y("perfil.yml")
        p["activos"]["puesto"]["ip"] = "192.168.1.10"
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), p, "prueba", CAT,
                            id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_intento_acceso")            # la clasificación no cambia
        self.assertEqual((r["resultado_filtro"], r["requiere_humano"]), ("veta", True))
        self.assertEqual(r["impacto_determinado"]["actor"]["nombre"], "puesto")

    def test_pasa_los_hallazgos_al_filtro(self):
        from unittest import mock
        from prototipo import perfil as perfilm
        h = j("hallazgos.json")
        with mock.patch.object(perfilm, "filtrar", wraps=perfilm.filtrar) as f:
            triaje.procesar(j("alerta_vp.json"), h, y("perfil.yml"), "prueba", CAT, "d1", "t")
        self.assertIs(f.call_args.kwargs["hallazgos"], h)

    def test_sin_accion_no_hay_impacto_determinado(self):
        alerta = {"familia": "explotacion_conocida", "origen_ip": "203.0.113.9",
                  "activo": "web-banking", "servicio": "https", "mitre": ["T1190"]}
        tr = triaje.procesar(alerta, {"nodos": {}}, {"activos": {}, "continuidad": {}}, "p", CAT, "d1", "t")
        self.assertIsNone(tr["impacto_determinado"])
```

Add to `prototipo/tests/test_validacion.py`, inside `class TestValidacion`:

```python
    def test_mostrar_incluye_la_consecuencia(self):
        dec = dict(DECISION)
        dec["impacto_determinado"] = {"motivo": "bloquea a puesto (activo interno: puesto de trabajo de un "
                                                "empleado) · 0 servicios detenidos"}
        txt = validacion.mostrar(dec, ALERTA)
        self.assertIn("Consecuencia: bloquea a puesto (activo interno", txt)

    def test_mostrar_sin_impacto_determinado_no_la_inventa(self):
        self.assertNotIn("Consecuencia", validacion.mostrar(DECISION, ALERTA))
```

Add to `prototipo/tests/test_stream.py`, inside `class TestStream`:

```python
    def test_linea_decision_muestra_la_consecuencia(self):
        d = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0,
             "accion_propuesta": "BLOQUEAR_IP", "accion_final": "BLOQUEAR_IP", "resultado_filtro": "veta",
             "version_justificador": "plantilla-0",
             "impacto_determinado": {"motivo": "bloquea a puesto (activo interno) · 0 servicios detenidos"}}
        self.assertIn("\n  Consecuencia: bloquea a puesto", stream._linea_decision(d))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_traza prototipo.tests.test_triaje prototipo.tests.test_validacion prototipo.tests.test_stream -v`
Expected: FAIL/ERROR in the 9 new tests (`KeyError: 'impacto_determinado'`, `'Consecuencia' not found`, `KeyError: 'hallazgos'`).

- [ ] **Step 3: Write minimal implementation**

`prototipo/triaje.py` — replace:
```python
    filtro = perfilm.filtrar(perfil_dict, accion, params, catalogo, alerta.get("activo"),
                             alerta.get("servicio"), clas["confianza"])
```
with:
```python
    filtro = perfilm.filtrar(perfil_dict, accion, params, catalogo, alerta.get("activo"),
                             alerta.get("servicio"), clas["confianza"], hallazgos=hallazgos)
```

`prototipo/traza.py` — in `construir`, after the line `"requiere_humano": filtro_out.get("requiere_humano"),` add:
```python
        "impacto_determinado": filtro_out.get("impacto"),   # a quién bloquea y qué detiene (RF-17)
```

`prototipo/validacion.py` — replace the whole `mostrar` with:
```python
def mostrar(decision, alerta):
    est = decision.get("justificacion_estructurada", {}) or {}
    mitre = ", ".join(est.get("tecnica_mitre") or []) or "—"
    # La consecuencia de aprobar: a quién bloquea y qué servicios detiene (impacto determinado, RF-17).
    det = decision.get("impacto_determinado") or {}
    consecuencia = f"Consecuencia: {det['motivo']}\n" if det.get("motivo") else ""
    return (
        "── Validación humana requerida ──\n"
        f"Activo: {alerta.get('activo')}  ·  Origen: {alerta.get('origen_ip')}  ·  Servicio: {alerta.get('servicio')}\n"
        f"Clase: {decision.get('clase')}  ·  Prioridad: {decision.get('prioridad')}  ·  Confianza: {decision.get('confianza')}\n"
        f"Técnica MITRE: {mitre}\n"
        f"Justificación: {decision.get('justificacion')}\n"
        f"Acción sugerida: {est.get('accion_sugerida', decision.get('accion_propuesta'))}  ·  Impacto: {decision.get('impacto')}  ·  Filtro: {decision.get('resultado_filtro')}\n"
        f"{consecuencia}"
        f"Acción final: {decision.get('accion_final')}\n"
    )
```

`prototipo/stream.py` — in `_linea_decision`, right after the `base = (...)` assignment, add:
```python
    det = d.get("impacto_determinado") or {}
    if det.get("motivo"):
        base += f"\n  Consecuencia: {det['motivo']}"
```

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .`
Expected: OK (357 tests).

- [ ] **Step 5: Commit**

```bash
git add prototipo/triaje.py prototipo/traza.py prototipo/validacion.py prototipo/stream.py \
        prototipo/tests/test_triaje.py prototipo/tests/test_traza.py prototipo/tests/test_validacion.py \
        prototipo/tests/test_stream.py
git commit -m "feat(traza): impacto_determinado en la traza y la consecuencia ante el analista y el daemon

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: la IP de ejecución sale del perfil (`perfil.ip_de`, `orden.construir`)

**Files:**
- Modify:
  - `prototipo/perfil.py` (añadir `ip_de` tras `criticidad_de`);
  - `prototipo/orden.py` (entero);
  - `prototipo/lazo.py:25`.
- Test:
  - `prototipo/tests/test_perfil.py`;
  - `prototipo/tests/test_orden.py`;
  - `prototipo/tests/test_lazo.py`.

**Interfaces:**
- Produces:
  - `perfil.ip_de(perfil, nodo) -> str|None`: busca en `activos[nodo].ip` y después en `topologia[nodo].ip`.
  - `orden.construir(decision, alerta, perfil=None)`: `nodo_ip` = `perfil.ip_de` y, si no hay, `IP_DE_NODO` como respaldo heredado.

Cierra el trabajo futuro «IP del activo desde la topología del perfil» (`estado-y-riesgos` §7). La Tarea 10 retira esa entrada.

- [ ] **Step 1: Write the failing tests**

Add to `prototipo/tests/test_perfil.py` (new class):

```python
class TestIpDe(unittest.TestCase):
    def test_del_inventario_antes_que_de_la_topologia(self):
        p = {"activos": {"web": {"ip": "10.10.0.10"}},
             "topologia": {"web": {"rol": "host_victima", "ip": "10.10.0.99"}}}
        self.assertEqual(perfil.ip_de(p, "web"), "10.10.0.10")

    def test_de_la_topologia_si_el_inventario_no_la_tiene(self):
        p = {"activos": {"web": {"criticidad": "alta"}},
             "topologia": {"web": {"rol": "host_victima", "ip": "10.10.0.99"}}}
        self.assertEqual(perfil.ip_de(p, "web"), "10.10.0.99")

    def test_none_si_el_perfil_no_la_declara(self):
        self.assertIsNone(perfil.ip_de({"activos": {}}, "web"))
        self.assertIsNone(perfil.ip_de({}, "web"))
```

Add to `prototipo/tests/test_orden.py`, inside `class TestConstruir`:

```python
    def test_la_ip_del_nodo_sale_del_perfil(self):
        d = dict(DECISION_VP, activo="web-banking")
        self.assertEqual(orden.construir(d, ALERTA, {"activos": {"web-banking": {"ip": "10.10.0.10"}}})["nodo_ip"],
                         "10.10.0.10")

    def test_sin_ip_en_el_perfil_cae_al_mapa_heredado(self):
        self.assertEqual(orden.construir(DECISION_VP, ALERTA, {"activos": {}})["nodo_ip"], "192.168.1.30")
```

Add to `prototipo/tests/test_lazo.py` (new class):

```python
class TestIpDelActivoDesdeElPerfil(unittest.TestCase):
    def test_la_orden_usa_la_ip_del_inventario(self):
        # Un activo que el mapa heredado del laboratorio no conoce: su IP sale del perfil.
        a = dict(j("alerta_vp.json")); a["activo"] = "web-banking"
        h = {"nodos": {"web-banking": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        p = y("perfil.yml"); p["activos"]["web-banking"] = {"ip": "10.10.0.10", "criticidad": "alta"}
        llamadas = []
        def ej(nodo_ip, cmd):
            llamadas.append(nodo_ip)
            return ejecutor_ok(nodo_ip, cmd)
        r = lazo.procesar_lazo(a, h, p, "prueba", CAT, ej, "d1", "t")
        self.assertEqual(r["orden"]["nodo_ip"], "10.10.0.10")
        self.assertIn("10.10.0.10", llamadas)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_perfil prototipo.tests.test_orden prototipo.tests.test_lazo -v`
Expected: ERROR `AttributeError: module 'prototipo.perfil' has no attribute 'ip_de'`; `TypeError: construir() takes 2 positional arguments but 3 were given`; the lazo test fails with `nodo_ip None`.

- [ ] **Step 3: Write minimal implementation**

`prototipo/perfil.py` — after `criticidad_de`, add:
```python
def ip_de(perfil, nodo):
    """IP de ejecución de `nodo` declarada en el perfil: la del inventario (`activos`) o, si no la
    tiene, la de la `topologia`. None si el perfil no la declara (orden.construir cae entonces al
    mapa heredado del laboratorio)."""
    activo = ((perfil or {}).get("activos") or {}).get(nodo) or {}
    nodo_top = ((perfil or {}).get("topologia") or {}).get(nodo)
    return activo.get("ip") or (nodo_top.get("ip") if isinstance(nodo_top, dict) else None)
```

`prototipo/orden.py` — replace the whole file with:
```python
"""Construye la orden de acción (mensaje) que el conector consume. Frontera motor↔conector."""
from prototipo import perfil as perfilm

# Respaldo heredado: mapa activo->IP del plano de datos del laboratorio, para perfiles que no
# declaran la IP del activo. La IP se resuelve primero del perfil (`perfil.ip_de`: inventario y
# topología del cliente, V4).
IP_DE_NODO = {
    "objetivo-vuln": "192.168.1.30", "puesto": "192.168.1.10",
    "iot": "192.168.1.20", "borde": "192.168.1.1",
}
_ACCIONES_SOBRE_ORIGEN = {"BLOQUEAR_IP", "MATAR_CONEXION"}

def construir(decision, alerta, perfil=None):
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
        "nodo_ip": (perfilm.ip_de(perfil, activo) if perfil else None) or IP_DE_NODO.get(activo),
        "params": params,
        "impacto": decision.get("impacto"),
        "justificacion": decision.get("justificacion"),
    }
```

`prototipo/lazo.py` — replace `o = ordenm.construir(decision, alerta)` with `o = ordenm.construir(decision, alerta, perfil)`.

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .`
Expected: OK (363 tests).

- [ ] **Step 5: Commit**

```bash
git add prototipo/perfil.py prototipo/orden.py prototipo/lazo.py \
        prototipo/tests/test_perfil.py prototipo/tests/test_orden.py prototipo/tests/test_lazo.py
git commit -m "feat(orden): la IP de ejecucion sale del inventario del perfil; IP_DE_NODO queda de respaldo

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: el agente ve a quién toca (topología enriquecida, IP de gestión)

**Files:**
- Modify:
  - `prototipo/agente_mitigacion.py`: `resolver_topologia`, `herramienta_consultar_topologia`, `construir_prompt_sistema` y `bucle_react`.
  - `prototipo/stream.py`: `construir_mitigar_fn` y `main`.
- Test:
  - `prototipo/tests/test_agente_mitigacion.py`;
  - `prototipo/tests/test_stream.py`.

**Interfaces:**
- Consumes: `impacto.puertos_abiertos(hallazgos, activo)` (Task 2).
- Produces:
  - `resolver_topologia(perfil, hallazgos=None)`: los nodos son **copias** enriquecidas con `funcion`, `criticidad` y `servicios_prestados` (si el inventario los declara) y `servicios_abiertos: [int]` (si hay hallazgos del nodo).
  - `bucle_react(..., hallazgos=None)`.
  - `stream.construir_mitigar_fn(agente, perfil, catalogo, ejecutor, escribir=print, hallazgos=None)`.
- Compatibilidad: `herramienta_consultar_topologia` sigue incluyendo la subcadena `nombre=rol` que afirman los tests actuales.

- [ ] **Step 1: Write the failing tests**

Add to `prototipo/tests/test_agente_mitigacion.py` (after `y_perfil_empresarial`, new helper and class):

```python
def y_perfil_inventariado():
    return {**y_perfil(),
            "activos": {"objetivo-vuln": {"ip": "192.168.1.30", "funcion": "servidor con servicios expuestos",
                                          "criticidad": "media", "servicios_prestados": [22, 80]}}}


class TestVistaDelAgente(unittest.TestCase):
    """Spec de conciencia de impacto §4.5: el agente ve a quién toca, no solo su rol."""

    def test_la_topologia_se_enriquece_con_el_inventario(self):
        topo = ag.resolver_topologia(y_perfil_inventariado())
        self.assertEqual(topo["objetivo-vuln"]["funcion"], "servidor con servicios expuestos")
        self.assertEqual(topo["objetivo-vuln"]["servicios_prestados"], [22, 80])
        self.assertEqual(topo["objetivo-vuln"]["rol"], "host_victima")      # lo de siempre sigue

    def test_con_hallazgos_ve_los_servicios_abiertos(self):
        h = {"nodos": {"objetivo-vuln": [{"puerto": 21, "servicio": "ftp", "estado": "open"},
                                         {"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        topo = ag.resolver_topologia(y_perfil_inventariado(), h)
        self.assertEqual(topo["objetivo-vuln"]["servicios_abiertos"], [21, 22])

    def test_no_muta_el_perfil(self):
        p = y_perfil_inventariado()
        ag.resolver_topologia(p)
        self.assertNotIn("funcion", p["topologia"]["objetivo-vuln"])

    def test_consultar_topologia_describe_a_quien_toca(self):
        obs = ag.herramienta_consultar_topologia(ag.resolver_topologia(y_perfil_inventariado()))
        self.assertIn("objetivo-vuln=host_victima (servidor con servicios expuestos; criticidad media; "
                      "servicios declarados: 22, 80)", obs)
        self.assertIn("canal de gestion (intocable): 192.168.1.100", obs)

    def test_el_prompt_nombra_la_ip_de_gestion(self):
        prompt = ag.construir_prompt_sistema({"origen_ip": "203.0.113.9", "activo": "objetivo-vuln"},
                                             ag.resolver_topologia(y_perfil()))
        self.assertIn("nunca actues sobre el canal de gestion (192.168.1.100)", prompt)

    def test_sin_ip_de_gestion_conserva_la_consigna_generica(self):
        topo = {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30"}, "ip_gestion": None}
        self.assertIn("nunca toques el plano de gestion", ag.construir_prompt_sistema({}, topo))

    def test_el_agente_ve_los_servicios_abiertos_al_consultar_la_topologia(self):
        h = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        guion = GeneradorGuion(['Action: {"tool":"consultar_topologia","args":{}}'])
        plan = ag.bucle_react({"origen_ip": "203.0.113.9", "activo": "objetivo-vuln"}, "vp_intento_acceso",
                              y_perfil_inventariado(), CAT, EjecutorEscalado(), guion, autonomo=True,
                              timestamp="t", escribir=lambda *a: None, max_pasos=1, hallazgos=h)
        lectura = next(p for p in plan["pasos"] if p.get("tool") == "consultar_topologia")
        self.assertIn("abiertos segun el auditor: 22", lectura["observacion"])
```

Add to `prototipo/tests/test_stream.py`, inside `class TestStream`:

```python
    def test_mitigar_fn_pasa_los_hallazgos_al_agente(self):
        from unittest import mock
        from prototipo import agente_mitigacion as ag, justificador_llm, rag
        vistos = {}
        def falso_bucle(*a, **k):
            vistos.update(k)
            return {"resultado": "mitigado"}
        with mock.patch.object(rag, "cargar_indice", return_value=None), \
             mock.patch.object(rag, "embedder_por_defecto", return_value=None), \
             mock.patch.object(justificador_llm, "generador_por_defecto", return_value=lambda p: ""), \
             mock.patch.object(ag, "bucle_react", side_effect=falso_bucle):
            fn = stream.construir_mitigar_fn(True, y("perfil.yml"), CAT, lambda ip, c: (0, ""),
                                             escribir=lambda *a: None, hallazgos={"nodos": {}})
            fn({"clase": "vp_intento_acceso", "timestamp": "t"}, {"origen_ip": "203.0.113.9"}, lambda *_: "s")
        self.assertEqual(vistos["hallazgos"], {"nodos": {}})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_agente_mitigacion prototipo.tests.test_stream -v`
Expected: FAIL/ERROR in the 8 new tests (`KeyError: 'funcion'`, `TypeError: ... unexpected keyword argument 'hallazgos'`, `'canal de gestion' not found`).

- [ ] **Step 3: Write minimal implementation**

`prototipo/agente_mitigacion.py` — imports: replace `from prototipo import conector, politica, rag` with:
```python
from prototipo import conector, impacto, politica, rag
```

Replace `resolver_topologia` with:
```python
def resolver_topologia(perfil, hallazgos=None):
    """Topologia de contencion del perfil, con cada dispositivo enriquecido con lo que el inventario
    sabe de el (funcion, criticidad, servicios declarados) y, si hay hallazgos del auditor, sus
    servicios abiertos: el agente ve a quien toca, no solo su rol (RF-17). Copia los nodos: no muta
    el perfil."""
    activos = perfil.get("activos") or {}
    topo = {}
    for nombre, nodo in (perfil.get("topologia", {}) or {}).items():
        if not isinstance(nodo, dict):
            topo[nombre] = nodo
            continue
        info = activos.get(nombre) or {}
        enriquecido = dict(nodo)
        for campo in ("funcion", "criticidad", "servicios_prestados"):
            if campo in info:
                enriquecido[campo] = info[campo]
        abiertos = impacto.puertos_abiertos(hallazgos, nombre)
        if abiertos is not None:
            enriquecido["servicios_abiertos"] = sorted(abiertos)
        topo[nombre] = enriquecido
    topo["ip_gestion"] = perfil.get("ip_gestion")
    return topo
```

Replace `herramienta_consultar_topologia` with:
```python
def _describir_nodo(nombre, nodo):
    """`nombre=rol` y, entre parentesis, lo que el inventario sabe del equipo (si sabe algo)."""
    detalles = []
    if nodo.get("funcion"):
        detalles.append(nodo["funcion"])
    if nodo.get("criticidad"):
        detalles.append(f"criticidad {nodo['criticidad']}")
    if "servicios_prestados" in nodo:
        detalles.append("servicios declarados: " + (", ".join(map(str, nodo["servicios_prestados"])) or "ninguno"))
    if "servicios_abiertos" in nodo:
        detalles.append("abiertos segun el auditor: " + (", ".join(map(str, nodo["servicios_abiertos"])) or "ninguno"))
    base = f"{nombre}={nodo.get('rol')}"
    return f"{base} ({'; '.join(detalles)})" if detalles else base

def herramienta_consultar_topologia(topo):
    dev = [_describir_nodo(k, v) for k, v in topo.items() if isinstance(v, dict) and v.get("rol")]
    obs = "nodos: " + ", ".join(dev)
    if topo.get("ip_gestion"):
        obs += f" · canal de gestion (intocable): {topo['ip_gestion']}"
    return obs
```

In `construir_prompt_sistema`, add after the `nodos = ...` line:
```python
    gestion = topo.get("ip_gestion")
    regla_gestion = (f"nunca actues sobre el canal de gestion ({gestion}): cortarlo impide responder y verificar"
                     if gestion else "nunca toques el plano de gestion")
```
then replace the prompt line
```python
        "  consultar_topologia()                     -> nodos y su rol\n"
```
with
```python
        "  consultar_topologia()                     -> nodos, su rol y que sabe el inventario de cada uno\n"
```
and replace
```python
        "Reglas: una accion por paso; solo estas herramientas; solo accion 'bloquear_ip'; nunca toques "
        "el plano de gestion. Si una herramienta devuelve Error, RAZONA y escala a otro dispositivo. "
```
with
```python
        f"Reglas: una accion por paso; solo estas herramientas; solo accion 'bloquear_ip'; {regla_gestion}. "
        "Si una herramienta devuelve Error, RAZONA y escala a otro dispositivo. "
```

In `bucle_react`: add `hallazgos=None` as the last parameter of the signature (after `gen_conocimiento=None`), and replace `topo = resolver_topologia(perfil)` (its first line) with `topo = resolver_topologia(perfil, hallazgos)`.

`prototipo/stream.py` — `construir_mitigar_fn`: signature becomes `def construir_mitigar_fn(agente, perfil, catalogo, ejecutor, escribir=print, hallazgos=None):`, and inside `_fn` the call becomes:
```python
        return ag.bucle_react(alerta, decision.get("clase"), perfil, catalogo, ejecutor,
                              gen, leer=leer, autonomo=False,
                              timestamp=decision.get("timestamp", ""),
                              indice=indice, embedder=rag.embedder_por_defecto(), escribir=escribir,
                              hallazgos=hallazgos)
```
In `main`: `mitigar_fn = construir_mitigar_fn(cfg["agente"], perfil, catalogo, ejecutor, hallazgos=hallazgos)`.

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .`
Expected: OK (371 tests). `test_consultar_topologia_lista_roles` sigue pasando, porque en `y_perfil()` no hay inventario y la cadena `gateway=firewall_perimetral` se mantiene.

- [ ] **Step 5: Commit**

```bash
git add prototipo/agente_mitigacion.py prototipo/stream.py \
        prototipo/tests/test_agente_mitigacion.py prototipo/tests/test_stream.py
git commit -m "feat(agente): la topologia del agente dice a quien toca y el prompt nombra la IP de gestion

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `inventario.py` — reconciliación declarado ↔ descubierto

**Files:**
- Create: `prototipo/inventario.py`
- Test: `prototipo/tests/test_inventario.py`

**Interfaces:**
- Consumes: `impacto.puertos_abiertos` (Task 2), `perfil.cargar`.
- Produces:
  - `inventario.reconciliar(perfil, hallazgos)`: devuelve `{"activos": {nombre: {"abiertos_no_declarados": [{"puerto", "servicio"}], "declarados_no_abiertos": [int]}}, "no_inventariados": [str], "no_escaneados": [str]}`.
  - `inventario.formatear(rep) -> str`.
  - `inventario.main(argv) -> int`.

- [ ] **Step 1: Write the failing test** — `prototipo/tests/test_inventario.py`

```python
import contextlib, io, json, os, tempfile, unittest
from prototipo import inventario

PERFIL = {"activos": {
    "objetivo-vuln": {"servicios_prestados": [22, 80, 443]},
    "puesto": {"servicios_prestados": []},
    "impresora": {"servicios_prestados": [9100]},
}}
HALLAZGOS = {"nodos": {
    "objetivo-vuln": [{"puerto": 21, "servicio": "ftp", "estado": "open"},
                      {"puerto": 22, "servicio": "ssh", "estado": "open"},
                      {"puerto": 80, "servicio": "http", "estado": "open"}],
    "puesto": [],
    "camara": [{"puerto": 554, "servicio": "rtsp", "estado": "open"}],
}}


class TestReconciliar(unittest.TestCase):
    def setUp(self):
        self.r = inventario.reconciliar(PERFIL, HALLAZGOS)

    def test_abiertos_no_declarados_son_exposicion_no_reconocida(self):
        self.assertEqual(self.r["activos"]["objetivo-vuln"]["abiertos_no_declarados"],
                         [{"puerto": 21, "servicio": "ftp"}])

    def test_declarados_no_abiertos(self):
        self.assertEqual(self.r["activos"]["objetivo-vuln"]["declarados_no_abiertos"], [443])

    def test_escaneado_y_no_inventariado(self):
        self.assertEqual(self.r["no_inventariados"], ["camara"])

    def test_inventariado_y_no_escaneado_no_se_compara(self):   # RNF-07
        self.assertEqual(self.r["no_escaneados"], ["impresora"])
        self.assertNotIn("impresora", self.r["activos"])

    def test_un_activo_que_coincide_no_tiene_discrepancias(self):
        self.assertEqual(self.r["activos"]["puesto"],
                         {"abiertos_no_declarados": [], "declarados_no_abiertos": []})


class TestCLI(unittest.TestCase):
    def test_imprime_el_informe(self):
        with tempfile.TemporaryDirectory() as d:
            rp, rh = os.path.join(d, "p.yml"), os.path.join(d, "h.json")
            with open(rp, "w", encoding="utf-8") as f:
                f.write("activos:\n  objetivo-vuln: { servicios_prestados: [22] }\n")
            with open(rh, "w", encoding="utf-8") as f:
                json.dump(HALLAZGOS, f)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = inventario.main([rp, rh])
        self.assertEqual(rc, 0)
        self.assertIn("objetivo-vuln: 2 abierto(s) no declarado(s)", out.getvalue())
        self.assertIn("ftp/21", out.getvalue())
        self.assertIn("escaneados y no inventariados: camara, puesto", out.getvalue())

    def test_uso_sin_argumentos(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inventario.main([]), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_inventario -v`
Expected: ERROR — `ImportError: cannot import name 'inventario' from 'prototipo'`.

- [ ] **Step 3: Write minimal implementation** — `prototipo/inventario.py`

```python
"""Reconciliación del inventario declarado con la red descubierta (RF-17).

Compara lo que el cliente declara en su perfil (`activos` y sus `servicios_prestados`) con lo que el
auditor vio en la red (hallazgos de Nmap). Hace visibles las discrepancias en vez de resolverlas: si
un puerto abierto no declarado es una exposición o un olvido del inventario, lo decide el cliente.

Uso:  python3 -m prototipo.inventario <perfil.yml> <hallazgos.json>
"""
import json, sys
from prototipo import impacto, perfil as perfilm


def reconciliar(perfil, hallazgos):
    """{activos: {nombre: {abiertos_no_declarados, declarados_no_abiertos}}, no_inventariados,
    no_escaneados}. Un activo no escaneado no se compara: no escaneado no es «sin servicios»."""
    activos = (perfil or {}).get("activos") or {}
    nodos = (hallazgos or {}).get("nodos") or {}
    por_activo = {}
    for nombre in sorted(activos):
        abiertos = impacto.puertos_abiertos(hallazgos, nombre)
        if abiertos is None:
            continue
        declarados = set((activos[nombre] or {}).get("servicios_prestados") or [])
        por_activo[nombre] = {
            "abiertos_no_declarados": [{"puerto": p, "servicio": abiertos[p]}
                                       for p in sorted(set(abiertos) - declarados)],
            "declarados_no_abiertos": sorted(declarados - set(abiertos)),
        }
    return {"activos": por_activo,
            "no_inventariados": sorted(set(nodos) - set(activos)),
            "no_escaneados": sorted(set(activos) - set(nodos))}


def formatear(rep):
    lineas = []
    for nombre, r in rep["activos"].items():
        nd, dn = r["abiertos_no_declarados"], r["declarados_no_abiertos"]
        if nd:
            lineas.append(f"{nombre}: {len(nd)} abierto(s) no declarado(s) (exposición no reconocida): "
                          + ", ".join(f"{s['servicio']}/{s['puerto']}" for s in nd))
        if dn:
            lineas.append(f"{nombre}: declarado(s) y no abierto(s) (¿servicio caído?): "
                          + ", ".join(map(str, dn)))
        if not nd and not dn:
            lineas.append(f"{nombre}: coincide con lo declarado")
    if rep["no_inventariados"]:
        lineas.append("escaneados y no inventariados: " + ", ".join(rep["no_inventariados"]))
    if rep["no_escaneados"]:
        lineas.append("inventariados y no escaneados: " + ", ".join(rep["no_escaneados"]))
    return "\n".join(lineas)


def main(argv):
    if len(argv) != 2:
        print("uso: python3 -m prototipo.inventario <perfil.yml> <hallazgos.json>")
        return 2
    perfil = perfilm.cargar(argv[0])
    with open(argv[1], encoding="utf-8") as f:
        hallazgos = json.load(f)
    print(formatear(reconciliar(perfil, hallazgos)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .`
Expected: OK (378 tests).

- [ ] **Step 5: Commit**

```bash
git add prototipo/inventario.py prototipo/tests/test_inventario.py
git commit -m "feat(inventario): reconciliacion del inventario declarado con lo que ve el auditor (CLI)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: métrica `bloqueos_automaticos_indebidos` y sección `automatizacion` de la campaña

**Files:**
- Modify:
  - `evaluacion/metricas.py` (añadir al final);
  - `evaluacion/campana.py` (`evaluar`, `tabla_markdown`).
- Test:
  - `evaluacion/tests/test_metricas.py`;
  - `evaluacion/tests/test_campana.py`.

**Interfaces:**
- Produces:
  - `metricas.bloqueos_automaticos_indebidos(registros) -> {"automaticos": int, "indebidos": int, "tasa_indebidos": float|"n/d"}`. Cada registro lleva `accion_final`, `requiere_humano` y `etiqueta`.
  - En el resultado de `campana.evaluar`, la clave `resultados["automatizacion"]`.

- [ ] **Step 1: Write the failing tests**

Add to `evaluacion/tests/test_metricas.py`:

```python
class TestBloqueosAutomaticosIndebidos(unittest.TestCase):
    def test_cuenta_los_automaticos_sobre_fp_y_propia_sea_cual_sea_el_impacto(self):
        regs = [
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "FP", "impacto": "localizado"},      # indebido
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "PROPIA", "impacto": "localizado"},  # indebido
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "VP", "impacto": "localizado"},      # correcto
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": True, "etiqueta": "FP", "impacto": "localizado"},       # lo retuvo el humano
            {"accion_final": None, "requiere_humano": False, "etiqueta": "FP", "impacto": "ninguno"},                  # sin acción
        ]
        self.assertEqual(m.bloqueos_automaticos_indebidos(regs),
                         {"automaticos": 3, "indebidos": 2, "tasa_indebidos": 2 / 3})

    def test_sin_automaticos_la_tasa_es_nd(self):
        self.assertEqual(m.bloqueos_automaticos_indebidos([]),
                         {"automaticos": 0, "indebidos": 0, "tasa_indebidos": "n/d"})

    def test_cubre_el_punto_ciego_de_continuidad(self):
        # un bloqueo localizado indebido no es «disruptivo» para continuidad(); para esta métrica sí cuenta
        regs = [{"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "FP", "impacto": "localizado"}]
        self.assertEqual(m.continuidad(regs)["disruptivas_indebidas"], 0)
        self.assertEqual(m.bloqueos_automaticos_indebidos(regs)["indebidos"], 1)
```

In `evaluacion/tests/test_campana.py`:

1. In `_procesar_falso`, replace `"accion_final":"BLOQUEAR_IP" if amenaza else "NINGUNA",` with `"accion_final":"BLOQUEAR_IP" if amenaza else None,   # como el motor real: sin acción es None`.
2. In `test_evaluar_produce_las_secciones`, replace the tuple `("clasificacion_prototipo","baseline","priorizacion","operacion","continuidad","condiciones")` with `("clasificacion_prototipo","baseline","priorizacion","operacion","continuidad","automatizacion","condiciones")`.
3. Add to `class TestCampana`:

```python
    def test_automatizacion_cuenta_los_bloqueos_sin_humano(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        # filas 1 (VP) y 2 (FP) se bloquean sin humano; la 2 es indebida
        self.assertEqual(res["automatizacion"], {"automaticos": 2, "indebidos": 1, "tasa_indebidos": 0.5})
        self.assertIn("Contenciones automáticas (sin humano): 2", campana.tabla_markdown(res))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests -t .`
Expected: ERROR `AttributeError: module 'evaluacion.metricas' has no attribute 'bloqueos_automaticos_indebidos'`; `KeyError: 'automatizacion'`.

- [ ] **Step 3: Write minimal implementation**

`evaluacion/metricas.py` — append:
```python
def bloqueos_automaticos_indebidos(registros):
    """Contenciones ejecutadas SIN humano (hay `accion_final` y no `requiere_humano`) cuya verdad es
    FP o PROPIA, sea cual sea su impacto. Cubre el punto ciego de `continuidad`, que solo cuenta las
    que alcanzan un servicio: bloquear a un empleado inocente es localizado y también es indebido."""
    auto = [r for r in registros if r.get("accion_final") and not r.get("requiere_humano")]
    indebidos = sum(1 for r in auto if r.get("etiqueta") in ("FP", "PROPIA"))
    return {"automaticos": len(auto), "indebidos": indebidos, "tasa_indebidos": _div(indebidos, len(auto))}
```

`evaluacion/campana.py` — in `evaluar`, replace the `regs = [...]` / `cont = ...` block with:
```python
    regs = [{"impacto": p["impacto"], "etiqueta": f["etiqueta"], "requiere_humano": p["requiere_humano"],
             "accion_final": p["accion_final"]}
            for f, p in zip(filas, preds)]
    cont = metricas.continuidad(regs)
    # Automatizacion: cuanto se ejecuta sin humano y cuanto de eso cae sobre un FP (cualquier impacto).
    autom = metricas.bloqueos_automaticos_indebidos(regs)
```
and in the `resultados = {...}` dict add `"automatizacion": autom,` right after `"continuidad": cont,`.

In `tabla_markdown`, right before `if "anclaje" in resultados:` add:
```python
    if "automatizacion" in resultados:
        a = resultados["automatizacion"]
        out += ["", f"Contenciones automáticas (sin humano): {a['automaticos']} · indebidas (FP/PROPIA): "
                    f"{a['indebidos']} · tasa de escalado al humano: {_celda(resultados['operacion']['tasa_escalado'])}"]
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests -t .`
Expected: OK (43 tests).

- [ ] **Step 5: Commit**

```bash
git add evaluacion/metricas.py evaluacion/campana.py evaluacion/tests/test_metricas.py evaluacion/tests/test_campana.py
git commit -m "feat(evaluacion): bloqueos automaticos indebidos, el punto ciego del indicador de continuidad

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: los perfiles describen redes reales (empresarial = el laboratorio; bancario con IPs)

**Files:**
- Modify:
  - `prototipo/perfiles/empresarial.yml` (entero);
  - `prototipo/perfiles/bancario.yml` (`activos`, `redes_internas`, `continuidad.actores`).
- Modify:
  - `prototipo/tests/test_perfil.py` (nueva `TestPerfilEmpresarial`; más tests en `TestPerfilBancario`);
  - `prototipo/tests/test_rnf14.py`.
- Modify: `lab/scripts/demo-agente-escalado.py` and `lab/scripts/demo-escalada-determinista.py` (`gateway` → `borde`).

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces:
  - Los perfiles usados por la campaña (Tarea 10) y por los demos.
  - `empresarial.yml` debe contener literalmente la línea `    activo_interno:  humano_siempre` (dos espacios tras los dos puntos). La Tarea 10 la usa en un `sed` de la documentación.

- [ ] **Step 1: Write the failing tests**

Add to `prototipo/tests/test_perfil.py` (new class after `TestPerfilBancario`):

```python
class TestPerfilEmpresarial(unittest.TestCase):
    """empresarial.yml describe la red REAL del laboratorio (spec de conciencia de impacto §4.8)."""
    def setUp(self):
        self.p = perfil.cargar(os.path.join(FX, "..", "..", "perfiles", "empresarial.yml"))

    def test_el_canal_de_gestion_es_el_auditor_y_es_intocable(self):   # RF-19 reparado
        self.assertEqual(self.p["ip_gestion"], "172.20.20.4")
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "172.20.20.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual((r["resultado"], r["accion_final"]), ("veta", None))

    def test_el_inventario_es_el_del_laboratorio(self):   # C6: un nombre por equipo
        from prototipo import orden
        self.assertEqual(set(self.p["activos"]), set(orden.IP_DE_NODO))
        for nombre, ip in orden.IP_DE_NODO.items():
            self.assertEqual(self.p["activos"][nombre]["ip"], ip, nombre)

    def test_bloquear_el_puesto_exige_humano(self):   # C1: el atacante del laboratorio es interno
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "192.168.1.10"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]), ("veta", "BLOQUEAR_IP", True))

    def test_un_atacante_externo_se_bloquea_solo(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual((r["resultado"], r["requiere_humano"]), ("permite", False))

    def test_la_criticidad_de_los_nodos_es_la_efectiva_de_siempre(self):   # C6: priorización intacta
        for nombre in ("borde", "puesto", "iot", "objetivo-vuln"):
            self.assertEqual(perfil.criticidad_de(self.p, nombre), "media", nombre)

    def test_la_topologia_y_el_inventario_coinciden_en_las_ips(self):
        for nombre, nodo in self.p["topologia"].items():
            self.assertEqual(nodo["ip"], self.p["activos"][nombre]["ip"], nombre)

    def test_la_politica_de_actores_esta_declarada(self):
        self.assertEqual(self.p["continuidad"]["actores"],
                         {"activo_interno": "humano_siempre", "dispositivo_red": "humano_siempre"})
```

Add to `class TestPerfilBancario` in `prototipo/tests/test_perfil.py`:

```python
    def test_bloquear_la_consola_del_soc_es_veto_duro(self):   # RF-19: mdr-siem es la IP de gestión
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "10.100.0.10"}, CAT, "core-db", "1521", 0.99)
        self.assertEqual((r["resultado"], r["accion_final"]), ("veta", None))

    def test_bloquear_un_activo_interno_del_banco_exige_humano(self):   # C1
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "10.200.0.10"}, CAT, "core-db", "1521", 0.99)
        self.assertEqual((r["accion_final"], r["requiere_humano"]), ("BLOQUEAR_IP", True))
        self.assertEqual(r["impacto"]["actor"]["nombre"], "taquilla")

    def test_una_ip_interna_no_inventariada_tambien_es_interna(self):   # redes_internas
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "10.55.3.7"}, CAT, "core-db", "1521", 0.99)
        self.assertTrue(r["requiere_humano"])
        self.assertEqual(r["impacto"]["actor"]["por"], "redes_internas")

    def test_bloquear_un_firewall_del_banco_alcanza_servicio(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "10.0.0.1"}, CAT, "web-banking", "443", 0.99)
        self.assertEqual(r["impacto"]["actor"]["tipo"], "dispositivo_red")
        self.assertEqual(r["impacto"]["nivel"], "alcanza_servicio")
        self.assertTrue(r["requiere_humano"])

    def test_cada_activo_declara_ip_y_funcion(self):
        for nombre, a in self.p["activos"].items():
            self.assertIn("ip", a, nombre)
            self.assertIn("funcion", a, nombre)

    def test_la_topologia_y_el_inventario_coinciden_en_las_ips(self):
        for nombre, nodo in self.p["topologia"].items():
            if nombre in self.p["activos"]:
                self.assertEqual(nodo["ip"], self.p["activos"][nombre]["ip"], nombre)
```

In `prototipo/tests/test_rnf14.py`, replace both existing tests and add a third. The whole `class TestRNF14` becomes:

```python
class TestRNF14(unittest.TestCase):
    def test_misma_accion_alcanza_servicio_diverge_por_perfil(self):
        # BLOQUEAR_PUERTO (alcanza_servicio) contra objetivo-vuln:80, origen externo, confianza alta.
        # Residencial: impacto_alcanza_servicio=automatica_si_confianza -> permite BLOQUEAR_PUERTO.
        # Empresarial: impacto_alcanza_servicio=humano_siempre -> degrada a BLOQUEAR_IP (localizado,
        # automático con confianza alta porque el origen es externo).
        res = perfil.filtrar(RES, "BLOQUEAR_PUERTO", {"puerto":80,"ip":"203.0.113.9"}, CAT, "objetivo-vuln", "http", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_PUERTO", {"puerto":80,"ip":"203.0.113.9"}, CAT, "objetivo-vuln", "http", 1.0)
        self.assertNotEqual(
            (res["resultado"], res["accion_final"]),
            (emp["resultado"], emp["accion_final"]),
            f"los perfiles deberían divergir: res={res}, emp={emp}")

    def test_localizado_sobre_origen_externo_coincide_en_ambos(self):
        # sobre un origen externo, bloquear la IP es automático en los dos perfiles (honesto)
        res = perfil.filtrar(RES, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(res["resultado"], emp["resultado"])

    def test_bloquear_un_activo_interno_diverge_por_perfil(self):
        # empresarial inventaria el puesto (.10) y exige humano para bloquear lo propio (C1);
        # residencial no tiene inventario con IPs: para él es un origen cualquiera y lo bloquea solo.
        res = perfil.filtrar(RES, "BLOQUEAR_IP", {"ip":"192.168.1.10"}, CAT, "objetivo-vuln", "ssh", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_IP", {"ip":"192.168.1.10"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual((res["resultado"], res["requiere_humano"]), ("permite", False))
        self.assertEqual((emp["resultado"], emp["requiere_humano"]), ("veta", True))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_perfil prototipo.tests.test_rnf14 -v`
Expected: FAIL in `TestPerfilEmpresarial` (`ip_gestion` is `192.168.1.100`, missing `ip`), in the new `TestPerfilBancario` tests (no `funcion`, no `redes_internas`) and in `test_bloquear_un_activo_interno_diverge_por_perfil`.

- [ ] **Step 3: Write the profiles**

Replace `prototipo/perfiles/empresarial.yml` with:

```yaml
# Cliente empresarial: la red del laboratorio (red-cliente), continuidad estricta.
# El inventario describe la red REAL vigilada: los nodos que el auditor escanea y el canal por el
# que el MDR actúa. Un nombre por equipo (C6): el laboratorio, el auditor y orden.IP_DE_NODO
# llaman `borde` a la .1.
version: v0

# Inventario de la red protegida (RF-17). criticidad gobierna la prioridad (media: la efectiva
# hasta ahora, C6); servicios_prestados son los puertos que el cliente reconoce como su servicio
# (lo demás abierto es exposición no reconocida: python3 -m prototipo.inventario); funcion dice qué
# es el equipo, para que el analista y el agente sepan a quién tocan.
activos:
  borde:         { ip: 192.168.1.1,  funcion: "equipo de borde: enruta la LAN hacia el proveedor",
                   criticidad: media, servicios_prestados: [] }
  puesto:        { ip: 192.168.1.10, funcion: "puesto de trabajo de un empleado",
                   criticidad: media, servicios_prestados: [] }
  iot:           { ip: 192.168.1.20, funcion: "dispositivo IoT con panel web",
                   criticidad: media, servicios_prestados: [80] }
  objetivo-vuln: { ip: 192.168.1.30, funcion: "servidor con servicios expuestos",
                   criticidad: media, servicios_prestados: [22, 80] }
# Una IP de estos rangos que no esté en el inventario también es un activo interno.
redes_internas: ["192.168.1.0/24"]

# Orígenes declarados cuya actividad es legítima: la administración del cliente (192.168.1.1)
# y el auditor del propio servicio (172.20.20.4), que escanea la red a propósito. Un ataque
# aparente desde ellos es FP (RF-03). Medido: sin declarar al auditor, sus barridos de puertos
# se clasificaban como ataque y el prototipo lo habría bloqueado (campaña de reconocimiento).
origenes_legitimos: ["192.168.1.1", "172.20.20.4"]
# Ráfaga: a partir de cuántas alertas del mismo origen en un minuto se considera ataque aunque el
# origen esté declarado (suplantación o equipo comprometido). Umbral tomado del clasificador
# entrenado (corte en 8,5, estable); sin esta clave, la regla no actúa.
rafaga: { umbral: 9, ventana_s: 60 }
continuidad:
  impacto_ninguno:          automatica
  impacto_localizado:       automatica_si_confianza
  impacto_alcanza_servicio: humano_siempre
  reversibilidad_obligatoria: true
  no_cortar_gestion: true
  umbral_confianza: 0.7   # umbral de escalado (RF-07); 0.7 por defecto
  # A quién bloquea la acción (C1): bloquear un activo interno o un dispositivo de red exige
  # humano. Un cliente que prefiera automatizarlo lo declara con automatica_si_confianza.
  actores:
    activo_interno:  humano_siempre
    dispositivo_red: humano_siempre
excepciones: []
topologia:
  objetivo-vuln: { rol: host_victima, ip: 192.168.1.30, gateway: borde }
  borde:         { rol: firewall_perimetral, ip: 192.168.1.1 }
# Canal de gestión (RF-19): el auditor, desde el que el conector lanza el SSH
# (conector._ssh_en_auditor). Bloquearlo es veto duro: impediría responder y verificar.
ip_gestion: 172.20.20.4
```

In `prototipo/perfiles/bancario.yml`, replace the comment line `# criticidad gobierna la prioridad (critica/alta suben); servicios_prestados es documental.` and the `activos:` block (lines 6–16) with:

```yaml
# Inventario (RF-17): criticidad gobierna la prioridad (critica/alta suben); servicios_prestados son
# los puertos del servicio; ip y funcion dicen a quien toca cada accion. IPs con el patron
# 10.<VLAN>.0.10 (SWIFT no tenia VLAN numerada: se usa la 30, libre entre la DMZ 20 y el Core 40).
activos:
  web-banking:    { ip: 10.10.0.10,  funcion: "banca en linea (portal web de clientes)",       criticidad: alta,    servicios_prestados: [443, 80] }   # DMZ VLAN 10
  api-movil:      { ip: 10.20.0.10,  funcion: "API de la aplicacion movil",                    criticidad: alta,    servicios_prestados: [443] }       # DMZ VLAN 20
  swift-alliance: { ip: 10.30.0.10,  funcion: "pasarela SWIFT Alliance (transferencias)",      criticidad: critica, servicios_prestados: [] }          # DMZ SWIFT
  middleware:     { ip: 10.40.0.10,  funcion: "middleware del core bancario",                  criticidad: alta,    servicios_prestados: [8443] }      # Core VLAN 40
  core-db:        { ip: 10.50.0.10,  funcion: "base de datos del core bancario (cluster)",     criticidad: critica, servicios_prestados: [1521] }      # Core VLAN 50
  hsm:            { ip: 10.60.0.10,  funcion: "modulo de seguridad de hardware (cifrado)",     criticidad: critica, servicios_prestados: [] }          # Core VLAN 60
  mdr-siem:       { ip: 10.100.0.10, funcion: "consola SOC/MDR (plano de gestion)",            criticidad: critica, servicios_prestados: [] }          # SOC VLAN 100
  atm:            { ip: 10.210.0.10, funcion: "cajero automatico de sucursal",                 criticidad: alta,    servicios_prestados: [] }          # Sucursal VLAN 210
  taquilla:       { ip: 10.200.0.10, funcion: "puesto de taquilla de sucursal",                criticidad: media,   servicios_prestados: [] }          # Sucursal VLAN 200
# Toda la red del banco: una IP 10.x no inventariada tambien es un activo interno.
redes_internas: ["10.0.0.0/8"]
```

In the same file, inside `continuidad:` after the `umbral_confianza:` line, add:

```yaml
  actores:                                          # C1: bloquear lo propio exige humano
    activo_interno:           humano_siempre
    dispositivo_red:          humano_siempre
```

Replace the comment `# Origenes cuya actividad es legitima (RNF-14). Match EXACTO por IP (el motor no interpreta CIDR):` with `# Origenes cuya actividad es legitima (RNF-14). Match EXACTO por IP (redes_internas si admite CIDR):`.

- [ ] **Step 4: Rename `gateway` → `borde` in the demos**

`lab/scripts/demo-agente-escalado.py`: in `generador_guion`, change the three occurrences of `"gateway"` to `"borde"` (the `ejecutar_comando` and `verificar_mitigacion` args, and `dispositivo_ejecutor` in `Final`).

`lab/scripts/demo-escalada-determinista.py`: edit the docstring and the `HostCaido` docstring.
- `(perfil empresarial: objetivo-vuln -> gateway)` → `(perfil empresarial: objetivo-vuln -> borde)`
- `el firewall (gateway,\n192.168.1.1) responde` → `el firewall (borde,\n192.168.1.1) responde`
- `  - dispositivo_ejecutor = gateway   -> se contuvo en el firewall` → `  - dispositivo_ejecutor = borde     -> se contuvo en el firewall`
- In `HostCaido`: `el firewall (gateway,\n    192.168.1.1) responde` → `el firewall (borde,\n    192.168.1.1) responde`
- Replace the paragraph

  ```
    (En el banco es idéntico con más saltos —web-banking -> FW-core -> FW-edge—; aquí se usa el lab
     porque la IP del activo se resuelve de un mapa del lab, orden.IP_DE_NODO.)
  ```

  with

  ```
    (En el banco es idéntico con más saltos —web-banking -> FW-core -> FW-edge—: la IP del activo sale
     del inventario del perfil, perfil.ip_de. Aquí se usa el lab porque el ejecutor simulado conoce sus IPs.)
  ```

- [ ] **Step 5: Run the suites and both demos**

```bash
PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .   # OK (392)
python3 lab/scripts/demo-escalada-determinista.py --auto | grep -E "escalado|dispositivo_ejecutor"
python3 lab/scripts/demo-agente-escalado.py --autonomo | grep "Resultado"
```
Expected:
- La suite pasa entera.
- En el demo determinista: `escalado             = True` y `dispositivo_ejecutor = borde`.
- En el demo del agente: `Resultado: mitigado · dispositivo ejecutor: borde · escalado: True · degradado: False`.

- [ ] **Step 6: Commit**

```bash
git add prototipo/perfiles/empresarial.yml prototipo/perfiles/bancario.yml \
        prototipo/tests/test_perfil.py prototipo/tests/test_rnf14.py \
        lab/scripts/demo-agente-escalado.py lab/scripts/demo-escalada-determinista.py
git commit -m "feat(perfiles): empresarial describe la red real del laboratorio; RF-19 protege al auditor

- empresarial: inventario borde/puesto/iot/objetivo-vuln con ip y funcion, redes_internas,
  continuidad.actores, ip_gestion 172.20.20.4 (antes una IP inexistente), topologia gateway -> borde.
  Se retiran servidor-web y controlador-ot, que no existen en el laboratorio.
- bancario: ip y funcion por activo, redes_internas 10.0.0.0/8.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: medir el efecto y documentarlo

**Files:**
- Create: `evaluacion/resultados/campana-2026-09-21.json`, generado por la campaña.
- Modify:
  - `evaluacion/resultados/tabla.md`, regenerado por la campaña;
  - `evaluacion/resultados/README.md`;
  - `documentacion/00-general/estado-y-riesgos.md`;
  - `documentacion/02-fase2-estado-del-arte/requisitos.md`;
  - `README.md`;
  - `prototipo/README.md`;
  - `docs/pruebas/03-lab-en-vivo.md`, `04-escenarios-de-ataque.md`, `05-topologias.md` y `07-roadmap-pipeline-y-latencia.md`;
  - `documentacion/07-fase7-documentacion-e-informe-final/guia-de-operacion.md`.

- [ ] **Step 1: Suites completas en verde y recuentos**

```bash
PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t . 2>&1 | tail -3
PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests -t . 2>&1 | tail -3
PYTHONPATH=. python3 -m unittest discover -s lab/dataset/tests -t . 2>&1 | tail -3
```
Expected: las tres en OK. Anota los tres recuentos (`Ran N tests`) para los pasos 5 y 6.

- [ ] **Step 2: Correr la campaña y comprobar el efecto contra el 11/09**

```bash
PYTHONPATH=. python3 -m evaluacion.campana --particion evaluacion --sin-llm
python3 - <<'EOF'
import json
a = json.load(open("evaluacion/resultados/campana-2026-09-11.json"))
b = json.load(open("evaluacion/resultados/campana-2026-09-21.json"))
assert a["clasificacion_prototipo"] == b["clasificacion_prototipo"], "la clasificacion cambio"
assert a["priorizacion"] == b["priorizacion"], "la priorizacion cambio"
assert b["automatizacion"] == {"automaticos": 0, "indebidos": 0, "tasa_indebidos": "n/d"}, b["automatizacion"]
assert round(b["operacion"]["tasa_escalado"] * 300) == 89, b["operacion"]["tasa_escalado"]
print("OK: clasificacion y priorizacion identicas; escalado", a["operacion"]["tasa_escalado"], "->",
      b["operacion"]["tasa_escalado"], "; automatizacion", b["automatizacion"])
EOF
```
Expected: `OK: …; escalado 0.0666… -> 0.2966…; automatizacion {'automaticos': 0, …}`.

Si alguna aserción falla, **para** y reporta: el spec §6 dice que estas cifras se miden, no se suponen.

La campaña nombra el fichero con la fecha del sistema (`campana-<AAAA-MM-DD>.json`). Si no es 21/09/2026, usa ese nombre en el script de arriba y en toda la documentación de esta tarea.

- [ ] **Step 3: Reconciliar el inventario del laboratorio**

```bash
python3 -m prototipo.inventario prototipo/perfiles/empresarial.yml lab/campañas/2026-08-31-evaluacion/hallazgos.json
```
Expected (orden de líneas por nombre de activo):
```
borde: coincide con lo declarado
iot: 1 abierto(s) no declarado(s) (exposición no reconocida): telnet/23
objetivo-vuln: 14 abierto(s) no declarado(s) (exposición no reconocida): ftp/21, telnet/23, smtp/25, rpcbind/111, …
puesto: coincide con lo declarado
```
Guarda la salida real: se cita en el paso 4.

- [ ] **Step 4: `evaluacion/resultados/README.md`**

1. In the table «Qué hay en cada directorio», row `` `.` (raíz) ``, replace `**Vigente** — \`campana-2026-09-11.json\`; las corridas anteriores de la raíz son de 205/18 y 220/31` with:

   ```
   **Vigente** — `campana-2026-09-21.json` (clasificación y priorización idénticas a `campana-2026-09-11.json`; añade la conciencia de impacto); las corridas anteriores de la raíz son de 205/18 y 220/31
   ```

2. In the section «Ablación de postura», replace `cifra de escalado vigente: **20/300 = 0,067** (antes de la 6ª regla era 0,0).` with `escalada **por confianza**: **20/300 = 0,067** (antes de la 6ª regla era 0,0). Desde la conciencia de impacto el escalado total es 89/300 (sección siguiente).`

3. Insert this new section right before `### Reproducibilidad del banco (RNF-03)`. The reconciliation block goes in verbatim from Step 3.

   ````markdown
   ### Conciencia de impacto: a quién bloquea cada contención (21/09/2026)

   Pregunta: el catálogo declaraba el impacto de una acción por su tipo (`BLOQUEAR_IP` siempre «localizado»,
   bloquee a quien bloquee). ¿A quién bloqueaban de verdad las contenciones automáticas? Se midió sobre la
   partición de evaluación con el perfil `empresarial` corregido para describir la red real del laboratorio
   (spec: `docs/superpowers/specs/2026-09-21-conciencia-de-impacto-design.md`).

   | Métrica | 11/09 | 21/09 |
   |---|---|---|
   | Recall · tasa de FP (clasificación) | 1,000 · 0,009 | **idénticos** |
   | Priorización ±1 · Spearman | 0,981 · 0,935 | **idénticos** |
   | Contenciones automáticas (sin humano) | 69 | **0** |
   | — de ellas sobre un FP (indebidas) | 2 | **0** |
   | Escalado al humano | 20/300 (0,067) | **89/300 (0,297)** |

   - **Las 69 automáticas bloqueaban `192.168.1.10`, el puesto de un empleado.** En el laboratorio el atacante es
     interno. Dos eran falsos positivos (los casos *error + acceso*): un empleado desconectado sin que nadie lo
     aprobara. El indicador de continuidad (`disruptivas_indebidas`) los contaba como 0 porque solo mira las
     acciones que alcanzan un servicio. La nueva métrica `bloqueos_automaticos_indebidos` cubre ese punto ciego.
   - **Ahora el filtro sabe a quién bloquea.** Bloquear un activo interno o un dispositivo de red exige humano
     por defecto (decisión D16). Las 20 de antes siguen siendo las ráfagas desde el origen de administración
     (confianza 0,6); las 69 nuevas son retenciones por actor interno.
   - **El coste es real:** el analista revisa 4,5 veces más decisiones. Un cliente que prefiera automatizar el
     bloqueo de sus activos internos lo declara (`continuidad.actores.activo_interno: automatica_si_confianza`).
     La automatización sigue disponible para orígenes externos desconocidos con confianza alta.
   - **Reconciliación del inventario del laboratorio** (`python3 -m prototipo.inventario`), que muestra la
     exposición no reconocida:

   ```
   <pega aquí la salida del paso 3>
   ```
   ````

- [ ] **Step 5: `documentacion/00-general/estado-y-riesgos.md`**

1. **Row «5 — Implementación»** (section 1):
   - replace `(**306 tests**)` with `(**<N_prototipo> tests**)`;
   - right before the closing ` |` of that row, append: ` La **conciencia de impacto** (21/09, RF-17/RF-19): cada contención determina a quién bloquea y qué servicios detiene desde el inventario del perfil (\`actores.py\`, \`impacto.py\`), el filtro retiene para el humano el bloqueo de lo propio (D16), el canal de gestión real (el auditor) es intocable y \`inventario.py\` reconcilia lo declarado con lo que ve el auditor.`

2. **Row «6 — Evaluación»**:
   - replace `(**39 tests**)` with `(**<N_evaluacion> tests**)`;
   - replace `Escala al humano el **6,7 %** (las ráfagas desde el origen de administración).` with:

   ```
   Escala al humano el **29,7 %** (89/300) desde la conciencia de impacto (21/09): el 6,7 % por confianza (ráfagas desde el origen de administración) más todo bloqueo de un activo interno (D16), con **0** contenciones automáticas indebidas (antes 2, invisibles al indicador de continuidad).
   ```

3. **Section 2**: add a row after `| D15 | … |`:

   ```
   | D16 | **Bloquear lo propio exige humano por defecto.** Una contención que recae sobre un activo interno o un dispositivo de red del cliente queda retenida para validación humana (`continuidad.actores`, por defecto `humano_siempre`, configurable por perfil); bloquear el canal de gestión es veto duro (RF-19). El impacto se **determina** desde el inventario (a quién bloquea, qué servicios detiene) y nunca queda por debajo del catálogo. *Coste medido:* el escalado sube de 6,7 % a 29,7 % en el laboratorio, porque allí el atacante es interno; la automatización queda para los orígenes externos | [spec](../../docs/superpowers/specs/2026-09-21-conciencia-de-impacto-design.md) · [resultados](../../evaluacion/resultados/README.md) |
   ```

4. **Section 7 «Trabajo futuro»**:
   - Delete the whole bullet `- **IP del activo desde la topología del perfil.** …Acotado.`. It is resolved: `perfil.ip_de` + `orden.construir(…, perfil)`.
   - In the bullet «Calibración del umbral de escalado (RF-07)», replace `Escalado medido en la campaña vigente: **0,067** (20/300, todas VP: las ráfagas desde el origen de\n  administración, 6ª regla).` with `Escalado por confianza en la campaña vigente: **0,067** (20/300, todas VP: las ráfagas desde el origen de\n  administración, 6ª regla); el total es 0,297 porque el perfil retiene además el bloqueo de lo propio (D16).`
   - Add at the end of «Trabajo futuro»:

   ```
   - **Dependencias entre activos y radio en cascada (Nivel 2 de la conciencia de impacto).** Un campo
     `depende_de` por activo y el cierre transitivo inverso («aislar el middleware afecta a la banca en línea»).
     Opcional en el plan de la conciencia de impacto (tareas 11–12).
   ```

5. **Section 7 «Fuera de alcance por diseño»**: add:

   ```
   - **Descubrimiento automático del inventario y uso en tiempo real (Nivel 3 de la conciencia de impacto).**
     Descubrir dependencias (NetFlow/IPFIX, service mesh, trazas de aplicación), integrar una CMDB/ITSM, medir
     cuántos usuarios usan un servicio en este momento o descubrir la función de un activo exige telemetría que
     el prototipo no tiene, y es la integración multicapa en producción que el plan excluye. El inventario es un
     dato del perfil: una fuente automática lo podría alimentar sin tocar el motor. Límites que esto deja: el
     radio de impacto es una **cota superior** (un puerto abierto no implica uso) y una IP interna no
     inventariada y fuera de `redes_internas` resuelve a desconocido. Detalle en el
     [spec](../../docs/superpowers/specs/2026-09-21-conciencia-de-impacto-design.md) §8–§9.
   ```

- [ ] **Step 6: `requisitos.md` y `README.md`**

In `documentacion/02-fase2-estado-del-arte/requisitos.md`:
- **RF-07**: replace `Escalado medido en la campaña vigente: **0,067** (20 de 300, todas VP: las ráfagas desde el origen de administración que la 6ª regla manda al humano antes de bloquear al admin; era 0,0 antes de esa regla).` with:

  ```
  Escalado medido en la campaña vigente (21/09): **0,297** (89 de 300): 20 por confianza (las ráfagas desde el origen de administración que la 6ª regla manda al humano; era 0,0 antes de esa regla) y 69 porque el bloqueo recae sobre un activo interno (`continuidad.actores`, D16).
  ```

- **RF-17**: replace `| **+** Es la entrada de la política de continuidad y de RF-07 |` with:

  ```
  | **+** Es la entrada de la política de continuidad y de RF-07. *Determinado (21/09):* `impacto.determinar` lo calcula desde el inventario del perfil —a quién bloquea la acción (`actores.quien_es`) y qué servicios detiene— y nunca por debajo del nivel del catálogo; queda en la traza (`impacto_determinado`) y en el prompt del analista |
  ```

- **RF-19**: replace `| **+** Precondición, no criterio de escalado: impediría la siguiente respuesta y la verificación |` with:

  ```
  | **+** Precondición, no criterio de escalado: impediría la siguiente respuesta y la verificación. *Reparado (21/09):* la `ip_gestion` del perfil empresarial apuntaba a una IP inexistente; ahora es el auditor (`172.20.20.4`), el canal real del conector, y bloquearla es veto duro en `perfil.filtrar` |
  ```

- **RF-20**: replace `| **+** Sin ellas el informe no puede demostrar que se respetó la continuidad |` with:

  ```
  | **+** Sin ellas el informe no puede demostrar que se respetó la continuidad. *Ampliado (21/09):* `bloqueos_automaticos_indebidos` cuenta además los bloqueos sin humano sobre FP/PROPIA de cualquier impacto, el punto ciego del indicador |
  ```

In `README.md`, replace:
- `Funcional, 306 tests` → `Funcional, <N_prototipo> tests`;
- `Funcional, 39 tests; campaña ejecutada` → `Funcional, <N_evaluacion> tests; campaña ejecutada`.

If the root README states the dataset count anywhere, update it too: `grep -n "37" README.md`.

- [ ] **Step 7: `prototipo/README.md`**

1. In the module table of §1, add three rows after the `prototipo/perfil.py` row:

   ```
   | `prototipo/actores.py` | ¿Quién es esta IP para el cliente? Gestión, dispositivo de red, activo interno o desconocido, resuelto solo desde el perfil (RF-17/19) |
   | `prototipo/impacto.py` | Impacto **determinado** de una acción: a quién bloquea y qué servicios detiene, nunca por debajo del catálogo (RF-17) |
   | `prototipo/inventario.py` | Reconciliación del inventario declarado con lo que ve el auditor (CLI) |
   ```

2. In §5, replace the two bullets (from `- **Acciones de impacto \`localizado\`` through `…no a un capricho del modelo.`) with:

   ```
   - **Bloquear un origen externo (`BLOQUEAR_IP`, localizado) — los perfiles COINCIDEN.** Ambos fijan
     `impacto_localizado: automatica_si_confianza`: con confianza sobre el umbral del perfil
     (`continuidad.umbral_confianza`, 0.7 por defecto — RF-07), ambos lo permiten sin humano.

   - **Bloquear un activo interno — los perfiles DIVERGEN.** `empresarial` inventaría la red del laboratorio y
     retiene para el humano el bloqueo de lo propio (`continuidad.actores`, §5.bis); `residencial` no tiene
     inventario con IPs, así que para él la `192.168.1.10` es un origen cualquiera y la bloquea solo.

   - **Acciones de impacto `alcanza_servicio` (p. ej. `BLOQUEAR_PUERTO`) — los perfiles DIVERGEN.**
     `residencial` trata ese impacto como el localizado (`automatica_si_confianza`): con confianza alta,
     permite. `empresarial` lo tiene en `humano_siempre` y **degrada** a `BLOQUEAR_IP`. El patrón de
     **excepción** «nunca automática» por servicio (el puerto público de un banco) vive en `bancario.yml`
     (`core-db:1521`, `middleware:8443`).
   ```

   In the next paragraph, replace `(\`test_localizado_coincide_en_ambos\` y\n\`test_misma_accion_alcanza_servicio_diverge_por_perfil\`)` with `(\`test_localizado_sobre_origen_externo_coincide_en_ambos\`,\n\`test_bloquear_un_activo_interno_diverge_por_perfil\` y \`test_misma_accion_alcanza_servicio_diverge_por_perfil\`)`.

   In the paragraph «**Por qué la divergencia no se ve corriendo el CLI.**», add at the end: ` Desde la conciencia de impacto (21/09) sí se ve: sobre el dataset, \`empresarial\` retiene para el humano cada bloqueo del puesto (\`veta\` con acción) y \`residencial\` lo permite.`

3. Insert a new section before `## 6. Corrida sobre el dataset real de la Fase 3`:

   ````markdown
   ## 5.bis Conciencia de impacto: a quién bloquea cada acción (21/09/2026)

   El catálogo declara un impacto fijo por tipo de acción; `impacto.determinar` lo **determina** con el
   inventario del perfil (`activos` con `ip`, `funcion`, `criticidad`, `servicios_prestados`) y los hallazgos del
   auditor, y nunca lo deja por debajo del catálogo:

   | La acción es sobre… | Qué se determina |
   |---|---|
   | una IP (`BLOQUEAR_IP`, `BLOQUEAR_IP_FIREWALL`, `MATAR_CONEXION`) | **a quién** bloquea (`actores.quien_es`); un dispositivo de red sube a `alcanza_servicio` |
   | un puerto o servicio (`BLOQUEAR_PUERTO`, `CERRAR_SERVICIO`) | qué servicio detiene, si está **declarado** y si está **abierto** según el auditor |
   | un nodo (`AISLAR_NODO`, `REINICIAR_NODO`) | el **radio**: declarados ∪ abiertos (cota superior) |

   `actores.quien_es` resuelve, en este orden: `gestion` (la `ip_gestion`) > `dispositivo_red` (cortafuegos de la
   topología) > `activo_interno` (inventario, otro nodo de la topología, `redes_internas` u origen legítimo) >
   `desconocido`. `perfil.filtrar` lo aplica a la acción **final**: la gestión es **veto duro** (RF-19); un activo
   interno o un dispositivo de red se retiene para el humano salvo que el perfil diga
   `continuidad.actores.<tipo>: automatica_si_confianza` (D16). La traza guarda `impacto_determinado` y el
   analista ve la línea **Consecuencia**:

   ```
   Consecuencia: bloquea a puesto (activo interno: puesto de trabajo de un empleado) · 0 servicios detenidos
   ```

   El agente de mitigación ve lo mismo en `consultar_topologia` (función, criticidad y servicios de cada
   dispositivo), y su prompt nombra la IP de gestión concreta. La IP de ejecución sale también del perfil
   (`perfil.ip_de`); `orden.IP_DE_NODO` queda como respaldo heredado.

   **Reconciliación** — lo declarado frente a lo descubierto:

   ```bash
   python3 -m prototipo.inventario prototipo/perfiles/empresarial.yml lab/campañas/2026-08-31-evaluacion/hallazgos.json
   ```

   Efecto medido y reconciliación del laboratorio: [`../evaluacion/resultados/README.md`](../evaluacion/resultados/README.md).
   ````

4. At the end of §6 (after the paragraph that ends `…criterio de cierre de\n5A en \`.superpowers/sdd/…/task-11-report.md\`.`), add:

   ```
   > Desde la conciencia de impacto (21/09, §5.bis) el perfil `empresarial` sí produce `veta` sobre el dataset:
   > retiene para el humano cada bloqueo del puesto (`192.168.1.10`), que es un activo interno.
   ```

5. In §10.ter, replace `La topología (\`topologia:\`/\`ip_gestion:\`) vive\n  en el perfil.` with:

   ```
   La topología (`topologia:`/`ip_gestion:`) vive
     en el perfil; `consultar_topologia` devuelve además la función, criticidad y servicios de cada
     dispositivo (del inventario, §5.bis) y el prompt nombra la IP de gestión concreta.
   ```

- [ ] **Step 8: `docs/pruebas` y guía de operación**

**`docs/pruebas/03-lab-en-vivo.md`:**
- line 113: `` `dispositivo ejecutor: gateway`. `` → `` `dispositivo ejecutor: borde`. ``
- In the closing note of §3.5 (`> El flujo típico: …`), after `pide **[Aprobar/Rechazar/Reclasificar]**` insert `(el bloqueo recae sobre \`puesto\`, un activo interno: verás la línea **Consecuencia**)`.

**`docs/pruebas/05-topologias.md`, line 12:** `(\`topologia.gateway.ip = 192.168.1.1\`)` → `(\`topologia.borde.ip = 192.168.1.1\`)`

**`docs/pruebas/04-escenarios-de-ataque.md`:**
1. Matrix row A → `| **A. Auto-bloqueo** | credenciales · T1110.001, **origen externo** | inyección (origen externo) o vivo con \`activo_interno: automatica_si_confianza\` | \`permite\`, \`requiere_humano=false\`, \`Ejecutadas: 1\` |`
2. In «En vivo vs inyección», replace `- **A, B, C, D → en vivo.** A = fuerza bruta SSH a la víctima;` with `- **A, B, C, D → en vivo.** A = fuerza bruta SSH a la víctima (el atacante del lab es interno: en vivo, A pide confirmación salvo con el perfil de abajo);`
3. Replace the intro and the injection block of section A:
   - **Starts at:** `Fuerza bruta SSH contra un activo cuyo auditor confirma exposición`.
   - **Ends at:** the `**Esperado** (salida real):` block of section A.

   **Replacement text:**

   ````markdown
   Fuerza bruta SSH desde un **origen externo** contra un activo cuyo auditor confirma exposición
   (`objetivo-vuln`) → confianza 1.0 → `BLOQUEAR_IP` localizado sobre una IP no inventariada → el perfil
   **permite** sin humano.

   > **Desde el `puesto` (.10) la misma alerta va al analista:** el bloqueo recaería sobre un activo interno del
   > cliente, y el perfil `empresarial` exige humano para bloquear lo propio (D16). Para ver el auto-bloqueo en
   > vivo con el atacante del lab, usa un perfil que automatice los activos internos (decisión del cliente):
   > ```bash
   > sed 's/activo_interno:  humano_siempre/activo_interno:  automatica_si_confianza/' \
   >     prototipo/perfiles/empresarial.yml > /tmp/empresarial-auto-interno.yml
   > ```

   **En vivo** (requiere el lab; ver [03 · Lab en vivo](03-lab-en-vivo.md) §3.5, terminal B; daemon con
   `/tmp/empresarial-auto-interno.yml`):
   ```bash
   for i in $(seq 1 8); do
     docker exec clab-red-cliente-puesto sh -c "sshpass -p mal_$i ssh -o StrictHostKeyChecking=no \
       -o ConnectTimeout=4 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no \
       -o PreferredAuthentications=password msfadmin@192.168.1.30 id 2>/dev/null"; done
   ```

   **Por inyección** (sin lab, origen externo):
   ```bash
   printf '%s\n' '{"id":"A1","rule":{"id":"5760","level":10,"groups":["sshd","authentication_failed"],"mitre":{"id":["T1110.001"]}},"predecoder":{"hostname":"objetivo-vuln","program_name":"sshd"},"data":{"srcip":"203.0.113.9"},"timestamp":"2026-09-09T00:00:00Z","full_log":"Failed password for root from 203.0.113.9"}' \
     | python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml --sin-lab --ventana-agrupacion 0
   ```

   **Esperado** (salida real):
   ```
   <pega aquí las líneas «Clase: …», «Consecuencia: …» y «Ejecutadas: …» de la salida real>
   ```
   ````

   Run the injection command and paste the real lines. Expected:
   - `… accion BLOQUEAR_IP -> BLOQUEAR_IP (filtro permite) …`
   - `Consecuencia: bloquea a 203.0.113.9 (origen no inventariado) · 0 servicios detenidos`
   - `Ejecutadas: 1`
4. Section C, expected output: `aplicada en gateway (rc=0)` → `aplicada en borde (rc=0)`, and `dispositivo ejecutor: gateway` → `dispositivo ejecutor: borde`.

**`docs/pruebas/07-roadmap-pipeline-y-latencia.md`**, section «Provocar el lazo para probarlo»:
- **Starts at:** the paragraph `El lazo humano **sí se dispara con el perfil real**…`.
- **Ends at:** the end of the `bash` block that runs the daemon.

**Replacement text:**

````markdown
El lazo humano **se dispara con el perfil real**: en la campaña vigente, el **29,7 %** de las alertas (89 de
300) van al analista. Son las **20 ráfagas desde el origen de administración** (`192.168.1.1`), que la 6ª regla
clasifica como VP con confianza 0,6 para que un humano confirme antes de bloquear al admin, y las **69 cuyo
bloqueo recaería sobre el puesto de un empleado** (`192.168.1.10`, activo interno: el perfil exige humano para
bloquear lo propio, D16). Cualquier fuerza bruta desde el puesto abre el menú:

```bash
# una alerta (fuerza bruta SSH desde el puesto) por el daemon; --sin-llm lo hace instantáneo, el menú es idéntico
sed -n '188p' lab/campañas/2026-08-31-evaluacion/alerts.json | \
  python3 -m prototipo.stream - prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json \
    --sin-llm --sin-lab --ventana-agrupacion 2 --salida /tmp/traza-menu.jsonl
```
````

Run the command once and answer `2` (rechazar). Check that the prompt shows `Consecuencia: bloquea a puesto (activo interno: puesto de trabajo de un empleado) · 0 servicios detenidos`.

**`documentacion/07-fase7-documentacion-e-informe-final/guia-de-operacion.md`:**
- `activo → \`gateway\` → …` → `activo → \`borde\` → …`
- `  Escalada (el activo no respondio): mitigado · contenido en gateway` → `  Escalada (el activo no respondio): mitigado · contenido en borde`
- In the paragraph that lists what the service shows before waiting for the analyst (`el servicio muestra alerta, clase, prioridad, justificación y acción`), replace that phrase with `el servicio muestra alerta, clase, prioridad, justificación, acción y su **consecuencia** (a quién bloquea y qué servicios detiene; en \`empresarial\`, todo bloqueo de un activo interno pasa por aquí)`.

- [ ] **Step 9: Barrido final**

```bash
grep -rn "gateway" docs/pruebas documentacion/07-fase7-documentacion-e-informe-final lab/scripts prototipo/perfiles | grep -v "gateway:" || echo "sin restos"
grep -rn "192.168.1.100\|servidor-web\|controlador-ot" prototipo/perfiles/empresarial.yml || echo "empresarial limpio"
PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t . 2>&1 | tail -1
PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests -t . 2>&1 | tail -1
PYTHONPATH=. python3 -m unittest discover -s lab/dataset/tests -t . 2>&1 | tail -1
```
Expected:
- En la topología solo quedan claves YAML `gateway:`, que son el enlace del grafo, no el nombre del nodo.
- `empresarial limpio`.
- Tres `OK`.

- [ ] **Step 10: Commit**

```bash
git add evaluacion/resultados/ documentacion/ README.md prototipo/README.md docs/pruebas/
git commit -m "docs(conciencia-impacto): efecto medido (0 automaticas indebidas, escalado 29,7 %), D16 y guias

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## NIVEL 2 (OPCIONAL) — dependencias y cascada

> Solo si el usuario decide ejecutarlo. El Nivel 1 queda completo y fusionable sin estas dos tareas.

### Task 11 (OPCIONAL): `afectados_en_cascada` y su integración en `determinar`

**Files:**
- Modify: `prototipo/impacto.py`
- Test: `prototipo/tests/test_impacto.py`

**Interfaces:**
- Produces:
  - `impacto.afectados_en_cascada(activo, perfil) -> list[str]`: ordenada alfabéticamente, no incluye al propio activo y termina aunque haya ciclos.
  - `determinar` añade la clave `activos_afectados_en_cascada` al dict: con contenido para acciones sobre puerto y sobre nodo, `[]` para las demás.

- [ ] **Step 1: Write the failing test** — append to `prototipo/tests/test_impacto.py`

```python
class TestCascada(unittest.TestCase):
    def _perfil(self, deps):
        return {"activos": {n: {"depende_de": d} for n, d in deps.items()}}

    def test_cadena(self):
        p = self._perfil({"a": [], "b": ["a"], "c": ["b"]})
        self.assertEqual(impacto.afectados_en_cascada("a", p), ["b", "c"])

    def test_diamante_cuenta_cada_activo_una_vez(self):
        p = self._perfil({"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]})
        self.assertEqual(impacto.afectados_en_cascada("a", p), ["b", "c", "d"])

    def test_ciclo_termina_y_no_se_incluye_a_si_mismo(self):
        p = self._perfil({"a": ["b"], "b": ["a"]})
        self.assertEqual(impacto.afectados_en_cascada("a", p), ["b"])

    def test_sin_dependencias(self):
        self.assertEqual(impacto.afectados_en_cascada("a", {"activos": {"a": {}}}), [])

    def test_determinar_la_incluye_para_nodos_y_servicios_no_para_ips(self):
        p = {"activos": {"db": {"servicios_prestados": [5432]}, "app": {"depende_de": ["db"]}}}
        nodo = impacto.determinar("AISLAR_NODO", {}, "db", p, CAT)
        self.assertEqual(nodo["activos_afectados_en_cascada"], ["app"])
        self.assertIn("en cascada: app", nodo["motivo"])
        puerto = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": 5432}, "db", p, CAT)
        self.assertEqual(puerto["activos_afectados_en_cascada"], ["app"])
        ip = impacto.determinar("BLOQUEAR_IP", {"ip": "203.0.113.9"}, "db", p, CAT)
        self.assertEqual(ip["activos_afectados_en_cascada"], [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_impacto -v`
Expected: ERROR `AttributeError: module 'prototipo.impacto' has no attribute 'afectados_en_cascada'`.

- [ ] **Step 3: Write minimal implementation** — `prototipo/impacto.py`

Add after `puertos_abiertos`:
```python
def afectados_en_cascada(activo, perfil):
    """Activos que dependen, directa o indirectamente, de `activo` según `depende_de` (cierre
    transitivo inverso), en orden alfabético. Guardia de ciclos: cada activo se visita una vez. Una
    dependencia no declarada da un falso «sin cascada»: es un límite del inventario (Nivel 2)."""
    dependientes = {}
    for nombre, info in ((perfil or {}).get("activos") or {}).items():
        for dep in (info or {}).get("depende_de") or []:
            dependientes.setdefault(dep, set()).add(nombre)
    vistos, pendientes = set(), [activo]
    while pendientes:
        for d in dependientes.get(pendientes.pop(), ()):
            if d not in vistos and d != activo:
                vistos.add(d)
                pendientes.append(d)
    return sorted(vistos)
```

In `determinar`, replace the `det = {...}` line with:
```python
    cascada = (afectados_en_cascada(activo, perfil)
               if accion_id in ACCIONES_SOBRE_PUERTO or accion_id in ACCIONES_SOBRE_NODO else [])
    det = {"nivel": nivel, "nivel_catalogo": nivel_catalogo, "servicios_afectados": servicios,
           "actor": actor, "activo": activo, "accion_id": accion_id, "activos_afectados_en_cascada": cascada}
```

Rename the current `_motivo` to `_motivo_base` (same body), and add:
```python
def _motivo(det, perfil):
    texto = _motivo_base(det, perfil)
    if det.get("activos_afectados_en_cascada"):
        texto += " · en cascada: " + ", ".join(det["activos_afectados_en_cascada"])
    return texto
```

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t .`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add prototipo/impacto.py prototipo/tests/test_impacto.py
git commit -m "feat(impacto): radio en cascada por dependencias declaradas, con guardia de ciclos (Nivel 2)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 12 (OPCIONAL): dependencias del banco, vista del agente y documentación

**Files:**
- Modify:
  - `prototipo/perfiles/bancario.yml`;
  - `prototipo/agente_mitigacion.py` (`resolver_topologia`, `_describir_nodo`);
  - `prototipo/README.md`;
  - `documentacion/00-general/estado-y-riesgos.md`.
- Test:
  - `prototipo/tests/test_perfil.py`;
  - `prototipo/tests/test_agente_mitigacion.py`.

**Interfaces:**
- Consumes: `impacto.afectados_en_cascada` (Task 11).
- Produces: en `resolver_topologia`, cada nodo con dependientes gana `afecta_en_cascada: [str]`, y `consultar_topologia` lo muestra como `si cae, afecta a: …`.

- [ ] **Step 1: Write the failing tests**

Add to `class TestPerfilBancario` in `prototipo/tests/test_perfil.py`:
```python
    def test_aislar_el_middleware_afecta_en_cascada_a_la_banca(self):   # Nivel 2
        from prototipo import impacto
        d = impacto.determinar("AISLAR_NODO", {}, "middleware", self.p, CAT)
        self.assertEqual(d["activos_afectados_en_cascada"], ["api-movil", "web-banking"])

    def test_caer_el_hsm_arrastra_al_core_y_a_swift(self):
        from prototipo import impacto
        self.assertEqual(impacto.afectados_en_cascada("hsm", self.p),
                         ["api-movil", "middleware", "swift-alliance", "web-banking"])
```

Add to `class TestVistaDelAgente` in `prototipo/tests/test_agente_mitigacion.py`:
```python
    def test_consultar_topologia_muestra_la_cascada(self):
        p = {"topologia": {"db": {"rol": "host_victima", "ip": "10.0.0.5"}},
             "activos": {"db": {"ip": "10.0.0.5"}, "app": {"depende_de": ["db"]}}}
        obs = ag.herramienta_consultar_topologia(ag.resolver_topologia(p))
        self.assertIn("si cae, afecta a: app", obs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_perfil prototipo.tests.test_agente_mitigacion -v`
Expected: FAIL (cascade `[]`, `'si cae, afecta a' not found`).

- [ ] **Step 3: Implement**

`prototipo/perfiles/bancario.yml` — add `depende_de` to four activos. Keep everything else on each line.
- `web-banking`: `…, servicios_prestados: [443, 80], depende_de: [middleware] }`
- `api-movil`: `…, servicios_prestados: [443], depende_de: [middleware] }`
- `swift-alliance`: `…, servicios_prestados: [], depende_de: [hsm] }`
- `middleware`: `…, servicios_prestados: [8443], depende_de: [core-db, hsm] }`

Add above `activos:` the comment line `# depende_de (Nivel 2): si cae uno de esos activos, este se ve afectado.`

`prototipo/agente_mitigacion.py` — in `resolver_topologia`, after the `servicios_abiertos` block, add:
```python
        cascada = impacto.afectados_en_cascada(nombre, perfil)
        if cascada:
            enriquecido["afecta_en_cascada"] = cascada
```
In `_describir_nodo`, before `base = …`, add:
```python
    if nodo.get("afecta_en_cascada"):
        detalles.append("si cae, afecta a: " + ", ".join(nodo["afecta_en_cascada"]))
```

**`prototipo/README.md` §5.bis** — add this paragraph at the end:

```
**Dependencias (Nivel 2).** Un activo puede declarar `depende_de: [...]`; `impacto.afectados_en_cascada`
calcula quién depende, directa o indirectamente, del activo tocado (con guardia de ciclos) y
`impacto_determinado.activos_afectados_en_cascada` lo lleva a la traza, al analista y al agente. En
`bancario.yml`: aislar el middleware afecta en cascada a la banca en línea y a la API móvil. Una
dependencia no declarada da un falso «sin cascada»: es un límite del inventario, no del motor.
```

**`documentacion/00-general/estado-y-riesgos.md`:**
- Delete the §7 bullet «Dependencias entre activos y radio en cascada (Nivel 2…)», added in Task 10.
- Append to the row «5 — Implementación», right before its closing ` |`: ` Con **dependencias declaradas** entre activos y radio de impacto en cascada (Nivel 2).`

- [ ] **Step 4: Run all suites**

```bash
PYTHONPATH=. python3 -m unittest discover -s prototipo/tests -t . 2>&1 | tail -1
PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests -t . 2>&1 | tail -1
PYTHONPATH=. python3 -m unittest discover -s lab/dataset/tests -t . 2>&1 | tail -1
```
Expected: OK × 3. Update the test counts in `README.md` and in `estado-y-riesgos.md` row 5 if they changed.

- [ ] **Step 5: Commit**

```bash
git add prototipo/perfiles/bancario.yml prototipo/agente_mitigacion.py prototipo/README.md \
        documentacion/00-general/estado-y-riesgos.md README.md \
        prototipo/tests/test_perfil.py prototipo/tests/test_agente_mitigacion.py
git commit -m "feat(bancario): dependencias declaradas y cascada visible para el analista y el agente (Nivel 2)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Cierre

- [ ] Revisión final del conjunto (todas las tareas) y **superpowers:finishing-a-development-branch**. Fusión `--no-ff` de `feature/conciencia-impacto` a `main` local; **sin push**.
