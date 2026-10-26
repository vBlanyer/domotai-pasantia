# v2 — trabajo aplazado conscientemente (post-entrega)

Este documento es el **único registro de «v2»**: todo lo que se decidió NO hacer antes de la
defensa, con su porqué y dónde está el detalle. Regla: si algo se aplaza, se anota aquí; una
mención suelta a «v2» en otro doc debe enlazar a esta página. (Creado el 26/10/2026 porque las
menciones estaban dispersas y no había dónde buscarlas.)

Nada de esta lista es un requisito pendiente del plan de trabajo: el plan está completo y los
externos están documentados con plantillas en
[requisitos-del-cliente-y-gobernanza.md](../04-fase4-diseno-de-arquitectura/requisitos-del-cliente-y-gobernanza.md).

## Arquitectura del paquete (`prototipo/`)

| Qué | Por qué se aplazó | Detalle |
|---|---|---|
| **Valorar la traza como módulo transversal** — las 2 excepciones restantes del contrato son la misma cuestión: `motor/triaje.procesar` y `accion/revertir` construyen su registro con `servicio/traza` | El contrato ya está garantizado por test con ambas congeladas; es una decisión de diseño, no un hueco. (El otro ítem de esta fila —mover el `main()` batch de `triaje` a `servicio/triaje_lote`— se adelantó el 26/10.) | [`prototipo/tests/test_arquitectura.py`](../../prototipo/tests/test_arquitectura.py) (lista `EXCEPCIONES`) |
| **Nivel 2: partir los dos módulos gordos** — `servicio/stream.py` (~1.140 líneas) en `terminal` / `supresion` / `cli` + el bucle, y `servicio/tablero.py` (~980) en `web_estado` / `web_datos` / `web_http` + fachada | Solo legibilidad; reglas si se hace: el estado a nivel de módulo (caches, locks) viaja ENTERO con su módulo, y los tests que importan privados se actualizan — sin fachadas con estado duplicado | Mapa del paquete en [`prototipo/README.md`](../../prototipo/README.md) |
| **Trocear `prototipo/README.md` (~61 KB)**: raíz corta (mapa + arranque) + un README por capa | Es el fichero más pesado de la raíz, pero es documentación, no riesgo | — |
| Espejar `prototipo/tests/` por capas | Cosmético; `discover` los encuentra igual | — |
| Import-linter formal | El test casero ya da la garantía; la herramienta sería refuerzo menor | `test_arquitectura.py` |

Decisión cerrada (no es pendiente): los YML y `perfiles/`/`corpus/` **se quedan en la raíz del
paquete** — raíz = superficie del integrador (familias, correspondencia, catálogo, perfiles),
capas = código. Analizado con datos el 26/10 (13–15 citas vivas por fichero).

## Plataforma y conector

| Qué | Por qué se aplazó | Detalle |
|---|---|---|
| **Drivers por plano para equipos no-SSH** (REST/NETCONF/SNMP/TR-069/central); `docker exec` como driver de referencia ejercitable | Rollout por tipo de equipo, trabajo por cliente; el patrón y los seams están documentados | [integracion-en-produccion.md §2.6](../04-fase4-diseno-de-arquitectura/integracion-en-produccion.md) |
| ~~Ejecutor SSH directo~~ — **adelantado el 26/10**: `TRIAJE_SSH_MODO=directo` (clave y known_hosts del HOST), validado en vivo contra la demo portátil | — | `prototipo/accion/conector.py` |
| Integración end-to-end con un equipo de borde de firmware real (p. ej. OpenWrt) | Descartada el 06/10 (revertida): el bloqueo en el borde ya funciona; esto es validación extra, no requisito | CHANGELOG / estado-y-riesgos |
| Segunda fuente de alertas (CEF) | Analizada y aparcada el 21/09; decisiones abiertas en su spec | `archivo/proceso-desarrollo/superpowers/specs/` |

## Metodología de evaluación (opcional — descartado para la entrega el 21/10)

| Qué | Por qué se aplazó | Detalle |
|---|---|---|
| **Hold-out con verdad declarada**: campañas nuevas tras congelar reglas (todas las filas `etiqueta_por: campaña`), idealmente en otro entorno (la demo portátil lo habilita) | El usuario descartó la revisión exhaustiva para la entrega; las cifras vigentes valen como consistencia interna | Auditoría 20/10 (hallazgo de circularidad 236/300) |
| **Revisión humana independiente** (106 justificaciones + 24 escaladas; hojas y puntuador listos, ~3–6 h de revisor) | Ídem; regenerar antes la hoja con el justificador vigente | `evaluacion/revision_manual.py`, `revision_escalados.py`, `puntuar_revision.py` |
| Clasificador con ajuste fino | Bloqueado por tamaño del dataset (recomendación #1 del informe) | ip7, recomendaciones |

## Seguridad y visor (residuales aceptados, ya documentados)

- Pentest propio: **#15** (suplantación de origen legítimo — límite de RF-03), **#17** (credenciales
  de laboratorio solo con `TRIAJE_SSH_MODO=password`), **#18** (`llm_claude.py` envía prompts fuera —
  barrera documental, fuera del camino de producción).
- Visor (declinados en la tanda del 20/10): frontera UTC del periodo del informe (va con el tema
  zona→UTC del backend), pausa optimista multi-operador (ventana mínima), y el descarte de un
  registro que no valida se queda con `console.warn` (la alternativa — tirar la lista — es peor).
- Futuro declarado del visor: doble canal y contador en vivo.
