# Evaluación del RAG por simulación de ataques

Sobre 14 alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida contra el `id` de ficha esperado (verdad estructural).

**Condiciones:** embedder `bge-m3-q8.gguf` (embedder_por_defecto) · generador `llm-5:llama-3.1-8b-instruct-q4.gguf` (generador_servidor)

## Recuperación: consulta Fija vs Agéntica

| Métrica | Fija | Agéntica |
|---|---|---|
| Hit Rate@1 | 0.50 | 0.57 |
| Hit Rate@3 | 0.79 | 0.93 |
| Hit Rate@5 | 0.93 | 1.00 |
| Precision@1 | 0.50 | 0.57 |
| Precision@3 | 0.38 | 0.40 |
| Precision@5 | 0.27 | 0.30 |
| MRR | 0.67 | 0.77 |
