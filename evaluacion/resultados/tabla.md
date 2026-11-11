# Tabla comparativa — perfil empresarial
n = 417 alertas (209 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 0.931 | 0.702 |
| Recall | 0.667 | 0.929 |
| F1 | 0.777 | 0.800 |
| Tasa de FP | 0.038 | 0.308 |

Matriz prototipo: {'vp': 122, 'fp': 9, 'vn': 225, 'fn': 61}
Matriz baseline: {'vp': 170, 'fp': 72, 'vn': 162, 'fn': 13}

Contenciones automáticas (sin humano): 27 · indebidas (FP/PROPIA): 4 · tasa de escalado al humano: 0.249
