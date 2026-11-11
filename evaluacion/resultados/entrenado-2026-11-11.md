# Clasificador entrenado (arbol CART) frente al determinista

Entrenado con 188 alertas soportadas; medido sobre 209 (particion de evaluacion). Profundidad del arbol: 4.

| Metrica | Determinista (5 reglas) | Arbol entrenado |
|---|---|---|
| Precision | 0.919 | 0.968 |
| Exhaustividad | 0.557 | 1.000 |
| F1 | 0.694 | 0.984 |
| Tasa de FP | 0.346 | 0.231 |

Matriz determinista: {'vp': 102, 'fp': 9, 'vn': 17, 'fn': 81}
Matriz arbol: {'vp': 183, 'fp': 6, 'vn': 20, 'fn': 0}

## Aciertos por procedencia de la etiqueta

| Etiqueta (por) | n | determinista | arbol |
|---|---|---|---|
| campaña/FP | 11 | 2/11 | 9/11 |
| campaña/VP | 156 | 75/156 | 156/156 |
| regla/FP | 15 | 15/15 | 11/15 |
| regla/VP | 27 | 27/27 | 27/27 |

## El arbol, como reglas

```
si n_origen_60s <= 5.5:
    si reglas_60s <= 2.5:
        si familia == 'reconocimiento':
            -> FP  (n=4, {'FP': 4})
        si no (familia != 'reconocimiento'):
            si n_origen_60s <= 2.5:
                -> FP  (n=3, {'FP': 3})
            si no (n_origen_60s > 2.5):
                -> VP  (n=17, {'FP': 3, 'VP': 14})
    si no (reglas_60s > 2.5):
        -> FP  (n=8, {'FP': 8})
si no (n_origen_60s > 5.5):
    si regla_id == '5710':
        si origen_legitimo == False:
            -> VP  (n=29, {'VP': 29})
        si no (origen_legitimo != False):
            -> FP  (n=7, {'FP': 7})
    si no (regla_id != '5710'):
        si nivel_wazuh <= 9:
            -> VP  (n=110, {'VP': 110})
        si no (nivel_wazuh > 9):
            si origen_legitimo == False:
                -> VP  (n=7, {'VP': 7})
            si no (origen_legitimo != False):
                -> VP  (n=3, {'FP': 1, 'VP': 2})
```
