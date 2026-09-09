# Evaluación del RAG por simulación de ataques

Sobre 12 alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida contra el `id` de ficha esperado (verdad estructural).

## Recuperación: consulta Fija vs Agéntica

| Métrica | Fija | Agéntica |
|---|---|---|
| Hit Rate@1 | 0.00 | 0.00 |
| Hit Rate@3 | 0.25 | 0.08 |
| Hit Rate@5 | 0.50 | 0.42 |
| Precision@1 | 0.00 | 0.00 |
| Precision@3 | 0.08 | 0.03 |
| Precision@5 | 0.10 | 0.08 |
| MRR | 0.14 | 0.10 |

## Interpretación (hallazgos de la calibración)

**La recuperación es débil y la consulta agéntica la empeora.** `Hit Rate@1 = 0.00` (la ficha correcta
nunca es la primera), `Hit Rate@5 = 0.50`, `MRR = 0.14`. El paso agéntico queda **por debajo** de la
consulta fija en todas las métricas — confirma, cuantificado, que el 1B formula consultas de búsqueda pobres.

**Causa raíz (diagnóstico).** La consulta fija es `regla {id} tecnicas MITRE {tec} servicio {srv}`; los
*embeddings* del 1B quedan **dominados por la palabra «regla»** y arrastran las fichas `regla-*` al top-5
sin importar la técnica. Ejemplo real (alerta de fuerza bruta SSH, T1110.001):

    consulta: regla 5760 tecnicas MITRE T1110.001 servicio ssh
    top-5:    regla-5712, regla-5763, mapeo-reconocimiento, regla-5710, d3fend-D3-AL
    esperado: mitre-T1110.001, mapeo-acceso_credenciales   (ambas fuera del top-5)

Las fichas `mitre-*` y `mapeo-*` esperadas son expulsadas; incluso aparece `mapeo-reconocimiento` (familia
equivocada). El 1B es un modelo de **generación**, no de *embeddings*: su discriminación semántica es baja.

**Palancas (trabajo futuro, no en este banco).**
1. **Reformular la consulta fija**: liderar con técnica + familia + intención de contramedida y quitar el
   número de regla (ruido que sesga hacia `regla-*`). Palanca barata; el banco ya la puede medir.
2. **Modelo de *embeddings* dedicado** (p. ej. un `bge`/`e5` pequeño) en vez del 1B de generación: es la
   corrección de fondo. La interfaz `embedder` ya es inyectable.
3. Revisar si conviene separar/ponderar el corpus por tipo.

**Valor del banco.** Convirtió un «creemos que el RAG es bueno» en un «la recuperación mide Hit@5=0.50 y
el paso agéntico resta», con la causa localizada. Eso es exactamente para lo que sirve la calibración.
