# Taxonomía de familias extensible — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el `set` hardcodeado de familias por un registro extensible alineado a MITRE, y añadir un tercer nivel de respuesta (`triar_y_enrutar`) entre `actuar` y `no_soportada`.

**Architecture:** Un registro `familias.yml` (familia → mitre/nivel/ruta) que `analisis.clasificar` consulta; una clase genérica `amenaza_enrutada` para lo enrutado (sin contención); el rol lógico de ruta se enlaza al destino real del cliente en el perfil. El motor sigue agnóstico; lo específico del SIEM vive en el adaptador, lo del cliente en el perfil.

**Tech Stack:** Python 3 + PyYAML, biblioteca estándar. Tests con `unittest` (sin pytest). Ejecutar desde la raíz con `PYTHONPATH=.`.

**Spec:** `docs/superpowers/specs/2026-09-16-taxonomia-familias-extensible-design.md`

## Global Constraints

- Sin `pip`/`venv`/`pytest`: tests con `python3 -m unittest`.
- Determinismo y reproducibilidad (RNF-03): misma entrada → misma salida; el registro es dato, no aleatorio.
- Catálogo cerrado (RF-15): `triar_y_enrutar` **no** propone acción de contención.
- Cero regresión: las 3 familias actuales (`acceso_credenciales`, `reconocimiento`, `servicio_expuesto`) clasifican igual que hoy.
- Commits terminan con `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Ajuste sobre el spec (§4.6):** en vez de retirar `explotacion_conocida`, se reutiliza como la familia ejemplar `triar_y_enrutar` (ya tiene mapeo MITRE T1190/T1210/T1203, ficha de corpus `mapeo-explotacion_conocida` y 3 casos en `evaluacion/simulaciones/ataques.jsonl`).

---

### Task 1: El registro de familias (`familias.yml` + `familias.py`)

**Files:**
- Create: `prototipo/familias.yml`
- Create: `prototipo/familias.py`
- Test: `prototipo/tests/test_familias.py`

**Interfaces:**
- Produces: `familias.registro() -> dict` (familia→`{mitre: list, nivel: str, ruta: str|None}`); `familias.cargar_registro(ruta=RUTA) -> dict`.

- [ ] **Step 1: Write `familias.yml`**

```yaml
# Registro de familias de ataque: familia -> {mitre, nivel, ruta}. Extensible y alineado a MITRE.
# nivel: 'actuar' (contener con el catalogo) | 'triar_y_enrutar' (clasificar + encaminar, sin contener).
# Una familia AUSENTE de este registro -> no_soportada (frontera honesta). 'plataforma'/'otra' no se listan.
acceso_credenciales:  { mitre: [T1110, T1078], nivel: actuar }
reconocimiento:       { mitre: [T1595, T1046], nivel: actuar }
servicio_expuesto:    { mitre: [T1190],        nivel: actuar }
explotacion_conocida: { mitre: [T1190, T1210, T1203], nivel: triar_y_enrutar, ruta: appsec }
```

- [ ] **Step 2: Write the failing test**

```python
# prototipo/tests/test_familias.py
import unittest
from prototipo import familias

class TestRegistroFamilias(unittest.TestCase):
    def test_familia_actuar_trae_nivel_y_mitre(self):
        e = familias.registro()["acceso_credenciales"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertIn("T1110", e["mitre"])

    def test_familia_enrutada_trae_ruta(self):
        e = familias.registro()["explotacion_conocida"]
        self.assertEqual(e["nivel"], "triar_y_enrutar")
        self.assertEqual(e["ruta"], "appsec")

    def test_familia_ausente_es_none(self):
        self.assertIsNone(familias.registro().get("plataforma"))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_familias -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'prototipo.familias'`.

- [ ] **Step 4: Write `familias.py`**

```python
"""Registro de familias de ataque: familia -> {mitre, nivel, ruta}. Extensible, alineado a MITRE.

nivel de respuesta: 'actuar' (contener con el catalogo cerrado) | 'triar_y_enrutar' (clasificar,
priorizar, enriquecer y encaminar, SIN contener). Una familia ausente del registro -> no_soportada.
El registro es dato (RNF-03): mismo fichero, mismo comportamiento."""
import os, yaml

RUTA = os.path.join(os.path.dirname(__file__), "familias.yml")
_REGISTRO = None

def cargar_registro(ruta=RUTA):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def registro():
    global _REGISTRO
    if _REGISTRO is None:
        _REGISTRO = cargar_registro()
    return _REGISTRO
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_familias -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add prototipo/familias.yml prototipo/familias.py prototipo/tests/test_familias.py
git commit -m "feat(familias): registro extensible de familias alineado a MITRE

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `analisis.clasificar` consulta el registro

**Files:**
- Modify: `prototipo/analisis.py` (import de `familias`, `_PRIORIDAD_BASE`, `clasificar`)
- Test: `prototipo/tests/test_analisis.py`

**Interfaces:**
- Consumes: `familias.registro()`.
- Produces: `analisis.clasificar(alerta, contexto, registro=None) -> {clase, prioridad, confianza, ruta?}`. `ruta` sólo aparece cuando `clase == "amenaza_enrutada"`.

- [ ] **Step 1: Write the failing test**

```python
# añadir a prototipo/tests/test_analisis.py (dentro de la clase de clasificar existente o una nueva)
from prototipo import analisis

class TestClasificarRegistro(unittest.TestCase):
    def _ctx(self, **kw):
        base = {"postura": None, "criticidad": "media", "origen_legitimo": False,
                "rafaga": 0, "umbral_rafaga": 9}
        base.update(kw); return base

    def test_familia_ausente_es_no_soportada(self):
        r = analisis.clasificar({"familia": "plataforma"}, self._ctx())
        self.assertEqual(r["clase"], "no_soportada")

    def test_familia_enrutada_produce_amenaza_enrutada_con_ruta(self):
        r = analisis.clasificar({"familia": "explotacion_conocida"}, self._ctx())
        self.assertEqual(r["clase"], "amenaza_enrutada")
        self.assertEqual(r["ruta"], "appsec")

    def test_familia_actuar_conserva_la_logica_vp(self):
        # postura None + familia de ataque -> vp_intento_acceso 0.5 (sin cambios)
        r = analisis.clasificar({"familia": "acceso_credenciales"}, self._ctx())
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 0.5)
        self.assertNotIn("ruta", r)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_analisis.TestClasificarRegistro -v`
Expected: FAIL (`test_familia_enrutada...` da `no_soportada` porque hoy `explotacion_conocida` cae en el camino de postura, y no existe `amenaza_enrutada`).

- [ ] **Step 3: Modify `prototipo/analisis.py`**

Añadir el import tras la línea 2 (`from prototipo.postura import ...`):

```python
from prototipo import familias
```

Añadir `amenaza_enrutada` a `_PRIORIDAD_BASE` (junto a las demás clases):

```python
    "amenaza_enrutada": 3,
```

Reemplazar la función `clasificar` entera por:

```python
def clasificar(alerta, contexto, registro=None):
    reg = registro if registro is not None else familias.registro()
    entrada = reg.get(alerta.get("familia"))
    postura = contexto.get("postura")
    umbral = contexto.get("umbral_rafaga")
    en_rafaga = bool(umbral) and (contexto.get("rafaga") or 0) >= umbral
    ruta = None
    if entrada is None:                                 # fuera del registro -> honesto
        clase, confianza = "no_soportada", 1.0
    elif entrada.get("nivel") == "triar_y_enrutar":     # se tria y encamina, no se contiene
        clase, confianza, ruta = "amenaza_enrutada", 1.0, entrada.get("ruta")
    elif contexto.get("origen_legitimo") and en_rafaga:
        clase, confianza = "vp_intento_acceso", 0.6
    elif contexto.get("origen_legitimo"):
        clase, confianza = "fp_actividad_legitima", 1.0
    elif postura is None:
        clase, confianza = "vp_intento_acceso", 0.5
    elif postura.get("expuesto"):
        clase, confianza = "vp_intento_acceso", 1.0
    else:
        clase, confianza = "fp_exposicion_inexistente", 1.0
    salida = {"clase": clase, "prioridad": _priorizar(clase, contexto.get("criticidad")),
              "confianza": confianza}
    if ruta is not None:
        salida["ruta"] = ruta
    return salida
```

Borrar la línea `FAMILIAS_ATAQUE = {...}` (ya no se usa; el único consumidor era esta función).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_analisis -v`
Expected: PASS (los nuevos y los existentes de clasificar).

- [ ] **Step 5: Commit**

```bash
git add prototipo/analisis.py prototipo/tests/test_analisis.py
git commit -m "feat(clasificar): consultar el registro de familias (+ nivel triar_y_enrutar)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `politica.proponer` — `amenaza_enrutada` no propone contención

**Files:**
- Modify: `prototipo/politica.py:3-11` (`ACCION_POR_CLASE`)
- Test: `prototipo/tests/test_politica.py`

**Interfaces:**
- Consumes: la clase `amenaza_enrutada` de Task 2.
- Produces: `politica.proponer("amenaza_enrutada", alerta) -> (None, {})`.

- [ ] **Step 1: Write the failing test**

```python
# añadir a prototipo/tests/test_politica.py
def test_amenaza_enrutada_no_propone_accion(self):
    from prototipo import politica
    accion, params = politica.proponer("amenaza_enrutada", {"origen_ip": "1.2.3.4"})
    self.assertIsNone(accion)
    self.assertEqual(params, {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politica -v`
Expected: PASS por casualidad (el `.get` ya devuelve None). Si PASA, sigue igualmente al Step 3 para dejar la intención explícita; si por el diseño del test FALLA, el Step 3 lo corrige.

- [ ] **Step 3: Modify `prototipo/politica.py`**

Añadir la clave explícita a `ACCION_POR_CLASE` (documenta que es intencional, no un olvido):

```python
    "amenaza_enrutada": None,   # se tria y encamina; sin contencion automatica
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_politica -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/politica.py prototipo/tests/test_politica.py
git commit -m "feat(politica): amenaza_enrutada sin contencion (se encamina)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Propagar la ruta (perfil binding + triaje + traza)

**Files:**
- Modify: `prototipo/perfil.py` (nueva función `ruta_de`)
- Modify: `prototipo/triaje.py:5-24` (`procesar`: resolver e inyectar `ruta`)
- Modify: `prototipo/traza.py:207-230` (`construir`: campo `ruta`)
- Modify: `prototipo/perfiles/bancario.yml` (bloque `rutas` de ejemplo)
- Test: `prototipo/tests/test_perfil.py`, `prototipo/tests/test_triaje.py`

**Interfaces:**
- Consumes: `clas.get("ruta")` (rol lógico) de Task 2.
- Produces: `perfil.ruta_de(perfil, rol) -> str|None` (destino del cliente, o el rol si no hay binding); la traza lleva la clave `ruta`.

- [ ] **Step 1: Write the failing tests**

```python
# prototipo/tests/test_perfil.py  (en TestPerfilBancario o una clase nueva)
def test_ruta_de_resuelve_con_binding_y_cae_al_rol(self):
    p = {"rutas": {"appsec": "cola-appsec-banco"}}
    self.assertEqual(perfil.ruta_de(p, "appsec"), "cola-appsec-banco")
    self.assertEqual(perfil.ruta_de({}, "appsec"), "appsec")   # sin binding -> rol logico
    self.assertIsNone(perfil.ruta_de(p, None))
```

```python
# prototipo/tests/test_triaje.py
def test_amenaza_enrutada_lleva_ruta_en_la_traza_sin_accion(self):
    from prototipo import triaje, catalogo as catm
    cat = catm.cargar_catalogo("prototipo/catalogo.yml")
    alerta = {"familia": "explotacion_conocida", "origen_ip": "203.0.113.9",
              "activo": "web-banking", "servicio": "https", "mitre": ["T1190"]}
    perfil = {"activos": {}, "continuidad": {}, "rutas": {"appsec": "cola-appsec-banco"}}
    tr = triaje.procesar(alerta, {"nodos": {}}, perfil, "bancario", cat, "d1", "t")
    self.assertEqual(tr["clase"], "amenaza_enrutada")
    self.assertEqual(tr["ruta"], "cola-appsec-banco")
    self.assertIsNone(tr["accion_propuesta"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_perfil prototipo.tests.test_triaje -v`
Expected: FAIL (`ruta_de` no existe; la traza no tiene clave `ruta`).

- [ ] **Step 3: Implement**

En `prototipo/perfil.py`, añadir:

```python
def ruta_de(perfil, rol):
    """Rol logico de ruta (p. ej. 'appsec') -> destino real del cliente. Sin binding, el rol mismo.
    El registro de familias es agnostico; el binding a la cola/equipo del cliente vive en el perfil."""
    if not rol:
        return None
    return perfil.get("rutas", {}).get(rol, rol)
```

En `prototipo/triaje.py`, dentro de `procesar`, tras `clas = analisis.clasificar(...)` y antes del `return`, resolver la ruta e inyectarla en `analisis_out`. Cambiar la construcción de `analisis_out` a:

```python
    ruta = perfilm.ruta_de(perfil_dict, clas.get("ruta"))
    analisis_out = {**clas, "justificacion": just, "version_justificador": version_just,
                    "pasajes_usados": pasajes, "consulta_rag": consulta_rag,
                    "recuperacion_agentica": recuperacion_agentica, "ruta": ruta}
```

En `prototipo/traza.py`, dentro de `construir`, añadir el campo (junto a `recuperacion_agentica`):

```python
        "ruta": analisis_out.get("ruta"),                    # rol/destino de encaminamiento (triar_y_enrutar)
```

En `prototipo/perfiles/bancario.yml`, añadir al final (ejemplo de binding):

```yaml
# Binding de rutas logicas -> destinos reales del cliente (nivel triar_y_enrutar).
rutas:
  appsec: cola-appsec-banco
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_perfil prototipo.tests.test_triaje -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/perfil.py prototipo/triaje.py prototipo/traza.py prototipo/perfiles/bancario.yml prototipo/tests/test_perfil.py prototipo/tests/test_triaje.py
git commit -m "feat(ruta): propagar el encaminamiento a la traza (binding en el perfil)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: El daemon imprime el encaminamiento

**Files:**
- Modify: `prototipo/stream.py:32-44` (`_linea_decision`)
- Test: `prototipo/tests/test_stream.py`

**Interfaces:**
- Consumes: la traza con `clase == "amenaza_enrutada"` y `ruta` (Task 4).
- Produces: `_linea_decision(d)` incluye una línea de encaminamiento cuando la clase es `amenaza_enrutada`.

- [ ] **Step 1: Write the failing test**

```python
# prototipo/tests/test_stream.py
def test_linea_decision_muestra_encaminamiento(self):
    from prototipo import stream
    d = {"clase": "amenaza_enrutada", "prioridad": 3, "confianza": 1.0,
         "accion_propuesta": None, "accion_final": None, "resultado_filtro": "sin_accion",
         "version_justificador": "plantilla-0", "ruta": "cola-appsec-banco"}
    linea = stream._linea_decision(d)
    self.assertIn("Enrutado a: cola-appsec-banco", linea)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_stream.TestStream.test_linea_decision_muestra_encaminamiento -v`
Expected: FAIL (la línea no menciona el encaminamiento). Si el nombre de la clase de tests difiere, usar el que exista en el fichero.

- [ ] **Step 3: Modify `prototipo/stream.py`**

En `_linea_decision`, antes del `return base`, añadir:

```python
    if d.get("clase") == "amenaza_enrutada":
        base += f"\n  Enrutado a: {d.get('ruta')} (triaje sin contencion automatica)"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest prototipo.tests.test_stream -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add prototipo/stream.py prototipo/tests/test_stream.py
git commit -m "feat(stream): el daemon imprime el encaminamiento de una amenaza enrutada

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Reconciliar la taxonomía en el caso de uso + verificación global

**Files:**
- Modify: `documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md` (§5 «no soportada» y §6 categorías)

**Interfaces:** ninguna (documentación + verificación de no-regresión).

- [ ] **Step 1: Actualizar el caso de uso**

En `caso-de-uso-acotado.md`, tras la tabla de categorías (§6), añadir un bloque que describa los **tres niveles de respuesta** y el **registro `familias.yml`**, y liste explícitamente las categorías **fuera de alcance conocido**. Texto a insertar:

```markdown
### Los tres niveles de respuesta y el registro de familias

La familia de una alerta determina no sólo su clase sino **qué hace el motor con ella**, según el
registro extensible `prototipo/familias.yml` (familia → técnica MITRE + nivel):

- **actuar** — el motor clasifica VP/FP y propone contención del catálogo cerrado. Las familias de
  plano de gestión (`acceso_credenciales`, `reconocimiento`, `servicio_expuesto`).
- **triar_y_enrutar** — el motor clasifica, prioriza y **encamina** a un equipo con contexto MITRE,
  **sin** contener automáticamente (p. ej. `explotacion_conocida` → AppSec). Para amenazas que no
  deben auto-contenerse (romperían el servicio) pero sí triarse.
- **no soportada** — familia ausente del registro: a cola manual con su severidad.

Añadir una familia = una línea en el registro. La cobertura real por cliente es *registro ∩ lo que
detecta su SIEM*. **Fuera de alcance conocido** (hoy → no soportada, por decisión, no por olvido):
malware/C2, movimiento lateral, manipulación de red (MITM/ARP), DoS, y fraude de pagos/ATM.
```

- [ ] **Step 2: Commit de la doc**

```bash
git add documentacion/01-fase1-analisis-del-modulo/caso-de-uso-acotado.md
git commit -m "docs(caso-de-uso): tres niveles de respuesta y registro de familias

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: Verificación global de no-regresión**

Run: `PYTHONPATH=. python3 -m unittest discover -s prototipo/tests`
Expected: OK, sin fallos.

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/dataset/tests`
Expected: OK (las 3 familias reales del dataset clasifican igual; `explotacion_conocida` no tiene muestras en `etiquetado.jsonl`, así que no cambia el conteo).

Run: `PYTHONPATH=. python3 -m unittest discover -s evaluacion/tests`
Expected: OK (el banco de recuperación RAG usa `explotacion_conocida` para *recuperación*, no para clasificación; no le afecta el cambio de clase).

- [ ] **Step 4: Verificación manual del flujo enrutado (opcional, si el lab está arriba)**

Inyectar una alerta de `explotacion_conocida` por el daemon con `bancario.yml` y comprobar que la traza
lleva `clase: amenaza_enrutada`, `ruta: cola-appsec-banco`, `accion_final: null`, y que el daemon imprime
`Enrutado a: cola-appsec-banco`.

---

## Self-Review (completado)

- **Cobertura del spec:** registro (T1), nivel triar_y_enrutar (T2), clase amenaza_enrutada (T2), política sin acción (T3), binding de ruta en perfil + traza (T4), daemon (T5), migración/doc (T6). Cubierto.
- **Ajuste señalado:** el spec proponía retirar `explotacion_conocida`; el plan la reutiliza como ejemplar `triar_y_enrutar` (tiene MITRE+corpus+sims). Es un cambio de mejora, marcado en Global Constraints.
- **Sin placeholders:** cada paso lleva el código o comando real.
- **Consistencia de tipos:** `clasificar(...,registro=None)`, `familias.registro()`, `perfil.ruta_de(perfil, rol)`, clave `ruta` en analisis_out y traza — nombres consistentes entre tareas.
