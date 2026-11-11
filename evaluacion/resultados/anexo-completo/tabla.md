# Tabla comparativa — perfil empresarial
n = 712 alertas (296 soportadas)  ·  baseline en su umbral optimo (nivel >= 5)

| Metrica | Prototipo | Baseline (Wazuh @optimo) |
|---------|-----------|--------------------------|
| Precision | 0.931 | 0.604 |
| Recall | 1.000 | 0.893 |
| F1 | 0.964 | 0.721 |
| Tasa de FP | 0.038 | 0.306 |

Matriz prototipo: {'vp': 244, 'fp': 18, 'vn': 450, 'fn': 0}
Matriz baseline: {'vp': 218, 'fp': 143, 'vn': 325, 'fn': 26}

Contenciones automáticas (sin humano): 54 · indebidas (FP/PROPIA): 8 · tasa de escalado al humano: 0.292
