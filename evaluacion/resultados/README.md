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

## Corridas con modelo de 8B (10/09/2026)

Tras rehacer la capa de invocacion (servidor residente) y con un modelo generalista de ocho mil
millones de parametros (`llama-3.1-8b-instruct-q4.gguf`):

| Directorio / fichero | Que contiene | Estado |
|---|---|---|
| `8b-sin-rag/` | Campana sin recuperacion. 18/18 ancladas, 0 degradadas | Vigente (`llm-3`) |
| `8b-con-rag/` | Campana con recuperacion, corpus y consulta dependientes de la clase. 18/18 ancladas, 0 degradadas, **0 contradicciones**, 50 s | **Vigente (`llm-4`)** |
| `rag-simulacion-2026-09-10.md` | Banco de calibracion con el 1B como embedder. Fija MRR 0.47, agentica 0.32 | Historico |
| `rag-simulacion-2026-09-10-bge.md` | Banco con bge-m3 como embedder y generacion reproducible. Fija MRR 0.70, agentica 0.73 | **Vigente** |
| (sin fichero; medido en memoria) | Crecer el corpus 32 -> 40 fichas con tecnicas hermanas, embedder bge-m3: MRR 0.70 -> 0.66, Hit@5 1.00 en ambos. Con el 1B era 0.41 -> 0.19. Detalle en `docs/pruebas/06-rendimiento-y-hardware.md` | Vigente |

La clasificacion es identica en todas las corridas, como debe ser: el modelo no participa en ella.
Lo que cambia es la justificacion.

### La tasa de anclaje de `8b-con-rag/` paso por tres estados, y el mismo numero significo dos cosas

| Estado | Version | Anclaje | Contradicciones con el motor | Descartes en plantilla | Donde |
|---|---|---|---|---|---|
| Enunciado ciego a la clase | `llm-2` | 18/18 (1,00) | **8 de 8** falsos positivos explicados como ataque | 0 | historial, `9a2db51` |
| Enunciado por clase, corpus solo de ataque | `llm-3` | 11/18 (0,61) | 0 | 7 de 8 | historial, `ac36a92` |
| Enunciado, consulta y corpus por clase | `llm-4` | 18/18 (1,00) | 0 | 0 | `8b-con-rag/` |

El primer 1,00 era vacio: la justificacion citaba todos los campos y contradecia la decision. El
0,61 fue una mejora: desaparecieron las contradicciones a costa de que los descartes cayeran a la
plantilla, porque el corpus no tenia nada que explicara por que algo NO es una amenaza. El segundo
1,00 se obtuvo anadiendo tres fichas de descarte al corpus, haciendo que la consulta de recuperacion
dependa de la clase decidida y separando el corpus en dos familias que no se mezclan (una amenaza
no ve fichas de descarte; un descarte no ve fichas de ataque). Las 18 justificaciones se leyeron una
a una: los descartes citan el motivo real (el origen figura como administracion declarada) y las
amenazas citan origen, activo y servicio expuesto. El desglose por clase esta en el JSON
(`anclaje.resumen.por_clase`).

### Reproducibilidad del banco (RNF-03)

Con la cache de prefijos del `llama-server` activa, el mismo prompt a temperatura 0 devolvia
consultas distintas segun lo que el servidor habia procesado antes: 4 de las 12 consultas
agenticas del banco cambiaban tras correr una campana, y el MRR agentico oscilo entre 0,72 y 0,81
sin que cambiara ni el codigo ni el corpus. El generador ya envia `cache_prompt: false`; se
verifico que con eso el banco da cifras identicas antes y despues de una campana. **Las cifras
agenticas anteriores a `llm-4` (0,72 en el commit `20b88e7`) eran dependientes del estado del
servidor y no deben citarse.** La consulta fija nunca tuvo este problema: no pasa por el
generador.

**Por que no se uso el modelo especializado en seguridad** que selecciono la Fase 4: sus dos
cuantizaciones publicas declaran plantillas de conversacion que no corresponden a su arquitectura, y
producen repeticion del enunciado o fuga de marcas de control. Se midio con un modelo generalista de
referencia, lo que aisla el efecto del tamano pero deja sin comprobar el de la especializacion.

```bash
# Con el servidor residente arrancado (lab/scripts/llm-server.sh):
python3 -m evaluacion.campana --particion evaluacion --con-rag --generador servidor --salida-dir evaluacion/resultados/8b-con-rag
python3 -m evaluacion.simular_ataques_rag --salida-dir evaluacion/resultados
```
