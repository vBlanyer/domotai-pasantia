# Clasificador entrenado (arbol CART) frente al determinista

Entrenado con 148 alertas soportadas; medido sobre 148 (particion de evaluacion). Profundidad del arbol: 4.

| Metrica | Determinista (5 reglas) | Arbol entrenado |
|---|---|---|
| Precision | 0.919 | 0.992 |
| Exhaustividad | 0.836 | 1.000 |
| F1 | 0.876 | 0.996 |
| Tasa de FP | 0.346 | 0.038 |

Matriz determinista: {'vp': 102, 'fp': 9, 'vn': 17, 'fn': 20}
Matriz arbol: {'vp': 122, 'fp': 1, 'vn': 25, 'fn': 0}

## Aciertos por procedencia de la etiqueta

| Etiqueta (por) | n | determinista | arbol |
|---|---|---|---|
| campaña/FP | 11 | 2/11 | 10/11 |
| campaña/VP | 95 | 75/95 | 95/95 |
| regla/FP | 15 | 15/15 | 15/15 |
| regla/VP | 27 | 27/27 | 27/27 |

## El arbol, como reglas

```
si n_origen_60s <= 8.5:
    si familia == 'servicio_expuesto':
        si origen_legitimo == False:
            si n_origen_60s <= 5.5:
                -> VP  (n=7, {'VP': 6, 'FP': 1})
            si no (n_origen_60s > 5.5):
                -> VP  (n=8, {'VP': 8})
        si no (origen_legitimo != False):
            -> FP  (n=3, {'FP': 3})
    si no (familia != 'servicio_expuesto'):
        -> FP  (n=22, {'FP': 22})
si no (n_origen_60s > 8.5):
    -> VP  (n=108, {'VP': 108})
```
