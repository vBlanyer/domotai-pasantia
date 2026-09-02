# Tabla comparativa — perfil empresarial
n = 205 alertas (18 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 0.556 | 0.154 |
| Recall | 1.000 | 1.000 |
| F1 | 0.714 | 0.267 |
| Tasa de FP | 0.041 | 0.282 |

Matriz prototipo: {'vp': 10, 'fp': 8, 'vn': 187, 'fn': 0}
Matriz baseline: {'vp': 10, 'fp': 55, 'vn': 140, 'fn': 0}

Anclaje LLM (RNF-02): {'llm_total': 18, 'anclados': 18, 'degradados': 0, 'pct_anclaje': 1.0}
