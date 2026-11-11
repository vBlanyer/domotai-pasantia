# Tabla comparativa — perfil bancario
n = 45 alertas (42 soportadas)  ·  baseline en su umbral optimo (nivel >= 3)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 0.952 | 0.889 |
| Recall | 1.000 | 1.000 |
| F1 | 0.976 | 0.941 |
| Tasa de FP | 0.400 | 1.000 |

Matriz prototipo: {'vp': 40, 'fp': 2, 'vn': 3, 'fn': 0}
Matriz baseline: {'vp': 40, 'fp': 5, 'vn': 0, 'fn': 0}

Contenciones automáticas (sin humano): 18 · indebidas (FP/PROPIA): 1 · tasa de escalado al humano: 0.467
