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
