# Fase 6 — Evaluación del prototipo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un marco de evaluación (`evaluacion/`) que mide el motor de triaje contra el baseline de nivel-de-regla de Wazuh sobre la partición de evaluación, calcula las métricas de la Fase 4, y produce una tabla comparativa y un informe.

**Architecture:** Paquete `evaluacion/` de Python stdlib que **consume** el motor (`from prototipo import ...`) y el dataset sin modificarlos. Módulos aislados: `metricas` (funciones puras), `cargar` (dataset), `baseline` (nivel Wazuh), `prioridad` (ground truth de prioridad), `prediccion` (corre el motor), `anclaje` (corre el LLM 1B), `campana` (orquestador + CLI). Las tareas van de abajo hacia arriba por dependencias; el harness (1–7) se prueba con datos falsos, y la corrida real + el informe (8) se hacen al final.

**Tech Stack:** Python 3.14 del sistema, solo stdlib (`json`, `unittest`, `time`, `math`, `argparse`) + pyyaml. NO pip/venv/pytest. El LLM 1B se invoca por subprocess vía `prototipo.justificador_llm` (entorno conda ya instalado en 5C). Tests: `python3 -m unittest`.

**Spec:** [docs/superpowers/specs/2026-09-02-fase6-evaluacion-design.md](../specs/2026-09-02-fase6-evaluacion-design.md)

## Global Constraints

- **Solo stdlib + pyyaml en `evaluacion/`.** Tests con `unittest`, nunca pytest. Ejecutar desde la raíz del repo.
- **No se modifica `prototipo/` ni `lab/`.** El harness los consume; si algo faltara, se reporta, no se parchea aquí.
- **Alcance:** métricas principales sobre `particion == "evaluacion"` (205 alertas: 10 VP, 8 FP, 187 no_soportada). La partición completa es un anexo.
- **no_soportada = verdadero negativo.** Ground truth binario: `etiqueta == "VP"` → positivo (amenaza); `etiqueta in {"FP","no_soportada"}` → negativo.
- **Predicción binaria del prototipo:** `clase` empieza por `vp_` → amenaza. **Del baseline:** `nivel_wazuh >= umbral` → amenaza.
- **Denominador 0 → la métrica se reporta como la cadena `"n/d"`, nunca 0 silencioso.**
- **Honestidad de n:** toda métrica de clasificación se acompaña de los conteos crudos de la matriz. En evaluación las 18 soportadas son todas `objetivo-vuln/ssh` — la priorización es de señal casi nula y se reporta como indicativa.
- **Reproducibilidad (RNF-03):** el LLM corre a temp 0 (ya fijado en `generador_llama`); la campaña registra perfil, partición y versiones.
- **UTF-8**, `ensure_ascii=False`, textos en español. Commits en español terminados con: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Estructura de ficheros

```
evaluacion/
├── __init__.py
├── metricas.py          funciones puras de medición
├── cargar.py            carga y filtra el dataset por partición
├── baseline.py          nivel de Wazuh como clasificador + barrido de umbral
├── prioridad.py         carga la prioridad esperada (ground truth de priorización)
├── prioridad_esperada.yml   mapeo a mano (activo, etiqueta) → prioridad
├── prediccion.py        corre el motor por alerta, mapea traza→binario, cronometra
├── anclaje.py           corre el LLM 1B sobre las soportadas, cuenta anclaje
├── campana.py           orquestador + CLI (--particion, --sin-llm)
├── resultados/          (generado) campana-<fecha>.json + tabla.md
└── tests/
    ├── __init__.py
    ├── test_metricas.py
    ├── test_cargar.py
    ├── test_baseline.py
    ├── test_prioridad.py
    ├── test_prediccion.py
    ├── test_anclaje.py
    └── test_campana.py
```

Crear `evaluacion/__init__.py` y `evaluacion/tests/__init__.py` vacíos en la Tarea 1 (primer commit) para que `python3 -m unittest` y `from prototipo import ...` funcionen.

---

## Task 1: `metricas.py` — las funciones puras de medición

**Files:**
- Create: `evaluacion/__init__.py` (vacío), `evaluacion/tests/__init__.py` (vacío), `evaluacion/metricas.py`
- Test: `evaluacion/tests/test_metricas.py`

**Interfaces:**
- Produces:
  - `matriz(pred, verdad) -> dict` con claves `"vp","fp","vn","fn"` (pred y verdad son listas de bool de igual longitud; True = positivo/amenaza).
  - `precision(m) -> float | "n/d"`, `recall(m) -> float | "n/d"`, `f1(m) -> float | "n/d"`, `tasa_fp(m) -> float | "n/d"` (m es una matriz).
  - `acierto_prioridad(pred_prio, esp_prio) -> float | "n/d"` — % de pares dentro de ±1 (listas de int de igual longitud).
  - `spearman(a, b) -> float | "n/d"` — correlación de rangos (listas numéricas de igual longitud; "n/d" si n<2 o varianza 0).
  - `cobertura(clases) -> float` — % de clases distintas de `"no_soportada"`.
  - `tasa(bools) -> float` — % de True en una lista (para escalado).
  - `continuidad(registros) -> dict` con `"disruptivas_indebidas"` (int) y `"retencion_correcta"` (float | "n/d") — cada registro es `{"impacto","etiqueta","requiere_humano"}`.

- [ ] **Step 1: Escribir el test que falla**

```python
# evaluacion/tests/test_metricas.py
import unittest
from evaluacion import metricas as m

class TestClasificacion(unittest.TestCase):
    def test_matriz_y_derivadas(self):
        # 8 VP, 2 FP, 180 VN, 2 FN
        pred  = [True]*8 + [True]*2 + [False]*180 + [False]*2
        verd  = [True]*8 + [False]*2 + [False]*180 + [True]*2
        mat = m.matriz(pred, verd)
        self.assertEqual(mat, {"vp":8,"fp":2,"vn":180,"fn":2})
        self.assertAlmostEqual(m.precision(mat), 8/10)
        self.assertAlmostEqual(m.recall(mat), 8/10)
        self.assertAlmostEqual(m.f1(mat), 2*(0.8*0.8)/(0.8+0.8))
        self.assertAlmostEqual(m.tasa_fp(mat), 2/182)

    def test_denominador_cero_es_nd(self):
        mat = {"vp":0,"fp":0,"vn":5,"fn":0}
        self.assertEqual(m.precision(mat), "n/d")   # 0/(0+0)
        self.assertEqual(m.recall(mat), "n/d")

class TestOperacion(unittest.TestCase):
    def test_cobertura_y_tasa(self):
        self.assertAlmostEqual(m.cobertura(["vp_intento_acceso","no_soportada","fp_x"]), 2/3)
        self.assertAlmostEqual(m.tasa([True, False, True, True]), 3/4)

    def test_prioridad_pm1(self):
        self.assertAlmostEqual(m.acierto_prioridad([4,3,1],[4,4,2]), 1.0)  # todos dentro de ±1
        self.assertAlmostEqual(m.acierto_prioridad([4,1],[4,4]), 1/2)      # el segundo se pasa

    def test_spearman(self):
        self.assertAlmostEqual(m.spearman([1,2,3],[1,2,3]), 1.0)
        self.assertAlmostEqual(m.spearman([1,2,3],[3,2,1]), -1.0)
        self.assertEqual(m.spearman([5],[5]), "n/d")

class TestContinuidad(unittest.TestCase):
    def test_disruptiva_sobre_fp_y_retencion(self):
        regs = [
            {"impacto":"alcanza_servicio","etiqueta":"FP","requiere_humano":True},   # disruptiva indebida, retenida
            {"impacto":"alcanza_servicio","etiqueta":"FP","requiere_humano":False},  # disruptiva indebida, NO retenida
            {"impacto":"localizado","etiqueta":"FP","requiere_humano":True},         # no disruptiva
            {"impacto":"alcanza_servicio","etiqueta":"VP","requiere_humano":False},  # sobre VP, no cuenta
        ]
        r = m.continuidad(regs)
        self.assertEqual(r["disruptivas_indebidas"], 2)
        self.assertAlmostEqual(r["retencion_correcta"], 1/2)
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest evaluacion.tests.test_metricas -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# evaluacion/metricas.py
"""Funciones puras de medición para la Fase 6. No conocen el motor ni Wazuh."""
import math

def _div(a, b):
    return a / b if b else "n/d"

def matriz(pred, verdad):
    vp = fp = vn = fn = 0
    for p, v in zip(pred, verdad):
        if p and v: vp += 1
        elif p and not v: fp += 1
        elif not p and not v: vn += 1
        else: fn += 1
    return {"vp": vp, "fp": fp, "vn": vn, "fn": fn}

def precision(m): return _div(m["vp"], m["vp"] + m["fp"])
def recall(m):    return _div(m["vp"], m["vp"] + m["fn"])
def tasa_fp(m):   return _div(m["fp"], m["fp"] + m["vn"])

def f1(m):
    p, r = precision(m), recall(m)
    if p == "n/d" or r == "n/d" or (p + r) == 0:
        return "n/d"
    return 2 * p * r / (p + r)

def cobertura(clases):
    if not clases: return 0.0
    return sum(1 for c in clases if c != "no_soportada") / len(clases)

def tasa(bools):
    if not bools: return 0.0
    return sum(1 for b in bools if b) / len(bools)

def acierto_prioridad(pred_prio, esp_prio):
    if not pred_prio: return "n/d"
    return sum(1 for p, e in zip(pred_prio, esp_prio) if abs(p - e) <= 1) / len(pred_prio)

def _rangos(xs):
    orden = sorted(range(len(xs)), key=lambda i: xs[i])
    rang = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[orden[j + 1]] == xs[orden[i]]:
            j += 1
        promedio = (i + j) / 2 + 1  # rango 1-based, promediado en empates
        for k in range(i, j + 1):
            rang[orden[k]] = promedio
        i = j + 1
    return rang

def spearman(a, b):
    n = len(a)
    if n < 2: return "n/d"
    ra, rb = _rangos(a), _rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = math.sqrt(sum((ra[i] - ma) ** 2 for i in range(n)))
    db = math.sqrt(sum((rb[i] - mb) ** 2 for i in range(n)))
    if da == 0 or db == 0: return "n/d"
    return num / (da * db)

def continuidad(registros):
    disruptivas = [r for r in registros
                   if r["impacto"] == "alcanza_servicio" and r["etiqueta"] == "FP"]
    retenidas = sum(1 for r in disruptivas if r["requiere_humano"])
    return {"disruptivas_indebidas": len(disruptivas),
            "retencion_correcta": _div(retenidas, len(disruptivas))}
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest evaluacion.tests.test_metricas -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evaluacion/__init__.py evaluacion/metricas.py evaluacion/tests/
git commit -m "Metricas puras de la Fase 6: confusion, F1, tasa-FP, prioridad, spearman, continuidad

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `cargar.py` — carga y filtro del dataset

**Files:**
- Create: `evaluacion/cargar.py`
- Test: `evaluacion/tests/test_cargar.py`

**Interfaces:**
- Produces: `cargar(ruta, particion="evaluacion") -> list[dict]` — lee el JSONL, devuelve las filas cuya `particion` coincide (o todas si `particion is None`). Cada fila es el dict crudo: sirve a la vez como ground truth (`etiqueta`, `nivel_wazuh`) y como alerta para el motor (`familia`, `activo`, `servicio`, `mitre`, `origen_ip`, `regla_id`, `timestamp`, `id_alerta`).

- [ ] **Step 1: Escribir el test que falla**

```python
# evaluacion/tests/test_cargar.py
import os, json, tempfile, unittest
from evaluacion import cargar

FILAS = [
    {"id_alerta":"1","particion":"evaluacion","etiqueta":"VP","nivel_wazuh":10,"familia":"acceso_credenciales"},
    {"id_alerta":"2","particion":"entrenamiento","etiqueta":"FP","nivel_wazuh":5,"familia":"acceso_credenciales"},
    {"id_alerta":"3","particion":"evaluacion","etiqueta":"no_soportada","nivel_wazuh":3,"familia":"plataforma"},
]

class TestCargar(unittest.TestCase):
    def setUp(self):
        fd, self.ruta = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for r in FILAS:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def tearDown(self):
        os.remove(self.ruta)

    def test_filtra_por_particion(self):
        filas = cargar.cargar(self.ruta, "evaluacion")
        self.assertEqual({f["id_alerta"] for f in filas}, {"1", "3"})

    def test_particion_none_devuelve_todas(self):
        self.assertEqual(len(cargar.cargar(self.ruta, None)), 3)

    def test_conserva_ground_truth(self):
        f = cargar.cargar(self.ruta, "evaluacion")[0]
        self.assertIn("etiqueta", f)
        self.assertIn("nivel_wazuh", f)
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest evaluacion.tests.test_cargar -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# evaluacion/cargar.py
"""Carga el dataset etiquetado y lo filtra por partición."""
import json

RUTA_DATASET = "lab/dataset/etiquetado.jsonl"

def cargar(ruta=RUTA_DATASET, particion="evaluacion"):
    filas = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            fila = json.loads(linea)
            if particion is None or fila.get("particion") == particion:
                filas.append(fila)
    return filas
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest evaluacion.tests.test_cargar -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evaluacion/cargar.py evaluacion/tests/test_cargar.py
git commit -m "Carga del dataset de evaluacion filtrada por particion

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `baseline.py` — el nivel de Wazuh como clasificador

**Files:**
- Create: `evaluacion/baseline.py`
- Test: `evaluacion/tests/test_baseline.py`

**Interfaces:**
- Consumes: `metricas.matriz`, `metricas.f1`.
- Produces:
  - `predecir(nivel, umbral) -> bool` — `nivel >= umbral`.
  - `verdad_binaria(filas) -> list[bool]` — `etiqueta == "VP"` por fila.
  - `barrido(filas, rango=range(3, 13)) -> dict` con `"puntos"` (lista de `{"umbral","matriz","f1"}`) y `"optimo"` (el punto de mayor F1; empate → menor umbral).

- [ ] **Step 1: Escribir el test que falla**

```python
# evaluacion/tests/test_baseline.py
import unittest
from evaluacion import baseline

FILAS = [
    {"etiqueta":"VP","nivel_wazuh":10}, {"etiqueta":"VP","nivel_wazuh":10},
    {"etiqueta":"FP","nivel_wazuh":5},  {"etiqueta":"no_soportada","nivel_wazuh":3},
]

class TestBaseline(unittest.TestCase):
    def test_predecir_umbral(self):
        self.assertTrue(baseline.predecir(10, 10))
        self.assertFalse(baseline.predecir(9, 10))

    def test_verdad_binaria(self):
        self.assertEqual(baseline.verdad_binaria(FILAS), [True, True, False, False])

    def test_barrido_tiene_un_punto_por_umbral_y_optimo(self):
        r = baseline.barrido(FILAS, range(3, 13))
        self.assertEqual(len(r["puntos"]), 10)
        # umbral 10: predice amenaza solo los dos nivel-10 (ambos VP) -> F1 perfecto
        self.assertEqual(r["optimo"]["umbral"], 10)
        self.assertEqual(r["optimo"]["matriz"], {"vp":2,"fp":0,"vn":2,"fn":0})
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest evaluacion.tests.test_baseline -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# evaluacion/baseline.py
"""El nivel de regla de Wazuh binarizado como clasificador VP/FP, con barrido de umbral."""
from evaluacion import metricas

def predecir(nivel, umbral):
    return nivel >= umbral

def verdad_binaria(filas):
    return [f["etiqueta"] == "VP" for f in filas]

def barrido(filas, rango=range(3, 13)):
    verd = verdad_binaria(filas)
    puntos = []
    for t in rango:
        pred = [predecir(f["nivel_wazuh"], t) for f in filas]
        mat = metricas.matriz(pred, verd)
        puntos.append({"umbral": t, "matriz": mat, "f1": metricas.f1(mat)})
    def clave(p):
        f1 = p["f1"]
        return (f1 if isinstance(f1, (int, float)) else -1.0, -p["umbral"])
    optimo = max(puntos, key=clave)
    return {"puntos": puntos, "optimo": optimo}
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest evaluacion.tests.test_baseline -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evaluacion/baseline.py evaluacion/tests/test_baseline.py
git commit -m "Baseline: nivel de Wazuh como clasificador con barrido de umbral y punto optimo

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `prioridad.py` + `prioridad_esperada.yml` — ground truth de priorización

**Files:**
- Create: `evaluacion/prioridad_esperada.yml`, `evaluacion/prioridad.py`
- Test: `evaluacion/tests/test_prioridad.py`

**Interfaces:**
- Produces:
  - `cargar_esperada(ruta) -> dict` — carga el YAML `{activo: {etiqueta: prioridad}}`.
  - `esperada(activo, etiqueta, tabla) -> int | None` — la prioridad esperada, o `None` si no está mapeada.

**Contexto:** en evaluación **todas** las alertas soportadas son `objetivo-vuln/ssh`. El mapeo es minúsculo y va con su justificación en comentarios. La priorización se reporta como indicativa (n casi nulo).

- [ ] **Step 1: Crear el fichero de datos**

```yaml
# evaluacion/prioridad_esperada.yml
# Prioridad esperada por (activo, etiqueta). Fuente: la gravedad del nodo en
# lab/docs/vulnerabilidades-esperadas.md + la etiqueta como desempate.
# HONESTO: en la particion de evaluacion TODAS las alertas soportadas son
# objetivo-vuln/ssh, asi que este mapeo tiene una sola entrada util. Escala 1-4.
objetivo-vuln:
  VP: 4   # acceso real contra el objetivo vulnerable (Metasploitable, nodo critico) -> maxima
  FP: 1   # actividad del administrador legitimo -> minima
```

- [ ] **Step 2: Escribir el test que falla**

```python
# evaluacion/tests/test_prioridad.py
import os, unittest
from evaluacion import prioridad

RUTA = os.path.join(os.path.dirname(__file__), "..", "prioridad_esperada.yml")

class TestPrioridad(unittest.TestCase):
    def test_carga_y_consulta(self):
        tabla = prioridad.cargar_esperada(RUTA)
        self.assertEqual(prioridad.esperada("objetivo-vuln", "VP", tabla), 4)
        self.assertEqual(prioridad.esperada("objetivo-vuln", "FP", tabla), 1)

    def test_no_mapeado_es_none(self):
        tabla = prioridad.cargar_esperada(RUTA)
        self.assertIsNone(prioridad.esperada("nodo-desconocido", "VP", tabla))
```

- [ ] **Step 3: Verificar que falla**

Run: `python3 -m unittest evaluacion.tests.test_prioridad -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 4: Implementación**

```python
# evaluacion/prioridad.py
"""Ground truth de priorizacion: prioridad esperada por (activo, etiqueta)."""
import yaml

def cargar_esperada(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def esperada(activo, etiqueta, tabla):
    return tabla.get(activo, {}).get(etiqueta)
```

- [ ] **Step 5: Verificar que pasa**

Run: `python3 -m unittest evaluacion.tests.test_prioridad -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add evaluacion/prioridad.py evaluacion/prioridad_esperada.yml evaluacion/tests/test_prioridad.py
git commit -m "Ground truth de prioridad esperada (mapeo a mano, n casi nulo documentado)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `prediccion.py` — correr el motor y mapear la traza

**Files:**
- Create: `evaluacion/prediccion.py`
- Test: `evaluacion/tests/test_prediccion.py`

**Interfaces:**
- Consumes: `prototipo.triaje.procesar`, `prototipo.catalogo`, `prototipo.perfil`.
- Produces:
  - `es_amenaza(clase) -> bool` — `clase.startswith("vp_")`.
  - `predecir_todas(filas, hallazgos, perfil_dict, perfil_nombre, catalogo) -> list[dict]` — por cada fila corre `procesar` (justificador de plantilla, rápido), cronometra, y devuelve `{"id_alerta","clase","amenaza","prioridad","confianza","accion_final","impacto","requiere_humano","ms"}`.

**Contexto:** `procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo, id_decision, timestamp)` devuelve una traza con al menos `clase, prioridad, confianza, accion_final, impacto, requiere_humano`. La fila del dataset sirve como `alerta`. Se cronometra con `time.perf_counter`.

- [ ] **Step 1: Escribir el test que falla**

```python
# evaluacion/tests/test_prediccion.py
import unittest
from evaluacion import prediccion

class TestMapeo(unittest.TestCase):
    def test_es_amenaza(self):
        self.assertTrue(prediccion.es_amenaza("vp_intento_acceso"))
        self.assertTrue(prediccion.es_amenaza("vp_acceso_consumado"))
        self.assertFalse(prediccion.es_amenaza("fp_exposicion_inexistente"))
        self.assertFalse(prediccion.es_amenaza("no_soportada"))

class TestPredecirTodas(unittest.TestCase):
    def _procesar_falso(self, *a, **k):
        return {"clase":"vp_intento_acceso","prioridad":3,"confianza":0.5,
                "accion_final":"BLOQUEAR_IP","impacto":"localizado","requiere_humano":False}

    def test_predecir_todas_mapea_y_cronometra(self):
        filas = [{"id_alerta":"1","activo":"objetivo-vuln","servicio":"ssh",
                  "familia":"acceso_credenciales","timestamp":"t"}]
        res = prediccion.predecir_todas(filas, {}, {}, "prueba", None,
                                        _procesar=self._procesar_falso)
        self.assertEqual(len(res), 1)
        r = res[0]
        self.assertTrue(r["amenaza"])
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertIsInstance(r["ms"], float)
        self.assertGreaterEqual(r["ms"], 0.0)
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest evaluacion.tests.test_prediccion -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# evaluacion/prediccion.py
"""Corre el motor de triaje por alerta y mapea la traza a prediccion binaria + tiempo."""
import time
from prototipo import triaje

def es_amenaza(clase):
    return str(clase).startswith("vp_")

def predecir_todas(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, _procesar=triaje.procesar):
    res = []
    for i, fila in enumerate(filas):
        t0 = time.perf_counter()
        traza = _procesar(fila, hallazgos, perfil_dict, perfil_nombre, catalogo,
                          id_decision=f"e{i}", timestamp=fila.get("timestamp", ""))
        ms = (time.perf_counter() - t0) * 1000.0
        res.append({
            "id_alerta": fila.get("id_alerta"),
            "clase": traza.get("clase"),
            "amenaza": es_amenaza(traza.get("clase")),
            "prioridad": traza.get("prioridad"),
            "confianza": traza.get("confianza"),
            "accion_final": traza.get("accion_final"),
            "impacto": traza.get("impacto"),
            "requiere_humano": traza.get("requiere_humano"),
            "ms": ms,
        })
    return res
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest evaluacion.tests.test_prediccion -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evaluacion/prediccion.py evaluacion/tests/test_prediccion.py
git commit -m "Prediccion: corre el motor por alerta, mapea traza a binario y cronometra

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `anclaje.py` — el LLM 1B sobre las soportadas

**Files:**
- Create: `evaluacion/anclaje.py`
- Test: `evaluacion/tests/test_anclaje.py`

**Interfaces:**
- Consumes: `prototipo.analisis` (`enriquecer`, `clasificar`), `prototipo.justificador_llm` (`justificar_llm`, `generador_llama`).
- Produces:
  - `soportadas(filas) -> list[dict]` — las filas con `etiqueta in {"VP","FP"}`.
  - `medir(filas, hallazgos, perfil_dict, generador=generador_llama) -> list[dict]` — por cada fila soportada construye el contexto (`enriquecer`) y la clase (`clasificar`), llama `justificar_llm(fila, contexto, clase, generador)`, y devuelve `{"id_alerta","etiqueta","justificador","anclaje_verificado","texto"}`.
  - `resumen(resultados) -> dict` con `"llm_total"`, `"anclados"`, `"degradados"`, `"pct_anclaje"` (sobre los que usaron el LLM; "n/d" si ninguno).

- [ ] **Step 1: Escribir el test que falla**

```python
# evaluacion/tests/test_anclaje.py
import unittest
from evaluacion import anclaje

FILAS = [
    {"id_alerta":"1","etiqueta":"VP","activo":"objetivo-vuln","servicio":"ssh",
     "familia":"acceso_credenciales","origen_ip":"192.168.1.10","regla_id":"5763","mitre":["T1110"]},
    {"id_alerta":"2","etiqueta":"no_soportada","activo":"x","servicio":"y","familia":"plataforma"},
]

class TestAnclaje(unittest.TestCase):
    def test_soportadas(self):
        self.assertEqual([f["id_alerta"] for f in anclaje.soportadas(FILAS)], ["1"])

    def test_medir_con_generador_falso_anclado(self):
        gen = lambda prompt: "Fuerza bruta SSH desde 192.168.1.10 contra objetivo-vuln."
        res = anclaje.medir(FILAS, {}, {}, generador=gen)
        self.assertEqual(len(res), 1)          # solo la soportada
        self.assertEqual(res[0]["justificador"], "llm")
        self.assertTrue(res[0]["anclaje_verificado"])

    def test_resumen_cuenta_anclados(self):
        res = [{"justificador":"llm","anclaje_verificado":True},
               {"justificador":"plantilla","anclaje_verificado":True}]
        r = anclaje.resumen(res)
        self.assertEqual(r["llm_total"], 1)
        self.assertEqual(r["anclados"], 1)
        self.assertEqual(r["degradados"], 1)
        self.assertAlmostEqual(r["pct_anclaje"], 1.0)
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest evaluacion.tests.test_anclaje -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# evaluacion/anclaje.py
"""Corre el justificador LLM 1B sobre las alertas soportadas y mide el anclaje (RNF-02)."""
from prototipo import analisis
from prototipo import justificador_llm

def soportadas(filas):
    return [f for f in filas if f.get("etiqueta") in ("VP", "FP")]

def medir(filas, hallazgos, perfil_dict, generador=justificador_llm.generador_llama):
    res = []
    for fila in soportadas(filas):
        contexto = analisis.enriquecer(fila, hallazgos, perfil_dict)
        clase = analisis.clasificar(fila, contexto)["clase"]
        r = justificador_llm.justificar_llm(fila, contexto, clase, generador)
        res.append({"id_alerta": fila.get("id_alerta"), "etiqueta": fila.get("etiqueta"),
                    "justificador": r["justificador"], "anclaje_verificado": r["anclaje_verificado"],
                    "texto": r["texto"]})
    return res

def resumen(resultados):
    usaron_llm = [r for r in resultados if r["justificador"] == "llm"]
    anclados = sum(1 for r in usaron_llm if r["anclaje_verificado"])
    degradados = sum(1 for r in resultados if r["justificador"] == "plantilla")
    pct = anclados / len(usaron_llm) if usaron_llm else "n/d"
    return {"llm_total": len(usaron_llm), "anclados": anclados,
            "degradados": degradados, "pct_anclaje": pct}
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest evaluacion.tests.test_anclaje -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evaluacion/anclaje.py evaluacion/tests/test_anclaje.py
git commit -m "Anclaje: corre el LLM 1B sobre las soportadas y cuenta justificaciones ancladas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `campana.py` — orquestador y CLI

**Files:**
- Create: `evaluacion/campana.py`
- Test: `evaluacion/tests/test_campana.py`

**Interfaces:**
- Consumes: `cargar`, `prediccion`, `baseline`, `prioridad`, `anclaje`, `metricas`, `prototipo.catalogo`, `prototipo.perfil`.
- Produces:
  - `evaluar(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, tabla_prioridad, con_llm=True, generador=None) -> dict` — corre prototipo + baseline + todas las métricas + (si `con_llm`) anclaje, y devuelve un dict de resultados anidado (`clasificacion_prototipo`, `baseline`, `priorizacion`, `operacion`, `continuidad`, `anclaje`, `condiciones`).
  - `tabla_markdown(resultados) -> str` — la tabla comparativa prototipo vs baseline@óptimo.
  - `main(argv) -> int` — CLI: `--particion` (def. evaluacion), `--sin-llm`, `--perfil` (def. empresarial), `--salida-dir` (def. evaluacion/resultados). Escribe `campana-<fecha>.json` y `tabla.md`.

- [ ] **Step 1: Escribir el test que falla**

```python
# evaluacion/tests/test_campana.py
import unittest
from evaluacion import campana

FILAS = [
    {"id_alerta":"1","etiqueta":"VP","nivel_wazuh":10,"activo":"objetivo-vuln","servicio":"ssh",
     "familia":"acceso_credenciales","timestamp":"t","origen_ip":"192.168.1.10","regla_id":"5763","mitre":[]},
    {"id_alerta":"2","etiqueta":"FP","nivel_wazuh":10,"activo":"objetivo-vuln","servicio":"ssh",
     "familia":"acceso_credenciales","timestamp":"t","origen_ip":"192.168.1.1","regla_id":"5763","mitre":[]},
    {"id_alerta":"3","etiqueta":"no_soportada","nivel_wazuh":3,"activo":"x","servicio":"desconocido",
     "familia":"plataforma","timestamp":"t","origen_ip":None,"regla_id":"502","mitre":[]},
]

def _procesar_falso(fila, *a, **k):
    amenaza = fila["familia"] == "acceso_credenciales"
    return {"clase":"vp_intento_acceso" if amenaza else "no_soportada",
            "prioridad":3 if amenaza else 1,"confianza":1.0,
            "accion_final":"BLOQUEAR_IP" if amenaza else "NINGUNA",
            "impacto":"localizado","requiere_humano":False}

class TestCampana(unittest.TestCase):
    def test_evaluar_produce_las_secciones(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        for k in ("clasificacion_prototipo","baseline","priorizacion","operacion","continuidad","condiciones"):
            self.assertIn(k, res)
        # el prototipo marca las 2 soportadas como amenaza -> 1 VP, 1 FP
        self.assertEqual(res["clasificacion_prototipo"]["matriz"], {"vp":1,"fp":1,"vn":1,"fn":0})

    def test_tabla_markdown_menciona_ambos(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        md = campana.tabla_markdown(res)
        self.assertIn("Prototipo", md)
        self.assertIn("Baseline", md)
```

- [ ] **Step 2: Verificar que falla**

Run: `python3 -m unittest evaluacion.tests.test_campana -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implementación**

```python
# evaluacion/campana.py
"""Orquesta la campana de evaluacion: prototipo vs baseline, todas las metricas, y el informe."""
import argparse, json, os, datetime
from evaluacion import cargar, prediccion, baseline, prioridad, anclaje, metricas
from prototipo import catalogo as catm, perfil as perfilm, triaje, justificador_llm

def evaluar(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, tabla_prioridad,
            con_llm=True, generador=None, _procesar=triaje.procesar):
    verd = [f["etiqueta"] == "VP" for f in filas]
    preds = prediccion.predecir_todas(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, _procesar=_procesar)

    # Clasificacion del prototipo
    pred_bin = [p["amenaza"] for p in preds]
    mat = metricas.matriz(pred_bin, verd)
    clas_proto = {"matriz": mat, "precision": metricas.precision(mat), "recall": metricas.recall(mat),
                  "f1": metricas.f1(mat), "tasa_fp": metricas.tasa_fp(mat)}

    # Baseline por barrido
    base = baseline.barrido(filas)

    # Priorizacion (solo soportadas con prioridad esperada mapeada)
    pp, ep = [], []
    for f, p in zip(filas, preds):
        e = prioridad.esperada(f.get("activo"), f.get("etiqueta"), tabla_prioridad)
        if e is not None and f.get("etiqueta") in ("VP", "FP"):
            pp.append(p["prioridad"]); ep.append(e)
    prioriz = {"n": len(pp), "acierto_pm1": metricas.acierto_prioridad(pp, ep),
               "spearman": metricas.spearman(pp, ep)}

    # Operacion
    clases = [p["clase"] for p in preds]
    ms = [p["ms"] for p in preds]
    oper = {"cobertura": metricas.cobertura(clases),
            "tasa_escalado": metricas.tasa([p["requiere_humano"] for p in preds]),
            "ms_medio_clasificar": sum(ms) / len(ms) if ms else 0.0}

    # Continuidad
    regs = [{"impacto": p["impacto"], "etiqueta": f["etiqueta"], "requiere_humano": p["requiere_humano"]}
            for f, p in zip(filas, preds)]
    cont = metricas.continuidad(regs)

    resultados = {
        "clasificacion_prototipo": clas_proto,
        "baseline": {"optimo": base["optimo"], "puntos": base["puntos"]},
        "priorizacion": prioriz,
        "operacion": oper,
        "continuidad": cont,
        "condiciones": {"perfil": perfil_nombre, "n_alertas": len(filas),
                        "n_soportadas": sum(1 for f in filas if f["etiqueta"] in ("VP", "FP")),
                        "version_baseline": "baseline-0"},
    }
    if con_llm:
        gen = generador or justificador_llm.generador_llama
        anc = anclaje.medir(filas, hallazgos, perfil_dict, generador=gen)
        resultados["anclaje"] = {"resumen": anclaje.resumen(anc), "detalle": anc}
    return resultados

def _celda(v):
    if isinstance(v, float): return f"{v:.3f}"
    return str(v)

def tabla_markdown(resultados):
    c = resultados["clasificacion_prototipo"]
    b = resultados["baseline"]["optimo"]
    bm = b["matriz"]
    bp = metricas.precision(bm); br = metricas.recall(bm); bfp = metricas.tasa_fp(bm)
    filas = [
        ("Precision", _celda(c["precision"]), _celda(bp)),
        ("Recall", _celda(c["recall"]), _celda(br)),
        ("F1", _celda(c["f1"]), _celda(b["f1"])),
        ("Tasa de FP", _celda(c["tasa_fp"]), _celda(bfp)),
    ]
    out = [f"# Tabla comparativa — perfil {resultados['condiciones']['perfil']}",
           f"n = {resultados['condiciones']['n_alertas']} alertas "
           f"({resultados['condiciones']['n_soportadas']} soportadas)  ·  "
           f"baseline en su umbral optimo (nivel >= {b['umbral']})", "",
           "| Metrica | Prototipo | Baseline (Wazuh @optimo) |",
           "|---------|-----------|--------------------------|"]
    out += [f"| {n} | {p} | {q} |" for n, p, q in filas]
    out += ["", f"Matriz prototipo: {c['matriz']}", f"Matriz baseline: {bm}"]
    if "anclaje" in resultados:
        out += ["", f"Anclaje LLM (RNF-02): {resultados['anclaje']['resumen']}"]
    return "\n".join(out)

def main(argv):
    ap = argparse.ArgumentParser(description="Campana de evaluacion de la Fase 6")
    ap.add_argument("--particion", default="evaluacion")
    ap.add_argument("--perfil", default="empresarial")
    ap.add_argument("--sin-llm", action="store_true")
    ap.add_argument("--salida-dir", default="evaluacion/resultados")
    ap.add_argument("--hallazgos", default="lab/campañas/2026-08-31-evaluacion/hallazgos.json")
    a = ap.parse_args(argv[1:])

    filas = cargar.cargar(particion=(None if a.particion == "todas" else a.particion))
    with open(a.hallazgos, encoding="utf-8") as f:
        hallazgos = json.load(f)
    perfil_dict = perfilm.cargar(f"prototipo/perfiles/{a.perfil}.yml")
    catalogo = catm.cargar_catalogo("prototipo/catalogo.yml")
    tabla_prioridad = prioridad.cargar_esperada("evaluacion/prioridad_esperada.yml")

    resultados = evaluar(filas, hallazgos, perfil_dict, a.perfil, catalogo, tabla_prioridad,
                         con_llm=not a.sin_llm)

    os.makedirs(a.salida_dir, exist_ok=True)
    fecha = datetime.date.today().isoformat()
    ruta_json = os.path.join(a.salida_dir, f"campana-{fecha}.json")
    ruta_md = os.path.join(a.salida_dir, "tabla.md")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(tabla_markdown(resultados) + "\n")
    print(f"Resultados -> {ruta_json}\nTabla -> {ruta_md}")
    print("\n" + tabla_markdown(resultados))
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Verificar que pasa (y la batería completa del harness)**

Run: `python3 -m unittest discover -s evaluacion/tests -v`
Expected: PASS (todos los módulos 1–7 verdes con datos falsos)

- [ ] **Step 5: Commit**

```bash
git add evaluacion/campana.py evaluacion/tests/test_campana.py
git commit -m "Orquestador y CLI de la campana: prototipo vs baseline, tabla comparativa, --sin-llm

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Corrida real e informe de evaluación

**Files:**
- Create: `documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md`
- Modify: `documentacion/06-fase6-evaluacion-del-prototipo/README.md`
- Genera (no versionado obligatorio): `evaluacion/resultados/campana-<fecha>.json`, `evaluacion/resultados/tabla.md`

**Interfaces:** consume todo lo anterior + el modelo 1B y los datos reales (dataset y hallazgos de la campaña, ya en el repo).

- [ ] **Step 1: Corrida rápida sin LLM (validar el flujo end-to-end)**

Run: `python3 -m evaluacion.campana --particion evaluacion --sin-llm`
Expected: imprime la tabla comparativa y escribe `evaluacion/resultados/`. Anota los números (matriz del prototipo, baseline óptimo, priorización, operación, continuidad). Confirma que el prototipo marca las 18 soportadas como amenaza (recall alto, precisión < 1 porque no distingue el admin del atacante) — resultado esperado y honesto.

- [ ] **Step 2: Corrida completa con el LLM (anclaje real)**

Run: `python3 -m evaluacion.campana --particion evaluacion`
Expected: como el anterior + la sección de anclaje del 1B sobre las 18 soportadas (~4-5 min). Anota `pct_anclaje` y cuántas degradaron a plantilla. Si alguna degrada por timeout, es válido registrarlo (RNF-09); anota el tiempo real.

- [ ] **Step 3: Anexo — corrida sobre la partición completa**

Run: `python3 -m evaluacion.campana --particion todas --sin-llm --salida-dir evaluacion/resultados/anexo-completo`
Expected: los números de las 410; se comparan con los de evaluación para evidenciar que coinciden (sin entrenamiento no hay fuga).

- [ ] **Step 4: Batería completa**

Run: `python3 -m unittest discover -s evaluacion/tests`
Expected: OK.

- [ ] **Step 5: Redactar el informe**

Escribe `documentacion/06-.../informe-evaluacion.md` con los números REALES de los pasos 1–3:
la tabla comparativa prototipo vs baseline@óptimo (con conteos crudos), la curva del barrido del baseline,
las métricas de priorización/operación/continuidad, el anclaje del 1B, el **análisis de errores caso por
caso** (las 18 soportadas son un solo nodo; el baseline determinista no separa admin legítimo de atacante
→ precisión limitada; explicar qué señal faltaría), las **limitaciones** (n=18, una familia, encoder no
medible) y los **umbrales calibrados** que se devuelven a la Fase 5 (mapeo nivel→prioridad del barrido,
umbral de escalado — marcados provisionales). Incluye la lectura manual de utilidad sobre una muestra de
las justificaciones del 1B (útil/parcial/inútil). Enlaza a la spec y al doc de métricas de la Fase 4.

- [ ] **Step 6: Actualizar el README de la Fase 6**

En `documentacion/06-.../README.md`: pasar el estado de «No iniciada» a **hecha**, enlazar el informe, y
resumir el hallazgo principal en una línea (sin copiar la tabla — la convención del repo prohíbe duplicar
tablas normativas; el README enlaza, el informe tiene los números).

- [ ] **Step 7: Commit**

```bash
git add documentacion/06-fase6-evaluacion-del-prototipo/ evaluacion/resultados/
git commit -m "Cerrar la Fase 6: campana ejecutada, tabla comparativa e informe de evaluacion

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas de ejecución

- **Tareas 1–7 son Python puro** con datos/generadores falsos; no necesitan el modelo, el lab ni los datos reales. Batería: `python3 -m unittest discover -s evaluacion/tests`.
- **La Tarea 8 necesita el modelo 1B** (entorno conda de 5C) y los datos reales (dataset y `hallazgos.json`, ya en el repo). No hay laboratorio que levantar: los hallazgos ya están capturados en fichero.
- **Ejecutar todo desde la raíz del repo.**
- El paso lento es el anclaje con el 1B (~4-5 min sobre 18 alertas); `--sin-llm` lo salta para iterar.
