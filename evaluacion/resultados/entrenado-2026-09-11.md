# Clasificador entrenado (arbol CART) frente al determinista

Entrenado con 106 alertas soportadas; medido sobre 106 (particion de evaluacion). Profundidad del arbol: 3.

| Metrica | Determinista (5 reglas) | Arbol entrenado |
|---|---|---|
| Precision | 0.971 | 1.000 |
| Exhaustividad | 0.770 | 0.989 |
| F1 | 0.859 | 0.994 |
| Tasa de FP | 0.105 | 0.000 |

Matriz determinista: {'vp': 67, 'fp': 2, 'vn': 17, 'fn': 20}
Matriz arbol: {'vp': 86, 'fp': 0, 'vn': 19, 'fn': 1}

## Aciertos por procedencia de la etiqueta

| Etiqueta (por) | n | determinista | arbol |
|---|---|---|---|
| campaña/FP | 4 | 2/4 | 4/4 |
| campaña/VP | 60 | 40/60 | 60/60 |
| regla/FP | 15 | 15/15 | 15/15 |
| regla/VP | 27 | 27/27 | 26/27 |

## El arbol, como reglas

```
si n_origen_60s <= 8.5:
    si origen_legitimo == False:
        si regla_id == '5602':
            -> VP  (n=7, {'VP': 7})
        si no (regla_id != '5602'):
            -> FP  (n=3, {'FP': 2, 'VP': 1})
    si no (origen_legitimo != False):
        -> FP  (n=17, {'FP': 17})
si no (n_origen_60s > 8.5):
    -> VP  (n=79, {'VP': 79})
```
