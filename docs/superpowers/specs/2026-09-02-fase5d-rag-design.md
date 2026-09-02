# Diseño — Fase 5D: RAG local para el justificador

**Fecha:** 2026-09-02
**Fase:** 5 — Implementación del prototipo (subproyecto D)
**Requisitos / objetivos que ejercita:** el **objetivo general** del proyecto (RAG local sobre modelo
desplegado localmente), RF-05 (justificación estructurada), RNF-02 (explicabilidad verificable),
RNF-08 (inyección de prompt), RNF-09 (degradación), RNF-01 (privacidad: todo local).
**Cierra:** la incongruencia **I-12** (RAG del objetivo general nunca diseñado ni implementado).

---

## 1. Objetivo y encuadre

El **objetivo general oficial** del proyecto exige «un módulo de generación aumentada por recuperación
(RAG) ejecutado sobre un modelo desplegado de forma local». Hasta ahora no existía. 5D lo implementa
**detrás de la misma interfaz `justificar_llm` de la Fase 5C** — el motor de triaje no cambia.

Además de cumplir el objetivo, RAG **ataca el fallo que la Fase 6 midió**: el justificador 1B ancla al
100 % pero es semánticamente poco fiable (describe la técnica MITRE y la regla de Wazuh al revés),
porque genera de memoria paramétrica. RAG recupera la **descripción real** de una base de conocimiento
local y la inyecta en el prompt, para que el modelo se apoye en evidencia recuperada en vez de inventar.

### Viabilidad confirmada (antes de diseñar)

- `~/miniforge3/envs/triaje-ml/bin/llama-embedding` existe y produce vectores de embedding con el GGUF
  de 1B **ya presente** (`modelos/llama-3.2-1b-q4.gguf`) — **sin descargas nuevas, todo local**.
- El corpus necesario es minúsculo: el dataset usa 3 técnicas MITRE (T1110, T1110.001, T1021.004) y
  ~4 reglas de Wazuh (5760, 5763, 5710, 5712).

### Decisiones fijadas (aprobadas antes de diseñar)

1. **Corpus mínimo curado:** fichas cortas y reales de las técnicas MITRE, las reglas de Wazuh y las
   vulnerabilidades del laboratorio que aparecen en el dataset (~15-20 documentos), redactadas desde
   fuentes reales. No se descarga ATT&CK completo (ruido para un caso de una familia).
2. **Recuperación por embeddings con el 1B actual:** semántica, vía `llama-embedding` sobre el GGUF ya
   presente; similitud coseno en Python puro. Sin modelo de embeddings dedicado ni descargas.

### Qué NO cubre 5D

- El clasificador con fine-tuning (sigue bloqueado por datos).
- ATT&CK completo ni un modelo de embeddings dedicado (posibles mejoras futuras; la interfaz del
  embedder es inyectable, así que sustituirlo no toca el motor).

---

## 2. El corpus (base de conocimiento)

Documentos cortos en `prototipo/corpus/corpus.jsonl`, uno por línea:
`{"id": "...", "tipo": "mitre|regla|vuln", "titulo": "...", "texto": "..."}`. Redactados a mano desde
fuentes reales (MITRE ATT&CK, la documentación de reglas de Wazuh, el inventario
`lab/docs/vulnerabilidades-esperadas.md`). Contenido mínimo:

- **MITRE** (3): T1110 *Brute Force*, T1110.001 *Password Guessing*, T1021.004 *Remote Services: SSH* —
  nombre real, qué es la técnica, cómo se detecta.
- **Reglas Wazuh** (4): 5760, 5763, 5710, 5712 — qué evento detecta cada una (p. ej. 5760 = intento de
  autenticación SSH fallido), no «un protocolo de seguridad».
- **Vulnerabilidades del lab** (las relevantes a acceso/SSH de `objetivo-vuln`).

Es **dato versionado**, no código. El corpus es **de confianza** (lo escribimos nosotros) — distinción
clave para RNF-08 (§4).

---

## 3. El módulo `prototipo/rag.py`

Misma **frontera de subprocess** que 5C: el embedder vive en el entorno conda y se invoca por
subprocess; se inyecta, de modo que los tests usan un embedder falso y solo la corrida en vivo toca el
binario. Interfaz:

- `cargar_corpus(ruta) -> list[dict]` — lee `corpus.jsonl`.
- `construir_consulta(alerta) -> str` — arma la consulta de recuperación desde los campos
  estructurados de la alerta: `regla_id`, `mitre` (lista), `servicio`. **Solo campos estructurados**,
  nunca el `full_log` (coherente con RNF-08).
- `embedder_llama(textos, modelo=..., binario=...) -> list[list[float]]` — subprocess **batched** a
  `llama-embedding` (un solo cargue del modelo para todos los textos); devuelve un vector por texto.
  Ante error/timeout devuelve `[]` (para que el justificador degrade — RNF-09).
- `_coseno(a, b) -> float` — similitud coseno en **Python puro** (`math`), 0.0 si algún vector es nulo.
- `indexar(corpus, embedder) -> list[dict]` — añade a cada doc su `vector`; devuelve el índice.
- `guardar_indice(indice, ruta)` / `cargar_indice(ruta)` — el índice se **precomputa** a
  `prototipo/corpus/indice.json` (pequeño, ~20 vectores) para no re-vectorizar en cada corrida. Se
  **versiona** junto al corpus, así la evaluación corre sin re-indexar y sin el modelo.
- `recuperar(consulta, indice, embedder, k=3) -> list[dict]` — embebe la consulta, ordena el índice por
  coseno, devuelve los `k` documentos más cercanos. Si el embedder falla (vector vacío), devuelve `[]`.

**Frontera del índice vs modelo:** el corpus (texto) y el `indice.json` (vectores) se versionan; un
script/paso de indexado los regenera con el modelo cuando el corpus cambia.

---

## 4. Integración con el justificador (RNF-08 intacto)

En `prototipo/justificador_llm.py`:

- `construir_prompt(alerta, contexto, clase, pasajes=None)` — parámetro **opcional** `pasajes`
  (retrocompatible con 5C). Si llegan, se inyectan en un bloque delimitado **«Conocimiento de
  referencia (fuentes verificadas):»** con la instrucción de apoyarse en él. El resto del prompt no
  cambia.
- `justificar_con_rag(alerta, contexto, clase, generador, indice, embedder, k=3, fallback=...)` —
  recupera los pasajes (`rag.recuperar`) y llama al camino de `justificar_llm` con el prompt aumentado;
  degrada a plantilla igual que 5C si el generador falla o el anclaje no se cumple. Devuelve el mismo
  dict `{texto, justificador, anclaje_verificado}` más `pasajes_usados` (los ids recuperados, para la
  traza).

**RNF-08 se mantiene, y es el punto delicado:** el bloque inyectado es el **corpus curado de
confianza**, no el `full_log` del atacante. La consulta de recuperación se construye **solo con campos
estructurados** (§3), así que texto controlado por el atacante sigue sin entrar en el prompt. La
superficie de inyección no aumenta.

---

## 5. Flujo de datos

```
corpus.jsonl ──indexar (1 vez, offline, con el modelo)──> indice.json  (versionado)
        │
alerta ──construir_consulta (regla_id + mitre + servicio)──> embedder_llama
        │                                                          │
        │                                    recuperar: coseno top-k sobre indice.json
        ▼                                                          ▼
   pasajes reales (p. ej. «regla 5760 = intento de autenticación SSH fallido»,
                    «T1110.001 Password Guessing = ataque de adivinación de credenciales»)
        │
   construir_prompt(alerta, contexto, clase, pasajes) ──> generador 1B ──> justificación fundamentada
```

---

## 6. El pago, medido (re-evaluación de la Fase 6)

`evaluacion/anclaje.py` ya corre el justificador 1B sobre las 18 alertas soportadas. Se añade la
variante **con RAG** y se comparan las dos columnas:

- **Anclaje (automático):** se espera que siga alto (~100 %); RAG no lo empeora.
- **Corrección semántica / utilidad (lectura manual sobre la muestra):** es donde debe verse la
  mejora — con RAG, la justificación describe la técnica y la regla **bien**, apoyándose en el pasaje
  recuperado, en vez de al revés.

Ese contraste **RAG vs sin RAG** es la evidencia que cierra I-12 con número. Un `--con-rag` en la
campaña selecciona la variante. Si RAG **no** mejorara la corrección, ese resultado negativo también es
un hallazgo válido y honesto.

---

## 7. Testing y entregables

### Testing (unittest, stdlib, sin pytest/pip)

- `construir_consulta`: usa solo campos estructurados; incluye regla, técnicas y servicio; NO el full_log.
- `_coseno`: valores conocidos (vectores idénticos → 1.0; ortogonales → 0.0; nulo → 0.0).
- `recuperar`: con un **embedder falso** (mapa texto→vector fijo), la consulta recupera el doc esperado
  en el top-k, de forma determinista.
- `indexar`: añade `vector` a cada doc.
- `construir_prompt` con `pasajes`: el bloque «Conocimiento de referencia» aparece y sigue sin incluir
  el `full_log`.
- `justificar_con_rag`: con embedder y generador falsos, produce el dict con `pasajes_usados` y degrada
  a plantilla cuando el generador falla.
- El `embedder_llama` real (subprocess) y la corrida con RAG sobre las 18 se validan **en vivo**, no en
  la batería unitaria.

### Entregables

1. `prototipo/corpus/corpus.jsonl` (fichas curadas) + `prototipo/corpus/indice.json` (índice
   versionado).
2. `prototipo/rag.py` con sus tests.
3. El enganche en `justificador_llm.py` (`construir_prompt(..., pasajes)` + `justificar_con_rag`), con
   tests y retrocompatible con 5C.
4. La re-evaluación con la comparación RAG vs sin RAG y una nota en el informe de la Fase 6.
5. Documentación en `prototipo/README.md` (sección RAG) y cierre de I-12 en `estado-y-riesgos.md`.

---

## 8. Criterio de cierre de 5D

- `rag.recuperar`, con un embedder falso, devuelve el documento correcto del corpus para una alerta de
  fuerza bruta SSH (recupera T1110.001 y la regla 5760).
- `construir_prompt` inyecta los pasajes en un bloque delimitado sin incluir el `full_log` (RNF-08).
- `justificar_con_rag` degrada a plantilla si el generador o el embedder fallan (RNF-09).
- **En vivo:** con el 1B y el corpus reales, una alerta VP produce una justificación **fundamentada en
  el pasaje recuperado**, y la comparación con/sin RAG está medida sobre las 18 soportadas.
- Batería `unittest` verde (núcleo con embedder/generador falsos).
- I-12 cerrada: el prototipo cumple el módulo RAG del objetivo general.

---

## Documentos relacionados

- [Fase 5C: el justificador con LLM](./2026-08-31-fase5c-justificador-llm-design.md) — la interfaz `justificar_llm` y la frontera de subprocess que 5D reutiliza.
- [Informe de la Fase 6](../../documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md) — el fallo de corrección semántica del 1B que RAG ataca.
- [Estado y riesgos, I-12](../../documentacion/00-general/estado-y-riesgos.md) — la incongruencia que 5D cierra.
- [Selección del modelo](../../documentacion/04-fase4-diseno-de-arquitectura/seleccion-del-modelo.md) — el Perfil A y el entorno conda local.
