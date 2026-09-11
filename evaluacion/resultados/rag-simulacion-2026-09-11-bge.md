# Evaluación del RAG por simulación de ataques

Sobre 16 alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida contra el `id` de ficha esperado (verdad estructural).

**Condiciones:** embedder `bge-m3-q8.gguf` (embedder_por_defecto) · generador `llm-5:llama-3.1-8b-instruct-q4.gguf` (generador_servidor)

## Recuperación: consulta Fija vs Agéntica

| Métrica | Fija | Agéntica |
|---|---|---|
| Hit Rate@1 | 0.44 | 0.69 |
| Hit Rate@3 | 0.81 | 0.94 |
| Hit Rate@5 | 0.94 | 1.00 |
| Precision@1 | 0.44 | 0.69 |
| Precision@3 | 0.38 | 0.42 |
| Precision@5 | 0.26 | 0.29 |
| MRR | 0.64 | 0.83 |
