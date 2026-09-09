# Nivel 2 · RAG, LLM y evaluación (necesita el modelo local)

## 2.1 · Evaluación contra el baseline (Fase 6)

**Sinopsis**
```
python3 -m evaluacion.campana [--particion evaluacion|todas] [--perfil empresarial|residencial] \
                              [--sin-llm] [--con-rag] [--salida-dir DIR] [--hallazgos RUTA]
```

**Ejemplo** (sin LLM, rápido — solo métricas de clasificación/priorización)
```bash
python3 -m evaluacion.campana --particion evaluacion --sin-llm
```

**Ejemplo** (con RAG, lento ~5 min — corre el 1B para el anclaje)
```bash
python3 -m evaluacion.campana --particion evaluacion --con-rag
```

**Esperado:** tabla prototipo vs baseline. Resultado principal: **precisión 1.000, tasa de FP 0.000** frente
al baseline (0.154 / 0.282). Escribe `evaluacion/resultados/tabla.md` y `campana-<fecha>.json`.

## 2.2 · Compilar el corpus del RAG desde MITRE ATT&CK

Destila las técnicas del perímetro del bundle STIX oficial y las compone con las fichas curadas.

**Sinopsis**
```
python3 -m prototipo.extraer_attack [bundle.json] [curado.jsonl] [corpus.jsonl]
```

**Ejemplo**
```bash
# requiere prototipo/corpus/fuentes/enterprise-attack.json (ver prototipo/corpus/fuentes/README.md)
python3 -m prototipo.extraer_attack
```

**Esperado:** `15 tecnicas extraidas + 14 curadas -> 29 fichas -> prototipo/corpus/corpus.jsonl`.

## 2.3 · Indexar y consultar el RAG (5D)

**Sinopsis**
```
python3 -m prototipo.rag ( --indexar | --consulta "<texto>" )
```

**Ejemplo** (generar el índice de embeddings; una vez, ~40 s)
```bash
python3 -m prototipo.rag --indexar
```

**Ejemplo** (ver qué recupera para una consulta defensiva)
```bash
python3 -m prototipo.rag --consulta "contramedida defensiva D3FEND filtrado de trafico ante fuerza bruta SSH"
```

**Esperado:** los pasajes más cercanos por coseno (fichas ATT&CK / D3FEND / mapeos). El corpus encadena
*técnica → contramedida D3FEND → acción del catálogo*.

## 2.4 · Banco de simulación y evaluación del RAG

Calibra la recuperación (**fija vs agéntica**) sobre 12 alertas sintéticas etiquetadas, con **Hit Rate@K,
Precision@K y MRR** (K=1,3,5).

**Sinopsis**
```
python3 -m evaluacion.simular_ataques_rag [--con-sintesis] [--salida-dir DIR]
```

**Ejemplo** (recuperación; usa el 1B para la consulta agéntica, ~6 min)
```bash
python3 -m evaluacion.simular_ataques_rag
```

**Ejemplo** (+ tasa de anclaje de la síntesis del 1B, más lento)
```bash
python3 -m evaluacion.simular_ataques_rag --con-sintesis
```

**Esperado:** tabla comparativa en `evaluacion/resultados/rag-simulacion-<fecha>.md`. Referencia actual:
**MRR 0.50 (agéntica)**, Hit@5 0.75; 3/4 familias al 100 % (servicio_expuesto residual).
