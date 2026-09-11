# Evaluación del RAG por simulación de ataques

Sobre 12 alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida contra el `id` de ficha esperado (verdad estructural).

**Condiciones:** embedder `bge-m3-q8.gguf` · generador `llm-4:llama-3.1-8b-instruct-q4.gguf` (generador_servidor)

## Recuperación: consulta Fija vs Agéntica

| Métrica | Fija | Agéntica |
|---|---|---|
| Hit Rate@1 | 0.50 | 0.50 |
| Hit Rate@3 | 0.83 | 0.92 |
| Hit Rate@5 | 1.00 | 1.00 |
| Precision@1 | 0.50 | 0.50 |
| Precision@3 | 0.39 | 0.39 |
| Precision@5 | 0.27 | 0.25 |
| MRR | 0.70 | 0.73 |
