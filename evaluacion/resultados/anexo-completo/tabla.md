# Tabla comparativa — perfil empresarial
n = 813 alertas (397 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 0.931 | 0.690 |
| Recall | 0.707 | 0.925 |
| F1 | 0.804 | 0.791 |
| Tasa de FP | 0.038 | 0.306 |

Matriz prototipo: {'vp': 244, 'fp': 18, 'vn': 450, 'fn': 101}
Matriz baseline: {'vp': 319, 'fp': 143, 'vn': 325, 'fn': 26}

Contenciones automáticas (sin humano): 54 · indebidas (FP/PROPIA): 8 · tasa de escalado al humano: 0.256
