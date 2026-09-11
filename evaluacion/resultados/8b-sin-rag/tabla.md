# Tabla comparativa — perfil empresarial
n = 233 alertas (42 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 1.000 | 0.247 |
| Recall | 1.000 | 0.741 |
| F1 | 1.000 | 0.370 |
| Tasa de FP | 0.000 | 0.296 |

Matriz prototipo: {'vp': 27, 'fp': 0, 'vn': 206, 'fn': 0}
Matriz baseline: {'vp': 20, 'fp': 61, 'vn': 145, 'fn': 7}

Anclaje LLM (RNF-02): {'llm_total': 42, 'anclados': 42, 'degradados': 0, 'pct_anclaje': 1.0, 'versiones': ['llm-5:llama-3.1-8b-instruct-q4.gguf'], 'por_clase': {'vp_intento_acceso': {'llm': 27, 'plantilla': 0, 'pct_anclaje': 1.0}, 'fp_actividad_legitima': {'llm': 15, 'plantilla': 0, 'pct_anclaje': 1.0}}}
