# Tabla comparativa — perfil empresarial
n = 205 alertas (18 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 1.000 | 0.154 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 0.267 |
| Tasa de FP | 0.000 | 0.282 |

Matriz prototipo: {'vp': 10, 'fp': 0, 'vn': 195, 'fn': 0}
Matriz baseline: {'vp': 10, 'fp': 55, 'vn': 140, 'fn': 0}

Anclaje LLM (RNF-02): {'llm_total': 11, 'anclados': 11, 'degradados': 7, 'pct_anclaje': 0.6111111111111112, 'versiones': ['llm-3:llama-3.1-8b-instruct-q4.gguf', 'plantilla-0']}
