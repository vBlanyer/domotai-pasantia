# Evaluación del RAG por simulación de ataques

Sobre 12 alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida contra el `id` de ficha esperado (verdad estructural).

## Recuperación: consulta Fija vs Agéntica

| Métrica | Fija | Agéntica |
|---|---|---|
| Hit Rate@1 | 0.25 | 0.25 |
| Hit Rate@3 | 0.42 | 0.75 |
| Hit Rate@5 | 0.75 | 0.75 |
| Precision@1 | 0.25 | 0.25 |
| Precision@3 | 0.14 | 0.25 |
| Precision@5 | 0.15 | 0.15 |
| MRR | 0.41 | 0.50 |

## Interpretación (calibración, con palancas 1+3 aplicadas)

**Estado final:** la recuperación **agéntica** con las mejoras da `Hit@3 = 0.75`, `Hit@5 = 0.75`,
`MRR = 0.50`. Dos conclusiones:

1. **Las palancas funcionaron y se pueden medir.** Comparado con la primera corrida (consulta fija con
   número de regla, sin filtrar el conocimiento):

   | Métrica | Baseline inicial (fija) | **Final (agéntica, palancas 1+3)** |
   |---|---|---|
   | Hit Rate@1 | 0.00 | **0.25** |
   | Hit Rate@3 | 0.25 | **0.75** |
   | Hit Rate@5 | 0.50 | **0.75** |
   | MRR | 0.14 | **0.50** (≈3.5×) |

   - **Palanca 1** — reformular `construir_consulta`: liderar con técnica MITRE + familia + intención de
     contramedida y **omitir el número de regla** (sesgaba los *embeddings* del 1B hacia las fichas `regla-*`).
   - **Palanca 3** — **excluir las fichas `regla-*`** de la recuperación de conocimiento (describen reglas
     de Wazuh, casi idénticas a los ataques de credenciales/servicio; competían y expulsaban a las
     `mitre-*`/`mapeo-*`/`d3fend-*` esperadas).

2. **La consulta agéntica pasó de restar a sumar.** En la primera corrida el paso agéntico **empeoraba**
   (Hit@5 0.42 < 0.50); ahora **mejora** (Hit@3 0.75 vs 0.42 fija; MRR 0.50 vs 0.41). Su valor estaba
   **enmascarado** por el ruido de las fichas de regla. La calibración lo hizo visible.

**Por familia (Hit@5, recuperación fija):** `acceso_credenciales 1.00`, `reconocimiento 1.00`,
`explotacion_conocida 1.00`, **`servicio_expuesto 0.00`** — residual. Las alertas de servicio expuesto
(T1133/T1021/T1021.004) siguen sin recuperar su ficha esperada en top-5; probable trabajo futuro: reforzar
esas fichas o un modelo de *embeddings* dedicado (la interfaz `embedder` ya es inyectable).

**Valor del banco:** convirtió suposiciones en un ciclo medible — reveló el fallo, localizó la causa
(fichas de regla + *embeddings* débiles), guió dos correcciones y **cuantificó la mejora** (MRR ×3.5),
además de descubrir que el paso agéntico sí aporta una vez quitado el ruido.
