# Resultados de las campañas de evaluación

Salidas generadas por `evaluacion/campana.py`. **Ninguno de estos ficheros se edita a mano**: se
regeneran corriendo la campaña. Los `campana-<fecha>.json` se acumulan por fecha; `tabla.md` siempre
refleja la última corrida de ese directorio.

## Qué hay en cada directorio

| Directorio | Qué mide | Estado de las cifras |
|------------|----------|----------------------|
| `.` (raíz) | Partición de evaluación (205 alertas, 18 soportadas) | **Vigente** — posterior a RF-03 |
| `anexo-completo/` | Partición completa (410 alertas, 36 soportadas); comprueba que no hubo fuga entre entrenar y evaluar | **Vigente** — regenerado el 10/09/2026 |
| `sin-rag/` · `con-rag/` | Contraste del **anclaje de la justificación** con y sin recuperación aumentada | **Históricos (02/09/2026)** — ver la nota de abajo |

## Nota sobre `sin-rag/` y `con-rag/`

Estas dos corridas son **anteriores a RF-03** (la configuración `origenes_legitimos` que distingue al
administrador legítimo del atacante), así que sus columnas de **clasificación** muestran las cifras de
la primera medición —precisión 0.556, F1 0.714, tasa de FP 0.041— y **no** las vigentes.

Se conservan igualmente porque **lo que aportan no es la clasificación, sino el contraste de anclaje y
corrección semántica de la justificación** con y sin RAG, que no cambió con RF-03: el clasificador y el
justificador son componentes independientes detrás de la misma interfaz. La lectura completa de ese
contraste está en el [informe de la Fase 6, §5.bis](../../documentacion/06-fase6-evaluacion-del-prototipo/informe-evaluacion.md).

Regenerarlas exige el modelo local (entorno conda de la Fase 5C) y unos **11 minutos por corrida**, al
recargarse el modelo en cada justificación. Cuando se rehagan sobre el hardware objetivo, sus cifras de
clasificación pasarán a coincidir con las de la raíz.

## Cómo regenerar

```bash
# Vigente: partición de evaluación, sin modelo (segundos)
python3 -m evaluacion.campana --particion evaluacion --sin-llm

# Vigente: partición completa (anexo)
python3 -m evaluacion.campana --particion todas --sin-llm --salida-dir evaluacion/resultados/anexo-completo

# Contraste de justificación (exige el modelo local; ~11 min cada una)
python3 -m evaluacion.campana --particion evaluacion --salida-dir evaluacion/resultados/sin-rag
python3 -m evaluacion.campana --particion evaluacion --con-rag --salida-dir evaluacion/resultados/con-rag
```
