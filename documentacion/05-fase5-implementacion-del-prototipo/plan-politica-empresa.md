# Política de la empresa en un fichero propio — plan de implementación

> **Estado (10/11/2026): pendiente.** Plan anotado a petición del usuario, sin ejecutar. Se implementa
> tarea a tarea con superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans.
> Los pasos usan casillas (`- [ ]`).

**Objetivo:** que las reglas de respuesta de la empresa (quién es de confianza, qué se automatiza, qué no
se toca nunca) vivan en un fichero propio, **`/etc/mdr/politica.yml`**, escrito en términos de negocio,
versionado y con constancia de quién lo aprobó, para que configurar el MDR no exija leer las claves
internas del motor.

**Arquitectura:** el fichero **se traduce** al arrancar a las mismas claves del perfil que hoy lee el
motor (`continuidad`, `excepciones`, `origenes_legitimos`, `automatizacion_por_familia`, …). El motor no
cambia: la traducción es una capa en `motor/perfil.py`. Sin `politica.yml`, todo funciona como hoy. La
consola (vista «Políticas de respuesta») sigue pudiendo **solo endurecer** sobre lo que dice el fichero, y
pasa a mostrar de dónde viene cada valor y qué cambios de consola no están todavía en el fichero.

**Tecnología:** Python 3.9+ (biblioteca estándar) + PyYAML; visor React/TypeScript. Sin dependencias
nuevas.

**Mockup de referencia:** el prototipo desechable «Política de la empresa» (artefacto publicado el
10/11/2026), con la vista Políticas rehecha: franja de la política vigente, origen de cada valor,
pestañas Confianza / Intocables / En castellano y la exportación de cambios como propuesta.

## Decisiones (conversación del 10/11/2026)

| Decisión | Valor |
|---|---|
| Por qué | El perfil mezcla inventario y topología (los mantiene el técnico de red) con la política (la decide Seguridad); y la política está escrita en el idioma del motor |
| Dónde | `/etc/mdr/politica.yml` (variable `TRIAJE_POLITICA`), junto al perfil |
| Formato | YAML en términos de negocio; tres valores de automatización: `sola`, `si_hay_certeza`, `con_analista` |
| Cómo entra al motor | Traducción determinista a las claves actuales del perfil al cargar; el motor no se toca |
| Precedencia | Código (vetos duros) > `politica.yml` > consola (solo endurece) |
| Conflicto con el perfil | Una regla en los dos ficheros es **error** de validación, no «gana uno» |
| Gobierno | Cabecera `politica: { version, aprobada_por, fecha }`; cubre el punto #10 de la hoja de ruta (control de cambios) |
| Descartado | OPA/Rego (otro lenguaje para una tabla), un LLM que lea el documento de políticas (rompe determinismo y auditoría), hoja de cálculo como fuente (pierde la validación) |
| Fuera de alcance | Horarios y ventanas de mantenimiento, aprobadores por rol: serían funcionalidad nueva del motor, no de este fichero |

## Traducción

| `politica.yml` | Clave del perfil que genera |
|---|---|
| `confianza.administradores` | `origenes_legitimos` |
| `confianza.socios_criticos` | `terceros_confiables` |
| `confianza.sospechar_si_rafaga: {alertas, en_segundos}` | `rafaga: {umbral, ventana_s}` |
| `respuesta_automatica.certeza_minima` | `continuidad.umbral_confianza` |
| `respuesta_automatica.por_defecto` | `continuidad.impacto_localizado` |
| `respuesta_automatica.si_afecta_a_un_servicio` | `continuidad.impacto_alcanza_servicio` |
| `respuesta_automatica.solo_observar` | `continuidad.impacto_ninguno` |
| `respuesta_automatica.equipos_propios` | `continuidad.actores.activo_interno` y `.dispositivo_red` |
| `respuesta_automatica.externos_desconocidos` | `continuidad.contener_externos_desconocidos` |
| `respuesta_automatica.por_tipo_de_ataque` | `automatizacion_por_familia` |
| `respuesta_automatica.por_zona` | `politicas_por_zona` |
| `respuesta_automatica.por_equipo` | `overrides_por_activo` |
| `nunca_tocar_en_automatico: [{equipo, servicio}]` | `excepciones: [{activo, servicio, regla: nunca_automatica}]` |
| `desconocidos_graves.revisar_desde_nivel` | `continuidad.revisar_no_soportada_nivel` |

Valores: `sola` → `automatica`, `si_hay_certeza` → `automatica_si_confianza`, `con_analista` →
`humano_siempre`. En familia, zona y equipo solo valen `si_hay_certeza` y `con_analista` (como hoy).
`reversibilidad_obligatoria` y `no_cortar_gestion` **no se exponen**: son siempre `true`.

## Restricciones globales

- Sin `TRIAJE_POLITICA` el comportamiento es **idéntico al actual**; las cifras canónicas no se mueven
  (`evaluacion/tests` 63 OK, mismas métricas).
- El fichero nunca puede abrir lo que el código cierra: plano de gestión, acciones `nunca_automatica`
  del catálogo y familias de freno duro. Si lo intenta, `validar-politica` falla y el servicio no arranca.
- La consola sigue pudiendo solo endurecer (`politica-operativa.yml`, auditado); nada de esta mejora le
  permite añadir automatización.
- Contrato de capas: la traducción vive en `motor/perfil.py` (sin E/S); la lectura del fichero, en
  `servicio/`; las órdenes, en `herramientas/` y `bin/mdr`.

## Tareas

### Tarea 1: traductor y validación
- [ ] `motor/perfil.py`: `traducir_politica(pol: dict) -> dict` (claves del perfil) y
  `validar_politica(pol, perfil) -> list[str]` (claves desconocidas, equipos/zonas/familias inexistentes,
  valores fuera de la tabla, regla repetida en el perfil, intento de abrir un freno duro).
- [ ] `fusionar_perfil_y_politica(perfil, pol) -> dict`: perfil nuevo con lo traducido; error si choca.
- [ ] Pruebas: cada fila de la tabla de traducción; perfil sin política = mismo perfil; choque = error;
  `con_analista` sobre una familia de freno duro = válido, `si_hay_certeza` = error.

### Tarea 2: carga en el servicio
- [ ] `servicio/stream.py`: si `TRIAJE_POLITICA` existe, leerla y fusionarla antes de validar el perfil;
  la cabecera (`version`, `aprobada_por`, `fecha`, hash del fichero) queda en el estado del servicio y se
  anota en la traza al arrancar (registro `politica_cargada`).
- [ ] Pruebas: arranque con y sin fichero; fichero inválido = el servicio no arranca y lo dice.

### Tarea 3: órdenes de `mdr`
- [ ] `mdr validar-politica [fichero]`: avisos en castellano y código de salida.
- [ ] `mdr explicar-politica`: la política efectiva contada en frases («Un intento de acceso a web01
  desde Internet se bloquea solo si la certeza es ≥ 0,9; sobre db01 siempre decide un analista»).
- [ ] `mdr migrar-politica`: extrae del perfil actual las claves de política a un `politica.yml` nuevo y
  las quita del perfil (con copia de seguridad), para las instalaciones existentes.
- [ ] `mdr estado` muestra la versión vigente y si hay cambios de consola sin pasar al fichero.

### Tarea 4: API
- [ ] `GET /api/politica` añade `origen` por fila (`codigo` | `fichero` | `consola` | `por_defecto`), la
  cabecera de la política y la lista de diferencias consola↔fichero.
- [ ] `GET /api/politica/explicar` (texto de `explicar-politica`) y
  `GET /api/politica/propuesta` (YAML de la política con los cambios de consola aplicados y
  `version + 1`, para que Seguridad lo apruebe). Solo lectura: **no** escribe `politica.yml`.

### Tarea 5: vista «Políticas de respuesta»
- [ ] Franja superior con la política vigente (versión, quién la aprobó, fecha, validación).
- [ ] Cada valor con su origen; los cambios de consola con autor, hora y «volver a la política».
- [ ] Pestañas nuevas: Confianza, Intocables y «En castellano».
- [ ] Aviso de diferencias y botón «Exportar como propuesta» (descarga el YAML).
- [ ] Pruebas del visor para cada estado (sin fichero, con fichero, con diferencias).

### Tarea 6: instalación y documentación
- [ ] `deploy/politica.ejemplo.yml` comentado; `instalar.sh` lo copia si no existe; `mdr configurar`
  pregunta por los administradores y socios críticos.
- [ ] Manual de producción: sección «La política de la empresa» (quién la escribe, cómo se aprueba,
  cómo se aplica). Manual de usuario: la vista Políticas actualizada.

## Fuera de este plan (a propósito)

- Horarios, ventanas de mantenimiento y aprobadores por rol.
- Escribir `politica.yml` desde la consola: la consola propone, Seguridad aprueba y el técnico instala.
- Importar desde hoja de cálculo.
