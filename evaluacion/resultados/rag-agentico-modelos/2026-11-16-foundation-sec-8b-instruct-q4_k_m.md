# Evaluación del RAG por simulación de ataques

Sobre 16 alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida contra el `id` de ficha esperado (verdad estructural).

**Condiciones:** embedder `bge-m3-q8.gguf` (embedder_por_defecto) · generador `llm-6:foundation-sec-8b-instruct-q4_k_m.gguf` (generador_servidor)

## Recuperación: consulta Fija vs Agéntica

| Métrica | Fija | Agéntica |
|---|---|---|
| Hit Rate@1 | 0.50 | 0.31 |
| Hit Rate@3 | 0.81 | 0.81 |
| Hit Rate@5 | 0.94 | 0.88 |
| Precision@1 | 0.50 | 0.31 |
| Precision@3 | 0.38 | 0.27 |
| Precision@5 | 0.26 | 0.18 |
| MRR | 0.68 | 0.56 |

## Síntesis del 1B (justificación con contexto recuperado)
- Tasa de anclaje: 1.00  ·  Tasa de término: 0.31
- Justificaciones que cayeron a la plantilla: 0 de 16 (texto del modelo sin anclar, fallo o plazo superado)
- Escritas por el modelo (y ancladas): 16 de 16  ·  Término en las del modelo: 0.31

## Tiempos (plazo del banco: 900 s; producción: 120 s)
- Llamadas al modelo: 48 · media 80.4 s · máx 213.3 s · por encima de 120 s: 16
