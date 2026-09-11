# Tabla comparativa — perfil empresarial
n = 220 alertas (31 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 1.000 | 0.237 |
| Recall | 1.000 | 1.000 |
| F1 | 1.000 | 0.384 |
| Tasa de FP | 0.000 | 0.303 |

Matriz prototipo: {'vp': 19, 'fp': 0, 'vn': 201, 'fn': 0}
Matriz baseline: {'vp': 19, 'fp': 61, 'vn': 140, 'fn': 0}

Anclaje LLM (RNF-02): {'llm_total': 31, 'anclados': 31, 'degradados': 0, 'pct_anclaje': 1.0, 'versiones': ['llm-5:llama-3.1-8b-instruct-q4.gguf'], 'por_clase': {'vp_intento_acceso': {'llm': 19, 'plantilla': 0, 'pct_anclaje': 1.0}, 'fp_actividad_legitima': {'llm': 12, 'plantilla': 0, 'pct_anclaje': 1.0}}}
