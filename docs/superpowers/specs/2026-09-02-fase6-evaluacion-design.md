# Diseño — Fase 6: Evaluación del prototipo

**Fecha:** 2026-09-02
**Fase:** 6 — Evaluación del prototipo
**Requisitos que ejercita:** RF-05/RNF-02 (calidad de justificación), RF-07 (umbral de escalado calibrado),
RF-09 (traza reproducible), RF-10 (cobertura), RF-20 (continuidad), RNF-03 (reproducibilidad), RNF-04 (latencia).
**Autoridad de qué medir:** [métricas-y-evaluacion.md](../../../documentacion/04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md) (Fase 4).

---

## 1. Objetivo y encuadre

Una sola pregunta: **¿el triaje asistido mejora sobre el nivel de regla de Wazuh, medido sobre el mismo
dataset y la misma partición?** El baseline es el método hoy en producción (clasificación por reglas y
firmas, sin IA). Un resultado negativo bien medido también es un hallazgo válido de la fase.

### Decisiones metodológicas fijadas (aprobadas antes de diseñar)

1. **Alcance:** las métricas principales se calculan sobre la **partición de evaluación (205 alertas:
   10 VP, 8 FP, 187 no_soportada)**. La partición completa (410) se reporta como **anexo** para
   evidenciar que los números coinciden — el clasificador es el baseline determinista y **no se
   entrenó**, así que no hay fuga train/test; aun así se respeta la partición porque el doc de métricas
   la exige y porque es la práctica honesta.
2. **Baseline:** el nivel de Wazuh (un entero) se binariza por **barrido de umbral** (`nivel ≥ t` para
   `t` en un rango), reportando la curva completa y el **punto óptimo por F1** — el baseline en su mejor
   versión, para que la comparación sea justa y no dependa de un umbral elegido a mano.
3. **no_soportada = verdaderos negativos:** una alerta de ruido de plataforma que el motor marca
   `no_soportada`/sin-acción cuenta como negativo correcto. Así la **tasa de FP** es medible y refleja
   la supresión de ruido, que es el valor del proyecto.
4. **Anclaje (RNF-02):** se corre el **modelo 1B real** sobre las **18 alertas soportadas** (VP+FP,
   ~4-5 min) para medir su anclaje; la plantilla (anclada por construcción) cubre el resto.

### Qué NO cubre la Fase 6

- El clasificador con fine-tuning (encoder) sigue **bloqueado** por el dataset de una sola familia; se
  evalúa el **baseline determinista** de 5A, y el desajuste encoder-sobre-prosa se documenta como
  limitación, no se mide (no hay encoder que medir).
- La utilidad de la justificación por revisión manual queda como una **muestra cualitativa** anotada en
  el informe, no automatizada.

---

## 2. Arquitectura del harness

Un paquete nuevo **`evaluacion/`** (hermano de `prototipo/` y `lab/`), **Python stdlib puro**, que
**consume** el motor sin modificarlo (`from prototipo import ...`) y el dataset (`lab/dataset/`). Se
ejecuta desde la raíz del repo. Unidades pequeñas, aisladas y con interfaz clara:

| Módulo | Responsabilidad | Depende de |
|--------|-----------------|-----------|
| `cargar.py` | Lee `lab/dataset/etiquetado.jsonl`, filtra por `particion`, devuelve una lista de `(fila, alerta)`: la `fila` conserva el ground truth (`etiqueta`, `nivel_wazuh`, `particion`) y `alerta` es el dict que consume el motor (la propia fila sirve: ya trae `regla_id`, `mitre`, `origen_ip`, `activo`, `servicio`, `familia`, `nivel_wazuh`, `evento_crudo`, `timestamp`, `id_alerta`) | dataset |
| `prediccion.py` | Corre el motor sobre cada alerta con los **hallazgos reales de la campaña** y mapea la traza a una **predicción binaria** (`vp_*`→`amenaza`; `fp_*`/`no_soportada`→`no_amenaza`), conservando prioridad, confianza, `accion_final`, `impacto`, `requiere_humano`. Cronometra cada llamada `procesar` | prototipo, cargar |
| `baseline.py` | El clasificador de nivel-Wazuh: `predecir(nivel, t) -> "amenaza"|"no_amenaza"` (`nivel ≥ t`); `barrido(filas, rango)` devuelve, por cada `t`, las predicciones y sus métricas | cargar, metricas |
| `metricas.py` | **Funciones puras** sobre `(predicciones, ground_truth)`: matriz de confusión, precisión, recall, F1, tasa de FP, acierto de prioridad (±1), Spearman de la cola, cobertura, tasa de escalado, continuidad, y conteo de anclaje | — (solo stdlib) |
| `anclaje.py` | Corre `justificador_llm.justificar_llm` con el generador 1B real sobre las 18 soportadas y cuenta `anclaje_verificado` | prototipo.justificador_llm, prototipo.analisis |
| `campana.py` | Orquestador + CLI: carga → predicción prototipo → barrido baseline → todas las métricas → anclaje → emite `resultados/campana-<fecha>.json` y `resultados/tabla.md`; registra las **condiciones de campaña** (perfil fijo, partición, versiones — RF-09) | todos |

**Frontera clara:** `metricas.py` no sabe nada del motor ni del baseline; recibe listas de etiquetas y
números y devuelve números. Eso lo hace trivialmente testeable con matrices conocidas. `prediccion.py`
es la única pieza que ejecuta el motor; `baseline.py` la única que interpreta el nivel de Wazuh;
`anclaje.py` la única que toca el LLM.

---

## 3. Flujo de datos

```
lab/dataset/etiquetado.jsonl ──filtra particion=evaluacion──> 205 (fila, alerta)
        │                                        fila: etiqueta (ground truth) + nivel_wazuh
        │
        ├─► [prediccion]  alerta + lab/campañas/2026-08-31-evaluacion/hallazgos.json
        │        motor: enriquecer→clasificar→politica→perfil→traza
        │        → predicción binaria + prioridad + accion_final/impacto + confianza + tiempo(ms)
        │
        ├─► [baseline]   nivel_wazuh; barrido t∈[rango] → predicción binaria por umbral
        │
        ▼
   [metricas]  MISMO ground truth para ambos  → tabla comparativa (baseline@óptimo vs prototipo)
        │
        ├─► [anclaje]  1B real sobre las 18 soportadas → % anclaje verificado
        ▼
   campana.py → resultados/campana-<fecha>.json + resultados/tabla.md
        │
        ▼
   documentacion/06-.../informe-evaluacion.md  (redactado a mano con los números reales)
```

**Por qué los hallazgos reales de la campaña:** el motor recomputa la postura del activo con
`analisis.enriquecer → postura_de(hallazgos, activo, servicio)`. Alimentarlo con el
`hallazgos.json` de la campaña de evaluación reproduce **exactamente** la postura con la que se etiquetó
cada alerta — la decisión del motor es fiel, sin sintetizar posturas y sin fuga.

---

## 4. Las métricas, exactas

### 4.1 Clasificación (matriz de confusión, no_soportada = VN)

Ground truth binario: `etiqueta == "VP"` → positivo (amenaza); `etiqueta in {"FP","no_soportada"}` →
negativo. Predicción del prototipo: `clase` empieza por `vp_` → positivo. Predicción del baseline:
`nivel ≥ t` → positivo.

| Métrica | Fórmula |
|---------|---------|
| Precisión | VP / (VP + FP) |
| Recall | VP / (VP + FN) |
| F1 | 2·P·R / (P + R) |
| Tasa de FP | FP / (FP + VN) |

Se reportan **los conteos crudos** de la matriz junto a los porcentajes (n pequeño — ver §5). Caso
degenerado (denominador 0, p. ej. el prototipo no marca ninguna amenaza) → la métrica se reporta como
`n/d` explícito, nunca como 0 silencioso.

### 4.2 Baseline por barrido

`barrido` evalúa `t` en un rango que cubre los niveles presentes (medido: 3, 5, 10 y cercanos → rango
`[3..12]`). Para cada `t`: matriz completa y F1. El informe muestra **la curva** y marca el **t óptimo
por F1**; la tabla comparativa usa el baseline en ese punto. Esto también produce el **mapeo
nivel→prioridad** que el doc de métricas §5 pide devolver a la Fase 5.

### 4.3 Priorización

Prioridad esperada por alerta soportada. **Honesto sobre la fuente:** `vulnerabilidades-esperadas.md`
documenta gravedad **por puerto/vulnerabilidad**, no un escalar limpio por nodo, y los `activo` del
dataset son nombres de nodo del lab (no los `activo` de los perfiles). Por eso la prioridad esperada se
define como un **mapeo pequeño y explícito, hecho a mano**, sobre el puñado de nodos que aparecen en las
alertas soportadas — tomando la gravedad del nodo de ese documento donde existe y la etiqueta como
desempate (VP de nodo grave > VP de nodo medio > FP). El mapeo vive en un fichero de datos del paquete
(`evaluacion/prioridad_esperada.yml`) con un comentario que justifica cada valor, no oculto en código.
Métricas: **acierto de prioridad ±1** y **Spearman** entre la cola del prototipo y la ideal. **Honesto
sobre el valor:** con 18 soportadas la correlación de cola es de señal débil y el mapeo es a mano; se
reporta con esa advertencia y con el n, como indicativo, no como resultado fuerte.

### 4.4 Operación

- **Tiempo de triaje:** instrumentado en `prediccion.py` (rodea `procesar` con `time.perf_counter`), no
  en el motor. Dos cifras separadas y honestas: (a) **clasificar+decidir** (baseline determinista,
  sub-ms) y (b) **justificar con LLM 1B** (~14 s, medido en 5C) — el camino interactivo con modelo. Se
  contrasta con RNF-04 sin fingir que el LLM es sub-segundo.
- **Cobertura (RF-10):** % de alertas clasificadas (clase ≠ `no_soportada`) — aquí bajo, porque el
  dataset es casi todo ruido de plataforma; se reporta como dato del dataset, no como fallo.
- **Tasa de escalado:** % con `requiere_humano == True`.

### 4.5 Continuidad (RF-20)

- **Acciones disruptivas indebidas:** nº de decisiones cuya `accion_final` tiene impacto
  `alcanza_servicio` **y** cuya alerta era un **FP** (habrían dañado el servicio por un falso positivo).
- **Retención correcta:** de esas, % con `requiere_humano == True` (la validación humana las habría
  retenido). Ambas salen de la traza (`impacto`, `requiere_humano`) sin instrumentación extra.

### 4.6 Anclaje de la justificación (RNF-02)

`anclaje.py` corre `justificar_llm(alerta, contexto, clase, generador_llama)` sobre las 18 soportadas y
cuenta `resultado["anclaje_verificado"] and resultado["justificador"] == "llm"`. Métrica: % de
justificaciones del LLM ancladas (las que degradaron a plantilla se reportan aparte, no inflan el
numerador). Reproducible: temp 0 (RNF-03), modelo registrado.

---

## 5. Honestidad, calibración y análisis de errores

- **n pequeño, declarado:** 18 alertas soportadas en evaluación (10 VP, 8 FP) es la limitación central.
  Toda métrica de clasificación se acompaña de su **conteo crudo**; ninguna conclusión se apoya en un
  porcentaje sin su n.
- **Realimentación a Fase 5** (doc de métricas §5): el barrido entrega el **mapeo nivel→prioridad** y el
  **umbral de confianza de escalado (RF-07)**, ambos marcados **provisionales** por el n.
- **Análisis de errores:** como los errores son pocos, se listan **caso por caso** (qué alerta, qué
  decidió el motor, qué era, por qué). Se recogen las limitaciones que el README de la fase ya exige: la
  falibilidad del auditor (ausencia de hallazgo ≠ activo seguro), el corte de conocimiento del modelo, y
  el desajuste encoder-sobre-prosa (documentado, no medible sin encoder).

---

## 6. Testing y entregables

### Testing (unittest, stdlib, sin pytest/pip)

- `test_metricas.py`: matrices de confusión **conocidas** → P/R/F1/tasa-FP esperados; casos degenerados
  (denominador 0 → `n/d`); Spearman sobre secuencias conocidas; continuidad sobre trazas fabricadas.
- `test_baseline.py`: `predecir` en los bordes del umbral; `barrido` devuelve un punto por `t`.
- `test_prediccion.py`: el mapeo traza→binario (`vp_*`→amenaza, resto→no) sobre trazas fabricadas;
  que cronometra sin romper la predicción.
- `test_anclaje.py`: el conteo de anclaje con un **generador falso** (sin el modelo real).
- `test_cargar.py`: filtra por partición y preserva el ground truth.

El harness sobre los datos reales (`campana.py` con el 1B) es **integración**: se corre una vez en la
tarea de verificación en vivo, no en la batería unitaria.

### Entregables

1. El paquete `evaluacion/` con sus tests (todo verde con generadores/datos falsos).
2. `evaluacion/resultados/campana-<fecha>.json` + `tabla.md` — generados con datos reales.
3. **El informe redactado** `documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md`:
   la tabla comparativa con números reales, la curva del baseline, el análisis de errores caso por caso,
   las limitaciones y los umbrales calibrados. Es lo que consume la Fase 7.
4. El README de la Fase 6 actualizado (de «No iniciada» a hecha, enlazando el informe).

---

## 7. Criterio de cierre

- El harness corre de punta a punta sobre la partición de evaluación y emite la tabla comparativa
  prototipo vs baseline (baseline en su punto óptimo por barrido).
- Las cuatro familias de métricas (clasificación, priorización, operación, continuidad) más el anclaje
  del 1B están calculadas, con conteos crudos y la advertencia de n.
- El informe redactado existe con la tabla real, el análisis de errores caso por caso y los umbrales
  calibrados devueltos a la Fase 5.
- Batería `unittest` verde (núcleo con datos/generadores falsos).
- Se cumpla o no la hipótesis, el resultado está medido y documentado honestamente.

---

## Documentos relacionados

- [Métricas y plan de evaluación](../../../documentacion/04-fase4-diseno-de-arquitectura/metricas-y-evaluacion.md) — la autoridad de qué medir y el baseline.
- [README de la Fase 6](../../../documentacion/06-fase6-evaluacion-del-prototipo/README.md) — el objetivo y las condiciones de campaña.
- [Fase 3: dataset etiquetado y particionado](../../../documentacion/03-fase3-entorno-de-pruebas/) — el ground truth y la partición.
- [Fase 5C: el justificador LLM](./2026-08-31-fase5c-justificador-llm-design.md) — el `justificar_llm`/`generador_llama` que mide el anclaje.
- [Ground truth del laboratorio](../../../lab/docs/vulnerabilidades-esperadas.md) — la gravedad de nodo para la prioridad esperada.
