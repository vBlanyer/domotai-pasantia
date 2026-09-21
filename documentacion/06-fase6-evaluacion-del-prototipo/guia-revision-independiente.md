# Guía para la revisión independiente

Gracias por revisar esto. El prototipo recibe las alertas de un SIEM, decide cuáles son ataques
reales, lo explica y propone una contención (por ejemplo, bloquear una IP). Las cifras automáticas ya
están medidas. Lo que falta es lo que solo puede juzgar una persona que **no** ha construido el
sistema:

1. si las explicaciones que da son buenas, y
2. qué haría un analista con las decisiones que el sistema no se atreve a tomar solo.

Son dos hojas de cálculo. Calcula **alrededor de hora y media** en total. Muchas filas se parecen
entre sí, y eso es normal: el laboratorio repite los mismos ataques con variaciones.

## Antes de empezar

- **Revisa solo.** No lo consultes con quien construyó el sistema hasta haber terminado. Si una fila
  no se entiende, eso es un resultado: anótalo en el comentario.
- **No busques la respuesta en otros ficheros.** La segunda hoja no lleva la etiqueta verdadera a
  propósito, para medir tu decisión y no la del dataset.
- **Deja en blanco lo que no sepas juzgar.** Una casilla vacía no cuenta; una respuesta a ciegas, sí.
- Abre los ficheros con LibreOffice o Excel. El separador es el **punto y coma**. La primera fila
  resume los criterios.

## La red que estás vigilando

Es la red de una pequeña empresa, montada en un laboratorio. Esto es lo que sabría el analista del
turno:

| Equipo | IP | Qué es |
|---|---|---|
| borde | 192.168.1.1 | El router de salida. También es desde donde **administra** la empresa: su actividad es legítima salvo que sea anómala |
| puesto | 192.168.1.10 | El ordenador de un empleado |
| iot | 192.168.1.20 | Un dispositivo IoT con panel web |
| objetivo-vuln | 192.168.1.30 | Un servidor con servicios expuestos (SSH y web, y bastantes más sin reconocer) |
| auditor | 172.20.20.4 | El escáner del propio servicio de seguridad; desde aquí se ejecutan las contenciones |

Una **ráfaga** son muchas alertas del mismo origen en un minuto. A partir de 9, el sistema la trata
como ataque aunque venga de un origen de administración (podría estar suplantado o comprometido).

## Hoja 1 — Justificaciones

Fichero: `evaluacion/resultados/revision-manual.csv` (106 filas).

Cada fila es una alerta, la clase que decidió el sistema (`clase_motor`) y el texto con el que lo
explica (`justificacion`). Hay dos clases:

- `vp_intento_acceso`: un intento real de acceso no autorizado.
- `fp_actividad_legitima`: la alerta no es un ataque; es actividad esperada (administración o auditoría).

No juzgas si la clase es correcta, sino **si el texto explica bien esa clase**. Marca `s` o `n` en
cada columna:

| Columna | `s` si… | `n` si… |
|---|---|---|
| **CORRECTA** | el texto explica por qué se tomó *esa* decisión | habla de otra cosa, o es tan genérico que valdría para cualquier alerta |
| **ANCLADA** | todo lo que cita está en la fila (origen, activo, servicio, regla, ráfaga) | inventa datos o trae hechos que no aparecen |
| **COHERENTE** | no contradice la clase ni el motivo real | dice lo contrario de lo que se decidió |

Ejemplos (inventados, no están en la hoja). Alerta: origen 192.168.1.10, activo objetivo-vuln, ssh.

| Clase | Texto | CORRECTA | ANCLADA | COHERENTE |
|---|---|---|---|---|
| vp_intento_acceso | «Desde 192.168.1.10 hay intentos repetidos de acceso SSH contra objetivo-vuln, que tiene SSH expuesto: es un intento de acceso.» | s | s | s |
| vp_intento_acceso | «El atacante, una IP conocida de una botnet rusa, intenta entrar por SSH.» | s | **n** (nada en la fila dice eso) | s |
| vp_intento_acceso | «SSH es un protocolo cifrado muy usado para administrar servidores.» | **n** (no explica la decisión) | s | s |
| fp_actividad_legitima | «Posible fuerza bruta; conviene bloquear el origen.» | **n** | s | **n** (dice que es un ataque) |

## Hoja 2 — Decisiones que el sistema te pasaría a ti

Fichero: `evaluacion/resultados/revision-escalados.csv` (24 filas).

Son decisiones en las que el sistema **no actúa solo** y pide validación, sea porque duda (confianza
baja) o porque la contención afectaría a un equipo de la propia empresa. La columna
`lo_que_ve_el_analista` es exactamente la pantalla que saldría en el turno. La línea
**Consecuencia** dice a quién bloquearía la acción y qué dejaría de funcionar.

Rellena:

| Columna | Qué poner |
|---|---|
| **DECISION** | `aprobar` (ejecutar la acción propuesta), `rechazar` (no hacer nada) o `reclasificar` (la clase está mal y no se ejecuta). Vale también `1`, `2` o `3` |
| **CLASE_NUEVA** | Solo si reclasificas: `fp_actividad_legitima`, `fp_exposicion_inexistente` (el servicio atacado no está expuesto) o `no_soportada` |
| **PREGUNTAR_BIEN** | `s` si hizo bien en pedirte permiso; `n` si podía haberlo hecho sin ti |
| **INFO_SUFICIENTE** | `s` si con lo que se muestra pudiste decidir; `n` si te faltó algo, y en ese caso di qué en el comentario |
| **comentario** | Libre. Lo más útil: lo que te hizo dudar |

Decide como lo harías en un turno real. Aprobar el bloqueo del ordenador de un empleado o del router
tiene coste; rechazar un ataque real, también. No hay respuesta «de examen».

## Cuando termines

Guarda los dos ficheros **con el mismo nombre y formato** (CSV, separador punto y coma) y
devuélvelos. Quien construyó el sistema los puntúa con:

```bash
python3 -m evaluacion.puntuar_revision
```

Eso cruza tus decisiones de la hoja 2 con la etiqueta verdadera y deja el resumen en
`evaluacion/resultados/revision-independiente.md`.
