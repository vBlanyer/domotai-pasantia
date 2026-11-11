# Tabla comparativa — perfil empresarial
n = 356 alertas (148 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 0.931 | 0.602 |
| Recall | 1.000 | 0.893 |
| F1 | 0.964 | 0.719 |
| Tasa de FP | 0.038 | 0.308 |

Matriz prototipo: {'vp': 122, 'fp': 9, 'vn': 225, 'fn': 0}
Matriz baseline: {'vp': 109, 'fp': 72, 'vn': 162, 'fn': 13}

Contenciones automáticas (sin humano): 27 · indebidas (FP/PROPIA): 4 · tasa de escalado al humano: 0.292
