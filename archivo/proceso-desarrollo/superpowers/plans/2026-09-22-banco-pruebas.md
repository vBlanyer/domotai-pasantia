# Banco de pruebas del laboratorio del banco — Plan 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir la base `lab/banco/regresion.py` (5 casos, CASCADA verificado en vivo) en el banco de pruebas completo del catálogo del spec: una definición por caso, un ejecutor con cuatro resultados (OK/FALLO/BLOQUEADO/OMITIDO), los alcances real/inyectada/perfil, los modos `--todos`/`--caso`/`--paso-a-paso`/`--guias` y un informe por grupo y por alcance.

**Architecture:** El catálogo de casos vive en `lab/banco/casos.py` como dicts de Python (no YAML: es más simple y ya está probado; se documenta la desviación del spec). Cada caso declara su `nivel`: `decision` (se comprueba llamando a `triaje.procesar` con una alerta sintética, sin lab, determinista), `inyectada` (se entrega la acción a `perfil.filtrar`+`impacto`, sin lab), `perfil` (solo lógica del perfil) o `vivo` (extremo a extremo por Wazuh y el conector). El ejecutor `lab/banco/pruebas.py` (renombra `regresion.py`) despacha por nivel y produce el informe. Los niveles sin lab corren en segundos y son deterministas; solo los `vivo` necesitan el banco levantado.

**Tech Stack:** Python 3 (biblioteca estándar; PyYAML solo para cargar el perfil en los tests), `unittest`, Docker/Containerlab para los casos `vivo`, el prototipo (`prototipo/triaje.py`, `perfil.py`, `impacto.py`, `conector.py`, `stream.py`).

**Spec:** `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md` (§4 catálogo, §6 banco de pruebas).

## Global Constraints

- Python 3 con la biblioteca estándar y PyYAML; tests con `unittest`: `PYTHONPATH=. python3 -m unittest discover -s <dir> -t .`. Sin pip, venv ni pytest.
- Suites que siempre deben seguir en verde: `prototipo/tests`, `evaluacion/tests`, `lab/dataset/tests` y `lab/banco/tests`.
- **No se modifica `prototipo/` (código):** el banco de pruebas mide el prototipo, no lo cambia. Los fallos que destape (K1, C4) se documentan, no se arreglan aquí.
- Commits que terminan exactamente en `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Rama `feature/banco-pruebas` (ya creada, sobre `feature/laboratorio-banco`). Nunca push.
- Ataques y tráfico solo dentro del laboratorio de Containerlab; todo local (RNF-01).
- No se modifican el plan de trabajo, el roadmap, el informe `.tex`, los documentos de las Fases 1–4 ni `informe-evaluacion.md`.
- **Cuatro resultados por caso:** `OK` (lo observado coincide con lo esperado; una discrepancia o un fallo declarados como esperados cuentan como OK), `FALLO` (diferencia no esperada), `BLOQUEADO` (el laboratorio no estaba en estado base — problema del laboratorio, no del prototipo), `OMITIDO` (falta un requisito, p. ej. el modelo, con el motivo).
- **K1 y C4 son fallos conocidos del prototipo** y sus casos declaran `fallo_esperado`: OK mientras el fallo persista; si el prototipo se corrige, el caso pasará a FALLO y habrá que actualizar lo esperado.
- Perfil del banco: `prototipo/perfiles/bancario.yml`. Hallazgos del auditor del banco: `lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json`. Nodo de gestión del conector: `clab-banco-mdr-siem` (`TRIAJE_NODO_GESTION`).

## Contexto: lo que ya existe (base, commit 4089513)

`lab/banco/regresion.py` ya tiene, probado en `lab/banco/tests/test_regresion.py` (12 tests):
- `CASOS`: 5 dicts (CASCADA, D1, A1, K1, E1) con `id`, `titulo`, `ataque`/`preparar`, `origen`, `menu`/`escalada`, `esperado`, `deshacer`.
- Funciones puras: `reglas_extra(salida)`, `caidos(muestra)`, `Lector(menu, escalada)`, `fuente_filtrada(lineas, ip, parar)`, `evaluar(esperado, registro, reglas, caidos_obs, preguntas)`.
- E/S con el lab: `_exec`, `leer_salud`, `leer_reglas`, `esperar_salud`, `estado_base`, `_lineas_wazuh`, `decidir`, `deshacer`, `correr_caso`, `informe`, `main`.

Este plan **renombra** `regresion.py`→`pruebas.py` y `test_regresion.py`→`test_pruebas.py`, **separa** el catálogo a `casos.py`, y **añade** los niveles `decision`/`inyectada`/`perfil`, los resultados `OMITIDO`/`fallo_esperado`, y los modos `--paso-a-paso`/`--guias`.

## File Structure

| Fichero | Responsabilidad |
|---|---|
| `lab/banco/casos.py` | El catálogo: una lista `CASOS` de dicts, cada uno con `nivel` y lo esperado. Sin E/S. |
| `lab/banco/pruebas.py` | El ejecutor: despacha por nivel, produce los cuatro resultados y el informe. (Renombra `regresion.py`.) |
| `lab/banco/tests/test_pruebas.py` | Tests de las funciones puras y del despacho. (Renombra `test_regresion.py`.) |
| `lab/banco/tests/test_casos.py` | Tests de coherencia del catálogo. |
| `docs/pruebas/banco/` | Guías generadas por `--guias` (una por caso). |
| `lab/banco/README.md`, `docs/pruebas/08-laboratorio-banco.md`, `documentacion/00-general/estado-y-riesgos.md` | Documentación. |

---

### Task 1: Renombrar a `pruebas.py` y extraer el catálogo a `casos.py`

**Files:**
- Rename: `lab/banco/regresion.py` → `lab/banco/pruebas.py`; `lab/banco/tests/test_regresion.py` → `lab/banco/tests/test_pruebas.py`
- Create: `lab/banco/casos.py`
- Test: `lab/banco/tests/test_casos.py`

**Interfaces:**
- Produces: `casos.CASOS` (la lista de dicts, movida desde `regresion.py`), `casos.NIVELES = ("decision", "inyectada", "perfil", "vivo")`. `pruebas.py` importa `from lab.banco import casos` y usa `casos.CASOS`.

- [ ] **Step 1: Mover el catálogo**

`git mv lab/banco/regresion.py lab/banco/pruebas.py` y `git mv lab/banco/tests/test_regresion.py lab/banco/tests/test_pruebas.py`. En `test_pruebas.py`, cambia `from lab.banco import regresion as rg` por `from lab.banco import pruebas as rg`.

Crea `lab/banco/casos.py` moviendo desde `pruebas.py` el bloque `CASOS`, el helper `_fuerza_bruta`, y las constantes `K1_CAEN` y `TODOS` (déjalas donde las usa cada uno; `TODOS`/`ESPERA_WAZUH` etc. que son de ejecución se quedan en `pruebas.py`). Añade al principio de cada dict de `CASOS` la clave `"nivel": "vivo"` (excepto CASCADA que es `"nivel": "vivo"` también — usa el monitor). Añade `NIVELES = ("decision", "inyectada", "perfil", "vivo")`.

`casos.py` no importa nada de ejecución; solo `from lab.banco import red` si `_fuerza_bruta` lo necesita (no lo necesita — usa IPs literales). En `pruebas.py`, sustituye la definición local de `CASOS` por `from lab.banco import casos` y usa `casos.CASOS`.

- [ ] **Step 2: Test de coherencia del catálogo (falla primero)**

`lab/banco/tests/test_casos.py`:

```python
import unittest
from lab.banco import casos


class TestCatalogo(unittest.TestCase):
    def test_cada_caso_tiene_id_titulo_y_nivel_valido(self):
        vistos = set()
        for c in casos.CASOS:
            self.assertTrue(c["id"] and c["titulo"], c)
            self.assertIn(c["nivel"], casos.NIVELES, c["id"])
            self.assertNotIn(c["id"], vistos, f"id duplicado: {c['id']}")
            vistos.add(c["id"])

    def test_los_casos_vivos_se_pueden_deshacer(self):
        for c in casos.CASOS:
            if c["nivel"] == "vivo":
                self.assertIn("deshacer", c, c["id"])

    def test_todo_caso_tiene_esperado(self):
        for c in casos.CASOS:
            self.assertIn("esperado", c, c["id"])


if __name__ == "__main__":
    unittest.main()
```

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_casos` → FALLA (no existe `casos`).

- [ ] **Step 3: Verificar que pasa y no hay regresión**

Run: `for d in prototipo/tests evaluacion/tests lab/dataset/tests lab/banco/tests; do PYTHONPATH=. python3 -m unittest discover -s $d -t . 2>&1 | tail -1; done`
Expected: `OK` en las cuatro. Ajusta cualquier import que quede apuntando a `regresion`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(banco): banco de pruebas (pruebas.py) y catalogo separado (casos.py)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Resultado OMITIDO y fallo/discrepancia esperados en el ejecutor

**Files:**
- Modify: `lab/banco/pruebas.py` (`evaluar`, `correr_caso`)
- Test: `lab/banco/tests/test_pruebas.py`

**Interfaces:**
- Consumes: `casos.CASOS`.
- Produces: `pruebas.evaluar(esperado, registro, reglas, caidos_obs, preguntas) -> list[str]` (sin cambio de firma); `pruebas.correr_caso(...)` devuelve `{"resultado": "OK"|"FALLO"|"BLOQUEADO"|"OMITIDO", "detalle": [...], ...}`. Un caso con `esperado["fallo_esperado"]` (str, el motivo) invierte: si hay fallos → OK con nota, si no hay fallos → FALLO («el fallo esperado ya no ocurre»). Un caso con `requiere` no satisfecho → OMITIDO.

- [ ] **Step 1: Tests (fallan primero)**

Añade a `test_pruebas.py`:

```python
class TestFalloEsperado(unittest.TestCase):
    def test_fallo_esperado_presente_es_ok(self):
        # el prototipo NO predice la cascada (fallo K1): con fallo_esperado, eso es OK
        r = rg.veredicto_caso({"fallo_esperado": "K1: no predice la cascada"}, ["prediccion_cascada: ..."])
        self.assertEqual(r, ("OK", ["fallo conocido reproducido: K1: no predice la cascada"]))

    def test_fallo_esperado_ausente_es_fallo(self):
        r = rg.veredicto_caso({"fallo_esperado": "K1: no predice la cascada"}, [])
        self.assertEqual(r[0], "FALLO")
        self.assertIn("ya no ocurre", r[1][0])

    def test_sin_fallo_esperado_los_fallos_son_fallo(self):
        self.assertEqual(rg.veredicto_caso({}, ["x"]), ("FALLO", ["x"]))
        self.assertEqual(rg.veredicto_caso({}, []), ("OK", []))
```

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_pruebas -k FalloEsperado` → FALLA.

- [ ] **Step 2: Implementar `veredicto_caso` y usarla en `correr_caso`**

En `pruebas.py`:

```python
def veredicto_caso(esperado, fallos):
    """Traduce los fallos crudos al resultado del caso, contemplando `fallo_esperado`."""
    motivo = esperado.get("fallo_esperado")
    if motivo:
        if fallos:
            return "OK", [f"fallo conocido reproducido: {motivo}"]
        return "FALLO", [f"el fallo esperado ya no ocurre ({motivo}): el prototipo pudo haberse corregido"]
    return ("FALLO" if fallos else "OK"), fallos
```

En `correr_caso`, sustituye el cálculo final del resultado por:

```python
    resultado, detalle = veredicto_caso(caso["esperado"], fallos)
    return {**res, "resultado": resultado, "detalle": detalle, "segundos": round(time.time() - t0)}
```

Añade al principio de `correr_caso`, tras construir `res`, la comprobación de requisitos:

```python
    falta = caso.get("requiere")
    if falta and not _requisito_ok(falta):
        return {**res, "resultado": "OMITIDO", "detalle": [f"requiere {falta}"], "segundos": 0}
```

y la función:

```python
def _requisito_ok(requisito):
    """Hoy solo se conoce 'modelo' (el servidor LLM del justificador/agente), que el banco no usa."""
    return False   # ningun requisito se da por satisfecho: los casos que lo declaran se omiten
```

- [ ] **Step 3: Verificar**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_pruebas` → `OK`.

- [ ] **Step 4: Commit**

```bash
git add lab/banco/pruebas.py lab/banco/tests/test_pruebas.py
git commit -m "feat(banco): resultados OMITIDO y fallo_esperado en el ejecutor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Nivel `decision` — casos de clasificación sin laboratorio

**Files:**
- Modify: `lab/banco/pruebas.py` (`correr_caso` despacha por nivel; nueva `correr_decision`)
- Modify: `lab/banco/casos.py` (añadir los casos de decisión)
- Test: `lab/banco/tests/test_pruebas.py`

**Interfaces:**
- Consumes: `prototipo.triaje.procesar`, `perfil.cargar`, `catalogo.cargar_catalogo`, `validacion.filtro_legible`.
- Produces: `pruebas.correr_decision(caso, perfil, hallazgos, catalogo) -> dict` (mismo formato de resultado). Un caso `nivel: decision` declara `alerta` (dict con origen_ip/activo/servicio/familia/regla_id/rafaga_60s opcional) y `esperado` con claves entre `clase`, `confianza`, `accion_final`, `requiere_humano`, `filtro` (el texto legible), `prediccion_cascada`.

- [ ] **Step 1: Tests (fallan primero)**

```python
class TestNivelDecision(unittest.TestCase):
    def setUp(self):
        import os
        from prototipo import perfil, catalogo
        raiz = rg.RAIZ
        self.p = perfil.cargar(os.path.join(raiz, "prototipo/perfiles/bancario.yml"))
        self.c = catalogo.cargar_catalogo(os.path.join(raiz, "prototipo/catalogo.yml"))
        import json
        self.h = json.load(open(rg.HALLAZGOS, encoding="utf-8"))

    def _correr(self, caso):
        return rg.correr_decision(caso, self.p, self.h, self.c)

    def test_d1_externo_automatico(self):
        caso = {"id": "D1d", "titulo": "x", "nivel": "decision",
                "alerta": {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "ssh",
                           "familia": "acceso_credenciales", "regla_id": "5763"},
                "esperado": {"clase": "vp_intento_acceso", "requiere_humano": False, "accion_final": "BLOQUEAR_IP"}}
        self.assertEqual(self._correr(caso)["resultado"], "OK")

    def test_a3_gestion_es_veto(self):
        caso = {"id": "A3d", "titulo": "x", "nivel": "decision",
                "alerta": {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh",
                           "familia": "acceso_credenciales", "regla_id": "5763"},
                "esperado": {"requiere_humano": True, "accion_final": None}}
        self.assertEqual(self._correr(caso)["resultado"], "OK")

    def test_detecta_diferencia(self):
        caso = {"id": "Xd", "titulo": "x", "nivel": "decision",
                "alerta": {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "ssh",
                           "familia": "acceso_credenciales", "regla_id": "5763"},
                "esperado": {"requiere_humano": True}}   # es automatico, no humano
        r = self._correr(caso)
        self.assertEqual(r["resultado"], "FALLO")
        self.assertIn("requiere_humano", r["detalle"][0])
```

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_pruebas -k NivelDecision` → FALLA.

- [ ] **Step 2: Implementar `correr_decision` y el despacho por nivel**

En `pruebas.py`:

```python
def _comparar_decision(esperado, traza):
    """Diferencias entre lo esperado y la traza de triaje.procesar (para nivel decision)."""
    from prototipo import validacion
    obs = {"clase": traza.get("clase"), "confianza": traza.get("confianza"),
           "accion_final": traza.get("accion_final"), "requiere_humano": traza.get("requiere_humano"),
           "filtro": validacion.filtro_legible(traza),
           "prediccion_cascada": (traza.get("impacto_determinado") or {}).get("activos_afectados_en_cascada")}
    return [f"{k}: esperado {esperado[k]!r}, obtenido {obs[k]!r}"
            for k in obs if k in esperado and obs[k] != esperado[k]]


def correr_decision(caso, perfil, hallazgos, catalogo):
    import time
    from prototipo import triaje, rafaga
    t0 = time.time()
    a = dict(caso["alerta"]); a.setdefault("timestamp", "2026-09-22T00:00:00Z"); a.setdefault("mitre", [])
    a.setdefault("id_alerta", caso["id"])
    if "rafaga_60s" in caso:
        a[rafaga.CAMPO] = caso["rafaga_60s"]
    traza = triaje.procesar(a, hallazgos, perfil, "bancario", catalogo, id_decision=caso["id"],
                            timestamp=a["timestamp"])
    fallos = _comparar_decision(caso["esperado"], traza)
    resultado, detalle = veredicto_caso(caso["esperado"], fallos)
    return {"id": caso["id"], "titulo": caso["titulo"], "resultado": resultado, "detalle": detalle,
            "segundos": round(time.time() - t0, 2)}
```

En `correr_caso`, al principio (tras la comprobación de `requiere`), despacha:

```python
    if caso["nivel"] == "decision":
        return correr_decision(caso, perfil, hallazgos, catalogo)
```

(Para eso `correr_caso` ya recibe `perfil, hallazgos, catalogo`; confírmalo en su firma y en `main`.)

- [ ] **Step 3: Añadir los casos de decisión a `casos.py`**

Añade a `CASOS` (usa las IPs del banco; `familia acceso_credenciales` salvo donde se indique). El origen externo genérico es `203.0.113.9`; `10.100.0.10` es la gestión; `10.100.0.20` el auditor (ambos legítimos declarados en el perfil).

```python
    _dec("D2", "Servicio no expuesto según el auditor -> FP exposición inexistente",
         {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "rdp", "regla_id": "5763"},
         {"clase": "fp_exposicion_inexistente", "accion_final": None}),
    _dec("D3", "Origen legítimo (gestión) -> FP actividad legítima",
         {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"clase": "fp_actividad_legitima", "accion_final": None, "requiere_humano": True}),
    _dec("D4", "Ráfaga desde origen legítimo -> VP conf 0.6, humano",
         {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"clase": "vp_intento_acceso", "confianza": 0.6, "requiere_humano": True}, rafaga=12),
    _dec("D6", "Familia no soportada -> no_soportada",
         {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "desconocido",
          "familia": "plataforma", "regla_id": "502"},
         {"clase": "no_soportada", "accion_final": None}),
    _dec("A2", "Origen aparente = un cortafuegos -> retenida, alcanza_servicio",
         {"origen_ip": "10.0.0.1", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "accion_final": "BLOQUEAR_IP"}),
    _dec("A3", "Origen aparente = la gestión -> veto duro",
         {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "accion_final": None}, rafaga=12),
    _dec("A4", "IP interna no inventariada -> activo interno, humano",
         {"origen_ip": "10.77.3.9", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "accion_final": "BLOQUEAR_IP"}),
    _dec("K5", "Ataque desde taquilla (nadie depende de ella) -> humano, sin cascada",
         {"origen_ip": "10.200.0.10", "activo": "web-banking", "servicio": "ssh", "regla_id": "5763"},
         {"requiere_humano": True, "prediccion_cascada": []}),
```

y el helper al principio de `casos.py`:

```python
def _dec(id_, titulo, alerta, esperado, rafaga=None):
    a = {"familia": "acceso_credenciales", **alerta}
    c = {"id": id_, "titulo": titulo, "nivel": "decision", "alerta": a, "esperado": esperado}
    if rafaga is not None:
        c["rafaga_60s"] = rafaga
    return c
```

**Nota para el ejecutor:** los valores esperados de arriba son la intención de diseño; si al correr el caso el prototipo decide otra cosa, NO ajustes el prototipo. Comprueba con la tabla de `bancario.yml` (origenes_legitimos, rafaga.umbral, continuidad) si el esperado estaba mal (corrígelo en `casos.py`) o si es un hallazgo real (déjalo como FALLO y anótalo en el informe/estado). Registra la decisión en el ledger.

- [ ] **Step 4: Verificar (sin lab)**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_pruebas -k NivelDecision` → `OK`.
Run: `PYTHONPATH=. python3 -c "
from lab.banco import pruebas, casos
import os, json
from prototipo import perfil, catalogo
p=perfil.cargar(os.path.join(pruebas.RAIZ,'prototipo/perfiles/bancario.yml'))
c=catalogo.cargar_catalogo(os.path.join(pruebas.RAIZ,'prototipo/catalogo.yml'))
h=json.load(open(pruebas.HALLAZGOS,encoding='utf-8'))
for caso in casos.CASOS:
    if caso['nivel']=='decision':
        r=pruebas.correr_decision(caso,p,h,c); print(r['id'],r['resultado'],r['detalle'])
"`
Anota cualquier FALLO y decídelo según la nota del Step 3 antes del commit.

- [ ] **Step 5: Commit**

```bash
git add lab/banco/pruebas.py lab/banco/casos.py lab/banco/tests/test_pruebas.py
git commit -m "feat(banco): casos de nivel decision (clasificacion y filtro sin laboratorio)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Nivel `inyectada` y `perfil` — filtro y cascada sin laboratorio

**Files:**
- Modify: `lab/banco/pruebas.py` (`correr_inyectada`, `correr_perfil`, despacho)
- Modify: `lab/banco/casos.py` (casos C1, C2, C3, K2, K3, A5, C5, K4)
- Test: `lab/banco/tests/test_pruebas.py`

**Interfaces:**
- Consumes: `perfil.filtrar`, `impacto.determinar`, `impacto.afectados_en_cascada`.
- Produces: `pruebas.correr_inyectada(caso, perfil, catalogo)` y `pruebas.correr_perfil(caso, perfil, catalogo)`. Un caso `nivel: inyectada` declara `accion` (id del catálogo), `params` (dict), `activo`, `servicio`, `confianza`, y `esperado` con claves entre `filtro_resultado` (`permite`/`degrada`/`veta`/`sin_accion`), `accion_final`, `requiere_humano`, `prediccion_cascada`. Un caso `nivel: perfil` declara `comprobacion` (`"sin_reversion"` o `"ciclo_depende_de"`) con su `activo`/`accion` y `esperado`.

- [ ] **Step 1: Tests (fallan primero)**

```python
class TestNivelInyectadaPerfil(unittest.TestCase):
    def setUp(self):
        import os
        from prototipo import perfil, catalogo
        self.p = perfil.cargar(os.path.join(rg.RAIZ, "prototipo/perfiles/bancario.yml"))
        self.c = catalogo.cargar_catalogo(os.path.join(rg.RAIZ, "prototipo/catalogo.yml"))

    def test_c1_bloquear_puerto_core_db_degrada(self):
        caso = {"id": "C1", "titulo": "x", "nivel": "inyectada", "accion": "BLOQUEAR_PUERTO",
                "params": {"puerto": 1521, "ip": "203.0.113.9"}, "activo": "core-db", "servicio": "sql",
                "confianza": 0.99, "esperado": {"filtro_resultado": "degrada", "accion_final": "BLOQUEAR_IP"}}
        self.assertEqual(rg.correr_inyectada(caso, self.p, self.c)["resultado"], "OK")

    def test_k2_aislar_core_db_predice_cascada(self):
        caso = {"id": "K2", "titulo": "x", "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {},
                "activo": "core-db", "servicio": "sql", "confianza": 0.99,
                "esperado": {"requiere_humano": True,
                             "prediccion_cascada": ["api-movil", "middleware", "web-banking"]}}
        self.assertEqual(rg.correr_inyectada(caso, self.p, self.c)["resultado"], "OK")

    def test_c5_sin_reversion_es_veto(self):
        caso = {"id": "C5", "titulo": "x", "nivel": "perfil",
                "comprobacion": "sin_reversion", "accion": "OBS_PROCESOS", "activo": "core-db",
                "esperado": {"filtro_resultado": "veta"}}
        self.assertEqual(rg.correr_perfil(caso, self.p, self.c)["resultado"], "OK")

    def test_k4_ciclo_termina(self):
        caso = {"id": "K4", "titulo": "x", "nivel": "perfil", "comprobacion": "ciclo_depende_de",
                "activo": "core-db", "esperado": {"termina": True}}
        self.assertEqual(rg.correr_perfil(caso, self.p, self.c)["resultado"], "OK")
```

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_pruebas -k NivelInyectadaPerfil` → FALLA.

- [ ] **Step 2: Implementar los dos ejecutores**

En `pruebas.py`:

```python
def correr_inyectada(caso, perfil, catalogo):
    import time
    from prototipo import perfil as perfilm
    t0 = time.time()
    filtro = perfilm.filtrar(perfil, caso["accion"], caso.get("params", {}), catalogo,
                             caso["activo"], caso.get("servicio"), caso.get("confianza", 1.0))
    esp = caso["esperado"]
    obs = {"filtro_resultado": filtro["resultado"], "accion_final": filtro["accion_final"],
           "requiere_humano": filtro["requiere_humano"],
           "prediccion_cascada": (filtro.get("impacto") or {}).get("activos_afectados_en_cascada")}
    fallos = [f"{k}: esperado {esp[k]!r}, obtenido {obs[k]!r}" for k in obs if k in esp and obs[k] != esp[k]]
    resultado, detalle = veredicto_caso(esp, fallos)
    return {"id": caso["id"], "titulo": caso["titulo"], "resultado": resultado, "detalle": detalle,
            "segundos": round(time.time() - t0, 2)}


def correr_perfil(caso, perfil, catalogo):
    import time
    from prototipo import perfil as perfilm, impacto
    t0 = time.time()
    esp, fallos = caso["esperado"], []
    if caso["comprobacion"] == "sin_reversion":
        filtro = perfilm.filtrar(perfil, caso["accion"], caso.get("params", {}), catalogo,
                                 caso["activo"], caso.get("servicio"), 1.0)
        if "filtro_resultado" in esp and filtro["resultado"] != esp["filtro_resultado"]:
            fallos.append(f"filtro_resultado: esperado {esp['filtro_resultado']!r}, obtenido {filtro['resultado']!r}")
    elif caso["comprobacion"] == "ciclo_depende_de":
        try:
            impacto.afectados_en_cascada(caso["activo"], perfil)   # no debe colgarse (guardia de ciclos)
            termino = True
        except RecursionError:
            termino = False
        if esp.get("termina") and not termino:
            fallos.append("afectados_en_cascada no terminó (posible ciclo sin guardia)")
    resultado, detalle = veredicto_caso(esp, fallos)
    return {"id": caso["id"], "titulo": caso["titulo"], "resultado": resultado, "detalle": detalle,
            "segundos": round(time.time() - t0, 2)}
```

En `correr_caso`, amplía el despacho:

```python
    if caso["nivel"] == "decision":
        return correr_decision(caso, perfil, hallazgos, catalogo)
    if caso["nivel"] == "inyectada":
        return correr_inyectada(caso, perfil, catalogo)
    if caso["nivel"] == "perfil":
        return correr_perfil(caso, perfil, catalogo)
```

- [ ] **Step 3: Añadir los casos a `casos.py`**

```python
    {"id": "C1", "titulo": "BLOQUEAR_PUERTO 1521 en core-db (excepción nunca_automatica) -> degrada a BLOQUEAR_IP",
     "nivel": "inyectada", "accion": "BLOQUEAR_PUERTO", "params": {"puerto": 1521, "ip": "203.0.113.9"},
     "activo": "core-db", "servicio": "sql", "confianza": 0.99,
     "esperado": {"filtro_resultado": "degrada", "accion_final": "BLOQUEAR_IP"}},
    {"id": "C2", "titulo": "BLOQUEAR_PUERTO 8443 en middleware -> degrada a BLOQUEAR_IP",
     "nivel": "inyectada", "accion": "BLOQUEAR_PUERTO", "params": {"puerto": 8443, "ip": "203.0.113.9"},
     "activo": "middleware", "servicio": "https", "confianza": 0.99,
     "esperado": {"filtro_resultado": "degrada", "accion_final": "BLOQUEAR_IP"}},
    {"id": "C3", "titulo": "AISLAR_NODO de web-banking (alcanza servicio) -> humano",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {}, "activo": "web-banking",
     "servicio": "https", "confianza": 0.99, "esperado": {"requiere_humano": True}},
    {"id": "K2", "titulo": "AISLAR_NODO de core-db -> predice la cascada transitiva",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {}, "activo": "core-db",
     "servicio": "sql", "confianza": 0.99,
     "esperado": {"requiere_humano": True, "prediccion_cascada": ["api-movil", "middleware", "web-banking"]}},
    {"id": "K3", "titulo": "AISLAR_NODO de middleware -> la cascada NO incluye atm (dependencia no declarada)",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {}, "activo": "middleware",
     "servicio": "https", "confianza": 0.99,
     "esperado": {"prediccion_cascada": ["api-movil", "web-banking"]}},
    {"id": "A5", "titulo": "AISLAR_NODO del nodo de gestión (mdr-siem) -> veto duro",
     "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {"ip_nodo": "10.100.0.10"},
     "activo": "mdr-siem", "servicio": "ssh", "confianza": 0.99,
     "esperado": {"filtro_resultado": "veta", "accion_final": None}},
    {"id": "C5", "titulo": "Acción sin reversión definida (OBS_PROCESOS) -> se veta como contención",
     "nivel": "perfil", "comprobacion": "sin_reversion", "accion": "OBS_PROCESOS", "activo": "core-db",
     "esperado": {"filtro_resultado": "veta"}},
    {"id": "K4", "titulo": "afectados_en_cascada termina aunque haya dependencias (guardia de ciclos)",
     "nivel": "perfil", "comprobacion": "ciclo_depende_de", "activo": "core-db", "esperado": {"termina": True}},
```

**Nota (K3, prediccion_cascada de K2):** el orden de `activos_afectados_en_cascada` es alfabético (`impacto.afectados_en_cascada` devuelve `sorted`). Verifica el valor exacto que sale y ajústalo en `casos.py` si difiere; una diferencia de *contenido* (no de orden) es un hallazgo, decídelo según la nota de la Task 3.
**Nota (C5):** confirma que `OBS_PROCESOS` existe en `catalogo.yml` con `reversion: no_aplica`; si `perfil.filtrar` sobre una acción de observación devuelve `permite` en vez de `veta` (porque no es contención), ajusta el caso: usa una acción de contención sin `reversion_cmd`, o cambia `esperado` y anota que las observaciones no se vetan. Es una comprobación de diseño, decídela con el código.
**Nota (A5):** requiere el arreglo de la Task 1 del plan 1 (actor en acciones sobre nodo); ya está en la rama.

- [ ] **Step 4: Verificar (sin lab)**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_pruebas -k NivelInyectadaPerfil` → `OK`.
Corre todos los casos `inyectada`/`perfil` como en el Step 4 de la Task 3 y decide cada FALLO.

- [ ] **Step 5: Commit**

```bash
git add lab/banco/pruebas.py lab/banco/casos.py lab/banco/tests/test_pruebas.py
git commit -m "feat(banco): casos de nivel inyectada y perfil (filtro, cascada, ciclos)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Informe por grupo y por alcance; `main` despacha todos los niveles

**Files:**
- Modify: `lab/banco/pruebas.py` (`informe`, `main`, `correr_caso`)
- Test: `lab/banco/tests/test_pruebas.py`

**Interfaces:**
- Produces: `pruebas.informe(resultados, cuando) -> str` con conteo por resultado y por nivel; `main` corre todos los casos (los `vivo` solo si el lab está y `--con-vivo`), escribe `informe.md` y `resultados.json`.
- Cada caso lleva `grupo` (la letra: D/C/K/A/E/O/X) derivada de su `id` (`caso["id"][0]`).

- [ ] **Step 1: Test del informe (falla primero)**

```python
class TestInforme(unittest.TestCase):
    def test_resume_por_resultado_y_nivel(self):
        res = [{"id": "D1", "titulo": "a", "resultado": "OK", "detalle": [], "segundos": 1, "nivel": "decision"},
               {"id": "K1", "titulo": "b", "resultado": "OK", "detalle": ["fallo conocido"], "segundos": 2, "nivel": "vivo"},
               {"id": "E6", "titulo": "c", "resultado": "OMITIDO", "detalle": ["requiere modelo"], "segundos": 0, "nivel": "vivo"}]
        txt = rg.informe(res, "2026-09-22 10:00")
        self.assertIn("2 OK", txt)
        self.assertIn("1 OMITIDO", txt)
        self.assertIn("decision", txt)
        self.assertIn("| D1 |", txt)
```

- [ ] **Step 2: Implementar**

Reemplaza `informe` por una versión que cuente por resultado y liste por nivel:

```python
def informe(resultados, cuando):
    from collections import Counter
    por_res = Counter(r["resultado"] for r in resultados)
    orden = ["OK", "FALLO", "BLOQUEADO", "OMITIDO"]
    cab = " · ".join(f"{por_res.get(k, 0)} {k}" for k in orden if por_res.get(k))
    lineas = [f"# Banco de pruebas del laboratorio del banco — {cuando}", "",
              f"**{cab}** de {len(resultados)} casos. Catálogo: `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md` §4.", "",
              "| Caso | Nivel | Resultado | Tiempo | Qué se comprobó / qué falló |", "|---|---|---|---|---|"]
    for r in resultados:
        detalle = "; ".join(r["detalle"]) if r["detalle"] else r["titulo"]
        lineas.append(f"| {r['id']} | {r.get('nivel','')} | {r['resultado']} | {r['segundos']} s | {detalle} |")
    lineas += ["", "**Notas:** K1 y C4 declaran `fallo_esperado` (fallos conocidos del prototipo): cuentan "
               "OK mientras el fallo persista. Los casos que requieren el modelo LLM (E6) salen OMITIDO: el "
               "banco corre con la plantilla determinista."]
    return "\n".join(lineas) + "\n"
```

En `main`, corre todos los casos pasando `nivel` al resultado y separando vivos:

```python
    resultados, ultimo_ataque = [], 0.0
    for caso in casos_a_correr:
        if caso["nivel"] == "vivo" and not con_vivo:
            resultados.append({"id": caso["id"], "titulo": caso["titulo"], "nivel": "vivo",
                               "resultado": "OMITIDO", "detalle": ["nivel vivo: usa --con-vivo con el banco levantado"],
                               "segundos": 0})
            continue
        if caso["nivel"] == "vivo" and caso.get("ataque"):
            espera = ESPERA_WAZUH - (time.time() - ultimo_ataque)
            if ultimo_ataque and espera > 0:
                print(f"   (esperando {int(espera)} s por la regla 5763)"); time.sleep(espera)
        print(f"== {caso['id']} [{caso['nivel']}]: {caso['titulo']}")
        r = correr_caso(caso, dir_salida, ejecutor, perfil, hallazgos, catalogo,
                        escribir=lambda s: print("   | " + s.replace(chr(10), chr(10)+"   | ")))
        r["nivel"] = caso["nivel"]
        if caso["nivel"] == "vivo" and caso.get("ataque"):
            ultimo_ataque = time.time()
        print(f"   -> {r['resultado']} ({r['segundos']} s)" + "".join(f"\n      - {d}" for d in r["detalle"]))
        resultados.append(r)
```

Añade a `argparse` la bandera `--con-vivo` (`action="store_true"`) y usa `con_vivo = a.con_vivo`. Sin `--con-vivo`, los casos `vivo` salen OMITIDO (así `--todos` corre sin lab en segundos). Con `--caso <id>` de un caso vivo, fuerza `con_vivo = True`.

Asegúrate de que `correr_caso` reciba `perfil, hallazgos, catalogo` y los pase a los `correr_*` de nivel; los `decision`/`inyectada`/`perfil` ignoran `dir_salida`/`ejecutor`.

- [ ] **Step 3: Verificar y correr la suite sin lab**

Run: `PYTHONPATH=. python3 -m unittest discover -s lab/banco/tests -t . 2>&1 | tail -1` → `OK`.
Run: `PYTHONPATH=. python3 -m lab.banco.pruebas` (sin `--con-vivo`) → corre decision+inyectada+perfil, los vivos OMITIDO; genera `informe.md`. Revisa que no haya FALLO inesperado; decide los que salgan.

- [ ] **Step 4: Commit**

```bash
git add lab/banco/pruebas.py lab/banco/tests/test_pruebas.py
git commit -m "feat(banco): informe por resultado y nivel; --con-vivo separa los casos de laboratorio

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Modos `--paso-a-paso` y `--guias`

**Files:**
- Modify: `lab/banco/pruebas.py` (`--paso-a-paso`, `--guias`, `guia_markdown`)
- Create: `docs/pruebas/banco/` (salida de `--guias`)
- Test: `lab/banco/tests/test_pruebas.py`

**Interfaces:**
- Produces: `pruebas.guia_markdown(caso) -> str` (una guía por caso desde su dict); `--guias` escribe `docs/pruebas/banco/<id>.md` para cada caso; `--paso-a-paso` corre un caso deteniéndose entre pasos y, para los `vivo`, deja que el analista conteste el menú real por `/dev/tty`.

- [ ] **Step 1: Test de `guia_markdown` (falla primero)**

```python
class TestGuias(unittest.TestCase):
    def test_guia_incluye_ataque_y_esperado(self):
        caso = {"id": "D1", "titulo": "Externo contra web-banking", "nivel": "vivo",
                "ataque": ("internet", "sshpass -p x ssh ... cliente@10.10.0.10 id"),
                "origen": "198.51.100.10", "esperado": {"accion_final": "BLOQUEAR_IP"},
                "deshacer": [("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP")]}
        g = rg.guia_markdown(caso)
        self.assertIn("# D1", g)
        self.assertIn("Externo contra web-banking", g)
        self.assertIn("sshpass", g)
        self.assertIn("iptables -D INPUT", g)

    def test_guia_de_caso_de_decision(self):
        caso = {"id": "A3", "titulo": "Gestión = veto", "nivel": "decision",
                "alerta": {"origen_ip": "10.100.0.10", "activo": "web-banking"},
                "esperado": {"accion_final": None}}
        g = rg.guia_markdown(caso)
        self.assertIn("nivel: decision", g)
        self.assertIn("10.100.0.10", g)
```

- [ ] **Step 2: Implementar `guia_markdown`, `--guias` y `--paso-a-paso`**

```python
def guia_markdown(caso):
    l = [f"# {caso['id']} · {caso['titulo']}", "", f"- **nivel:** {caso['nivel']}"]
    if caso.get("preparar"):
        l += ["", "## Preparar", "```bash"] + [f"docker exec clab-banco-{n} sh -c {cmd!r}" for n, cmd in caso["preparar"]] + ["```"]
    if caso.get("ataque"):
        origen, cmd = caso["ataque"]
        l += ["", f"## Atacar (desde {origen})", "```bash", f"docker exec clab-banco-{origen} sh -c {cmd!r}", "```"]
    if caso.get("alerta"):
        l += ["", "## Alerta (nivel decision)", "```json", json.dumps(caso["alerta"], ensure_ascii=False), "```"]
    l += ["", "## Esperado", "```json", json.dumps(caso["esperado"], ensure_ascii=False, indent=1), "```"]
    if caso.get("deshacer"):
        l += ["", "## Deshacer", "```bash"] + [f"docker exec clab-banco-{n} {cmd}" for n, cmd in caso["deshacer"]] + ["```"]
    return "\n".join(l) + "\n"


def generar_guias(destino):
    os.makedirs(destino, exist_ok=True)
    for caso in casos.CASOS:
        with open(os.path.join(destino, f"{caso['id']}.md"), "w", encoding="utf-8") as f:
            f.write(guia_markdown(caso))
    return len(casos.CASOS)
```

En `main`, antes de correr nada:

```python
    if a.guias:
        n = generar_guias(os.path.join(RAIZ, "docs", "pruebas", "banco"))
        print(f"{n} guías -> docs/pruebas/banco/"); return 0
```

Para `--paso-a-paso`, cuando se pasa con `--caso <id>`: corre ese caso con `con_vivo=True` y un lector interactivo (el `_leer_interactivo` de `stream`, que lee de `/dev/tty`) en vez del `Lector` guionizado, e imprime cada fase antes de ejecutarla (`estado base`, `preparar`, `atacar`, `esperando decisión`, `verificar`, `deshacer`). Implementa un `Lector` alternativo que delegue en `input`/tty; para el mínimo, en `--paso-a-paso` usa `leer=None` en `decidir` para que caiga a `input`. Añade las banderas `--guias` y `--paso-a-paso` a `argparse`; `--paso-a-paso` exige `--caso`.

- [ ] **Step 3: Verificar**

Run: `PYTHONPATH=. python3 -m unittest lab.banco.tests.test_pruebas -k Guias` → `OK`.
Run: `PYTHONPATH=. python3 -m lab.banco.pruebas --guias` → escribe `docs/pruebas/banco/*.md`; ábrelas y comprueba que se leen bien.

- [ ] **Step 4: Commit**

```bash
git add lab/banco/pruebas.py lab/banco/tests/test_pruebas.py docs/pruebas/banco/
git commit -m "feat(banco): modos --guias (guias por caso) y --paso-a-paso

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Corrida en vivo y el informe real

Sin código nuevo. Levanta el banco, corre la suite completa con `--con-vivo`, y guarda el informe como evidencia.

**Files:**
- Create: `lab/campañas/2026-09-22-banco-regresion/informe.md` y `resultados.json` (los genera la corrida)

- [ ] **Step 1: Estado base**

```bash
sh lab/lab.sh up banco 2>/dev/null || true      # si no está levantado
sh lab/banco/banco.sh aprovisionar
sh lab/banco/banco.sh test
```

Si `test` no da todo OK, resuelve el laboratorio (reglas sobrantes de pruebas previas, o `down`+`up`) antes de seguir.

- [ ] **Step 2: Corrida sin lab (rápida)**

Run: `PYTHONPATH=. python3 -m lab.banco.pruebas`
Expected: decision/inyectada/perfil en OK (o FALLOS ya decididos y anotados); los vivos OMITIDO. Revisa el `informe.md`.

- [ ] **Step 3: Corrida completa con lab**

Run: `PYTHONPATH=. python3 -m lab.banco.pruebas --con-vivo`
Toma varios minutos (espera de 60 s entre ataques). Esperado:
- CASCADA, D1, A1, K1, E1 y los demás vivos con su resultado;
- K1 en OK con «fallo conocido reproducido»;
- ningún BLOQUEADO (si aparece, el laboratorio no estaba limpio: arréglalo y repite).

Guarda el `informe.md` y `resultados.json` resultantes (van a `lab/campañas/<fecha>-banco-regresion/`). Si un caso vivo sale FALLO por un motivo de laboratorio (timing, Wazuh), ajusta el caso o su plazo y repite ese caso con `--caso <id> --con-vivo`; si es un hallazgo real del prototipo, déjalo y anótalo.

- [ ] **Step 4: Commit del informe**

```bash
git add lab/campañas/2026-09-22-banco-regresion/
git commit -m "test(banco): corrida completa del banco de pruebas (informe y resultados)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Documentación

**Files:**
- Modify: `lab/banco/README.md`, `docs/pruebas/08-laboratorio-banco.md`, `documentacion/00-general/estado-y-riesgos.md`

- [ ] **Step 1: README del banco**

Añade a `lab/banco/README.md`, en la sección «Qué hay», la fila del banco de pruebas, y sustituye la nota «El plan 2 … **no se construyó**» por una que diga que sí se construyó:

```markdown
## Banco de pruebas (plan 2)

    python3 -m lab.banco.pruebas              # catálogo sin laboratorio (decision/inyectada/perfil), segundos
    python3 -m lab.banco.pruebas --con-vivo   # además los casos de extremo a extremo (necesita el banco levantado)
    python3 -m lab.banco.pruebas --caso K1 --con-vivo
    python3 -m lab.banco.pruebas --guias      # genera docs/pruebas/banco/<caso>.md

Cada caso declara su **nivel**: `decision` (clasificación y filtro, llamando al motor sin lab),
`inyectada` (una acción entregada al filtro del perfil, sin lab), `perfil` (solo lógica del perfil) o
`vivo` (extremo a extremo por Wazuh y el conector). Resultados: **OK**, **FALLO**, **BLOQUEADO** (el
laboratorio no estaba limpio) y **OMITIDO** (falta un requisito, p. ej. el modelo). K1 y C4 se declaran
como fallos conocidos: cuentan OK mientras el fallo persista. Catálogo y diseño: spec §4 y §6.
```

Corrige la fila de la tabla y la línea «El plan 2 … no se construyó» en consecuencia (ahora apunta al banco de pruebas).

- [ ] **Step 2: Guía manual y estado**

- En `docs/pruebas/08-laboratorio-banco.md`, añade al final una sección corta «Prueba automática» que remita a `python3 -m lab.banco.pruebas --con-vivo` como la versión no manual de los mismos casos.
- En `documentacion/00-general/estado-y-riesgos.md`, en la fila «3 — Entorno de pruebas» (o donde ya se cite el laboratorio del banco), añade: «Banco de pruebas del catálogo (§4): `python3 -m lab.banco.pruebas` — casos de clasificación, filtro y cascada sin lab, más los de extremo a extremo con `--con-vivo`.»
- Actualiza el recuento de tests del prototipo/banco donde se cite, con el número que den las suites.

- [ ] **Step 3: Suites y commit**

Run: `for d in prototipo/tests evaluacion/tests lab/dataset/tests lab/banco/tests; do PYTHONPATH=. python3 -m unittest discover -s $d -t . 2>&1 | tail -1; done` → `OK` en las cuatro.

```bash
git add lab/banco/README.md docs/pruebas/08-laboratorio-banco.md documentacion/00-general/estado-y-riesgos.md README.md
git commit -m "docs(banco): documenta el banco de pruebas (plan 2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
