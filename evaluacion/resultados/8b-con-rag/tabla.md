# Tabla comparativa — perfil empresarial
n = 300 alertas (106 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 0.978 | 0.548 |
| Recall | 1.000 | 0.920 |
| F1 | 0.989 | 0.687 |
| Tasa de FP | 0.009 | 0.310 |

Matriz prototipo: {'vp': 87, 'fp': 2, 'vn': 211, 'fn': 0}
Matriz baseline: {'vp': 80, 'fp': 66, 'vn': 147, 'fn': 7}

Anclaje LLM (RNF-02): {'llm_total': 106, 'anclados': 106, 'degradados': 0, 'pct_anclaje': 1.0, 'versiones': ['llm-6:llama-3.1-8b-instruct-q4.gguf'], 'por_clase': {'vp_intento_acceso': {'llm': 89, 'plantilla': 0, 'pct_anclaje': 1.0}, 'fp_actividad_legitima': {'llm': 17, 'plantilla': 0, 'pct_anclaje': 1.0}}}
