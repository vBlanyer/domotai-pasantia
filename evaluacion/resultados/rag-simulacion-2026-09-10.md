# Evaluación del RAG por simulación de ataques

Sobre 12 alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida contra el `id` de ficha esperado (verdad estructural).

**Condiciones:** embedder `llama-3.2-1b-q4.gguf` · generador `llm-2:llama-3.2-1b-q4.gguf` (generador_servidor)

## Recuperación: consulta Fija vs Agéntica

| Métrica | Fija | Agéntica |
|---|---|---|
| Hit Rate@1 | 0.33 | 0.25 |
| Hit Rate@3 | 0.58 | 0.25 |
| Hit Rate@5 | 0.75 | 0.58 |
| Precision@1 | 0.33 | 0.25 |
| Precision@3 | 0.19 | 0.08 |
| Precision@5 | 0.15 | 0.12 |
| MRR | 0.47 | 0.32 |
