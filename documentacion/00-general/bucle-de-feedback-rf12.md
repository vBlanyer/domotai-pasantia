# Bucle de feedback (RF-12): cómo se consumen las reclasificaciones

**Estado: diseño / trabajo futuro.** Documenta cómo se *usaría* el feedback que el prototipo ya persiste,
para cuando se implemente el consumidor. Hoy el feedback se **almacena** (RF-12) pero **no se consume
automáticamente**: no reentrena, no cura el corpus, no cambia reglas. Esta nota fija los cuatro destinos y el
componente pendiente, para quien retome RF-12.

## Punto de partida: qué produce hoy el lazo

Cada vez que el analista **reclasifica** un incidente (o lo aprueba/rechaza), la traza encadenada por hash
(`prototipo/traza.py`, RF-09) registra:

```
(alerta estructurada, clase_del_motor, veredicto_humano, clase_reclasificada)
```

La reclasificación **retiene sin ejecutar** y guarda `clase_reclasificada` como feedback (RF-08/RF-12). Lo que
**no** hace, por diseño: no alimenta el RAG, no reentrena, no muta ninguna regla. RF-12 lo dice literal —
*"almacenar el feedback en formato reutilizable, **sin reentrenamiento**"*. El enganche (los datos, en JSONL
reutilizable) existe; el consumidor es lo pendiente.

## Precisión de términos: el RAG no se «entrena»

La pregunta natural —"¿cómo entrena esto al RAG?"— parte de una confusión útil de aclarar:

- El **RAG no es un modelo con pesos**: es *recuperación* sobre un **corpus curado** de fichas
  (MITRE/D3FEND/reglas/descartes) + un embedder + coseno. Mejorarlo es **curar el corpus**, no entrenar.
- Lo que sí «aprende» es el **clasificador determinista** (reglas, descubiertas y validadas con el árbol
  `prototipo/arbol.py`).
- Y el ajuste más directo de todos no es aprendizaje, es **configuración** (perfil, cobertura del auditor).

Por eso un mes de reclasificaciones no alimenta *un* bucle, sino **cuatro**.

## Qué tienes al cabo de un mes

Filtrando la traza del periodo, las tripletas `(alerta, clase_motor, clase_reclasificada)` son, ni más ni
menos, **datos etiquetados por humanos**: ground truth acumulado sobre alertas reales. La cuestión es a qué
bucle enruta cada patrón.

## Los cuatro destinos del feedback

### 1 · Configuración — el más rápido, sin tocar código

El patrón más común y su arreglo directo en el **perfil de cliente**:

- Un origen que se reclasifica una y otra vez a `fp_actividad_legitima` → se añade su IP a
  `origenes_legitimos`. El motor pasa a marcarlo FP **solo**.
- Casos grises recurrentes (`postura = None`, el auditor no había escaneado ese activo) → se da **cobertura
  al auditor** sobre ese activo. El gris se resuelve en el motor, deja de preguntar.
- Escalado sistemáticamente tarde/pronto → se recalibra `continuidad.umbral_confianza` (RF-07).

Es el bucle que de verdad **corta la recurrencia**: sin él, la misma alerta al día siguiente se clasifica
igual y se vuelve a reclasificar (el motor es determinista y no recuerda el clic de ayer; RNF-03).

### 2 · El corpus del RAG — curación, no entrenamiento

Aquí el feedback toca el RAG, con un matiz que es el corazón del asunto: **no se meten las alertas
reclasificadas en el corpus**. El corpus es conocimiento defensivo curado, no un registro de decisiones. Se
lee la señal y se cura a mano:

- Muchos descartes a `fp_exposicion_inexistente` para un servicio que el justificador no supo fundamentar →
  se **añade o afina una ficha de descarte** (`TIPOS_DESCARTE`) que explique ese motivo, y se **reindexa**
  con `python3 -m prototipo.rag --indexar`.
- Ataques cuya técnica no tenía ficha MITRE/D3FEND → se añaden esas fichas.
- **Cada cambio se valida contra el banco de recuperación** (`evaluacion/simular_ataques_rag.py`, Hit@k/MRR;
  ver [`docs/pruebas/02-rag-evaluacion.md`](../../docs/pruebas/02-rag-evaluacion.md)) **antes** de comprometerlo:
  curar mal el corpus **degrada** la recuperación (medido al crecer el corpus con bge-m3). Por eso se mide.

Esto mejora la **explicación** (el trabajo del RAG), no la clasificación. Para eso está el bucle 3.

### 3 · Las reglas del clasificador — el «entrenamiento» honesto

Es el uso más valioso de las reclasificaciones: **etiquetas nuevas para el árbol**. `prototipo/arbol.py` ya
existe como instrumento de descubrimiento de reglas (así salió la 6ª, la de ráfaga, con evidencia 79/79; ver
`evaluacion/entrenado.py`). El ciclo:

1. Unir el dataset original + las tripletas del mes → **dataset enriquecido**.
2. Reentrenar el **árbol CART** sobre él, con partición y sin fuga.
3. El árbol **propone reglas candidatas** con su evidencia (p. ej. "origen X + condición Y → clase Z,
   120/124 estable con particiones intercambiadas").
4. Un humano **valida y promueve** las reglas fuertes a `analisis.clasificar` como regla determinista
   auditable.

El árbol **descubre**; la persona **promueve**. Nunca el árbol reescribe el motor solo.

### 4 · Evaluación / deriva

Las tripletas son ground truth para **medir** al motor sobre datos reales del mes con el marco de la Fase 6
(`evaluacion/`): ¿bajó la precisión?, ¿hay un error sistemático (una familia que siempre se reclasifica
igual)? Eso **prioriza** qué arreglar en los bucles 1–3.

## El reparto, en una tabla

| Patrón en las reclasificaciones del mes | Bucle | Qué cambia | Quién aprueba |
|---|---|---|---|
| Mismo origen → `fp_actividad_legitima` | Config | `origenes_legitimos` del perfil | operador |
| Grises (`postura = None`) recurrentes | Config | cobertura del auditor | operador |
| Escalado mal calibrado | Config | `umbral_confianza` (RF-07) | operador |
| Descarte mal fundamentado por el LLM | **Corpus RAG** | ficha de descarte + reindexar (validar con el banco) | curador |
| Error de clase reproducible con evidencia | **Reglas / árbol** | nueva regla en `clasificar` | revisor humano |
| Deriva de precisión/recall | Evaluación | prioriza los otros bucles | — |

## Lo que ya existe y lo que falta

- **Ya existe:** la traza como fuente (RF-13), `arbol.py` (descubrimiento de reglas), `rag.py --indexar`
  (recuración del corpus), el banco de recuperación (`evaluacion/simular_ataques_rag.py`) y el marco de
  evaluación (Fase 6). Las piezas están.
- **Falta (RF-12):** el **cosechador** — un proceso que lea la traza del periodo, **agregue** los patrones
  (cuántas reclasificaciones, de qué clase a cuál, por qué origen/servicio/familia) y **enrute** cada uno a
  su bucle con una propuesta concreta (una línea de perfil, una ficha de corpus, una regla candidata del
  árbol). Entrada: `trazas-*.jsonl` del periodo. Salida: un informe de propuestas para revisión humana.

## La regla de oro

En los cuatro bucles, **un humano revisa y una versión cambia** (perfil, corpus, regla) de forma trazable y
reproducible. Es lo contrario a un modelo que se ajusta con cada clic: eso daría respuestas distintas a la
misma alerta sin razón auditable, y rompería la tesis del proyecto (determinismo, explicabilidad, sin caja
negra; RNF-03). **El feedback informa el cambio; no lo aplica solo.**

## Referencias

- [Requisitos](../02-fase2-estado-del-arte/requisitos.md) — RF-08 (validación humana), RF-09 (traza),
  RF-12 (feedback reutilizable sin reentrenamiento), RF-07 (umbral de escalado).
- [El clasificador y el árbol](../../prototipo/README.md) — por qué un árbol y no fine-tuning; la 6ª regla.
- [Evaluación de la recuperación (RAG)](../../docs/pruebas/02-rag-evaluacion.md) — el banco Hit@k/MRR.
- [Caso de uso acotado](../01-fase1-analisis-del-modulo/caso-de-uso-acotado.md) — las categorías de clase.
