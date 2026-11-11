# Almacenamiento en PostgreSQL — plan de implementación

> **Para quien lo ejecute:** se implementa tarea a tarea con superpowers:subagent-driven-development
> (recomendado) o superpowers:executing-plans. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** que el MDR guarde todo lo que decide (ataques, familias, campañas, equipos, contenciones,
casos, auditoría) en PostgreSQL, preparado para volumen bancario, protegido y fácil de migrar, sin que la
contención dependa nunca de la base de datos.

**Arquitectura:** la traza JSONL encadenada y firmada sigue siendo la **evidencia y la fuente de verdad**;
pasa a rotarse por mes con la cadena continua. Un **proyector** lee la traza desde un punto de control y
la vuelca en PostgreSQL de forma idempotente (por hash). La consola y los informes consultan PostgreSQL;
sin base de datos configurada, todo sigue funcionando como hoy (laboratorio y pruebas). La base de datos
se puede reconstruir entera reproduciendo la traza: eso es también la vía de migración.

**Tecnología:** Python 3.9+ (biblioteca estándar) + PyYAML + **psycopg2** (única dependencia nueva;
`python3-psycopg2` existe en Debian, Ubuntu y Red Hat); PostgreSQL 14 o superior (particionado
declarativo); SQL estándar en migraciones versionadas.

**Diseño:** no hay documento aparte; las decisiones se tomaron en la conversación del 10/11/2026 y están
recogidas aquí:

| Decisión | Valor |
|---|---|
| Dónde vive PostgreSQL | En el servidor que indique el cliente (su BD o una gestionada tipo RDS); `instalar.sh` puede montar uno local para clientes pequeños |
| Fuente de verdad | La traza JSONL firmada; la BD es una proyección reconstruible |
| Si la BD cae | La contención sigue; el proyector se pone al día al volver |
| Volumen de referencia | 5.000 decisiones/día por cliente (≈1,8 M/año), sin cambios de diseño hasta 50.000/día |
| Identificador de decisión | Entero que crece por instalación (`1042`), sin prefijo. Los registros que no son decisiones no se inventan un id: llevan en `id_decision` la decisión a la que se refieren (o `null`) y su identidad es su hash. Si un día se centralizan varias instalaciones, la clave sería `(instalación, id_decision)` |

## Restricciones globales

- La contención **nunca** espera a la BD: el daemon escribe la traza y sigue; proyectar es asíncrono.
- La traza es la única fuente de verdad: todo lo que hay en la BD se puede regenerar desde ella.
- Sin `TRIAJE_PG` el comportamiento es **idéntico al actual** (laboratorio, pruebas, CI sin BD).
- Las cifras canónicas de evaluación no se mueven: `evaluacion/tests` sigue dando 63 OK y las mismas métricas.
- Dependencias: biblioteca estándar + PyYAML + psycopg2. Nada más.
- Contrato de capas (`prototipo/tests/test_arquitectura.py`): el código nuevo vive en `servicio/` y `herramientas/`; ninguna capa interior importa `psycopg2`.
- Contraseñas nunca en `triaje.env` en claro: la conexión usa `TRIAJE_PG` (cadena de conexión **sin** contraseña) + fichero `pgpass` 0600 (mecanismo estándar de libpq).
- Conexión cifrada obligatoria fuera de loopback: `sslmode=verify-full` (con `sslrootcert`); `require` no basta.
- Nombres, textos y mensajes en español, como el resto del producto.

## Atención en la revisión

Casos que el plan implica y que un revisor debe ver cubiertos (cada uno tiene su prueba en la tarea indicada):

1. **La BD cae durante horas y vuelve:** el proyector se pone al día sin perder ni duplicar registros (Tarea 5, `test_bd_caida_y_vuelta_no_pierde_ni_duplica`).
2. **Cambio de mes con contenciones activas:** siguen activas, visibles y revertibles tras la rotación y tras reiniciar (Tarea 3, `test_contencion_de_octubre_sigue_activa_en_noviembre`).
3. **Traza manipulada:** el proyector se detiene en el registro roto y avisa; no vuelca datos alterados (Tarea 5, `test_cadena_rota_detiene_la_proyeccion`).
4. **Paridad:** con y sin BD, la consola da las mismas cifras para la misma traza (Tarea 6, `test_paridad_metricas_con_y_sin_bd`).
5. **Dos escritores en el cambio de mes** (daemon + `revertir` desde la línea de órdenes): la cadena sigue continua (Tarea 2, `test_rotacion_con_dos_escritores_no_rompe_la_cadena`).

## Estructura de ficheros

| Fichero | Responsabilidad |
|---|---|
| `prototipo/servicio/traza.py` (modificar) | Rotación mensual, registro `inicio_segmento`, verificación de la familia de segmentos |
| `prototipo/servicio/secuencia.py` (crear) | Identificadores de decisión únicos que continúan tras reiniciar y rotar |
| `prototipo/accion/contenciones.py`, `prototipo/accion/revertir.py` (modificar) | Identidad de una contención por hash, no por índice |
| `prototipo/migraciones/0001_esquema_inicial.sql` … (crear) | Esquema versionado (SQL estándar) |
| `prototipo/servicio/almacen.py` (crear) | Conexión, migraciones y consultas a PostgreSQL |
| `prototipo/servicio/proyector.py` (crear) | Traza → PostgreSQL con punto de control, idempotente |
| `prototipo/servicio/tablero.py` (modificar) | Lecturas de la consola desde el almacén si está configurado |
| `prototipo/herramientas/bd.py` (crear) | Órdenes `mdr migrar`, `mdr reconstruir-bd`, `mdr podar-bd`, `mdr bd` |
| `bin/mdr`, `deploy/*`, `prototipo/herramientas/{configurar,estado_instalacion}.py` (modificar) | Instalación, configuración y comprobación de la BD |
| `prototipo/tests/test_*.py` (crear/modificar) | Una batería por tarea; las de integración usan `TRIAJE_PG_PRUEBA` |

**Pruebas de integración:** necesitan una BD desechable. `TRIAJE_PG_PRUEBA` (cadena de conexión a una BD
de pruebas que se puede vaciar). Sin ella se omiten **con aviso visible**; la CI (Tarea 9) las ejecuta
siempre con un servicio PostgreSQL.

---

### Tarea 1: identificadores de decisión numéricos y únicos

Hoy `id_decision` es `s{n}` y `n` vuelve a 1 en cada arranque (`stream.py`, `seq = [0]`): con una traza
fija que sobrevive a reinicios, dos decisiones distintas comparten id y los casos se mezclan. Además, el
campo se reutiliza para registros que no son decisiones (`s1042~sup`, `s1042~tope`, `conectividad~…`), lo
que obliga a que sea texto. Será la clave en la BD.

**Ficheros:** crear `prototipo/servicio/secuencia.py`; modificar `prototipo/servicio/stream.py` (inicialización de `seq` y su uso en la línea ~831; registro de supresión ~199; registro de tope ~294), `prototipo/servicio/conectividad_web.py` (`_auditar`), `prototipo/servicio/casos.py` (claves de caso), `prototipo/servicio/tablero.py` (rutas `/api/traza/<id>` y `/api/caso/<id>`), `visor/src/api.ts` y los usos de `id_decision` en el visor; tests `prototipo/tests/test_secuencia.py` y las suites afectadas.

**Interfaces:**
- Produce:
  - Una decisión nueva lleva `"id_decision": <int>` (1, 2, 3…, sin prefijo), que continúa tras reiniciar.
  - Los registros derivados llevan en `id_decision` la decisión a la que se refieren (supresión, tope, reversión, actualización de caso) o `null` (auditoría de Conectividad); el tipo lo dice `tipo`.
  - `secuencia.numero_de(id) -> int | None`: normaliza un id antiguo o nuevo (`1042` → 1042; `"s1042"` → 1042; `"s1042~sup"` → 1042; `"d4"`, `"conectividad~…"`, `"inc:203.0.113"`, `None` → `None`).
  - `secuencia.siguiente_desde(registros: list[dict]) -> int`: el mayor `numero_de(id_decision)` de las decisiones, más 1; 1 si no hay ninguna.
  - Casos: el de una decisión se identifica por su número; el de una campaña sigue siendo `inc:<prefijo/24>`. `/api/caso/<id>` y `/api/traza/<id>` aceptan `1042` y, mientras convivan trazas antiguas, `s1042`.
  - El triaje por lotes de la evaluación (`triaje_lote.py`, `lazo.py`: `d{i}`) **no cambia**: no llega a producción y así las cifras canónicas no se mueven.

- [ ] **Paso 1: tests que fallan**
  - `test_numero_de_ids_nuevos_y_antiguos`: `numero_de(1042) == 1042`, `numero_de("s1042") == 1042`, `numero_de("s1042~sup") == 1042`, `numero_de("d4") is None`, `numero_de("conectividad~x") is None`, `numero_de(None) is None`.
  - `test_vacia_empieza_en_1`: `siguiente_desde([]) == 1`.
  - `test_continua_tras_el_mayor_mezclando_formatos`: decisiones con `s3`, `7`, `s5` → `8`.
  - En `test_stream.py`, `test_reinicio_no_repite_ids`: el daemon dos veces sobre la **misma** traza con una alerta cada vez → `id_decision` `1` y `2`, enteros.
  - `test_supresion_apunta_a_su_decision`: la repetición suprimida se registra con `tipo == "actividad_suprimida"` e `id_decision == 1` (la decisión recordada), no con `"1~sup"`.
  - En `test_conectividad_web.py`: el registro `auditoria_conectividad` lleva `id_decision is None`.
  - En `test_tablero.py`: `/api/caso/1` y `/api/caso/s1` devuelven el mismo caso sobre una traza que mezcla ambos formatos.
  - Visor: `parsearDecision` acepta `id_decision` numérico y de texto; se muestra «Decisión 1042».
- [ ] **Paso 2:** `python3 -m unittest prototipo.tests.test_secuencia prototipo.tests.test_stream prototipo.tests.test_tablero prototipo.tests.test_conectividad_web` y `npx vitest run` → FALLAN.
- [ ] **Paso 3:** implementar. Todo lo que lee ids (`casos.estado_de_casos`, `MemoriaDecisiones.desde_traza`, `contenciones`, la cronología y las tablas del visor) compara por `numero_de(...)`, no por el texto.
- [ ] **Paso 4:** todas las suites Python y del visor → OK; `evaluacion/tests` 63 OK con las mismas cifras; lint en su línea base.
- [ ] **Paso 5:** commit `feat: identificadores de decisión numéricos que no se repiten tras reiniciar`.

### Tarea 2: rotación mensual de la traza con la cadena continua

**Ficheros:** modificar `prototipo/servicio/traza.py` (`Cadena`, `familia`, `leer_familia`, `_main --verificar`) y `prototipo/servicio/retener_trazas.py`; test `prototipo/tests/test_traza_rotacion.py`.

**Interfaces:**
- Consume: Tarea 1 (`secuencia.siguiente_desde`, para el `siguiente_id` de la cabecera).
- Produce:
  - Segmentos: el activo es `<base>.jsonl`; al rotar se renombra a `<base>.<AAAAMM>.jsonl` (solo dígitos, así que `traza.familia()` ya lo ordena).
  - `Cadena(…, rotar_por_mes: bool = False)`: antes de escribir el primer registro de un mes nuevo, cierra el segmento y abre uno nuevo cuyo **primer registro** es `{"tipo": "inicio_segmento", "segmento": "AAAAMM", "hash_segmento_anterior": <último hash>, "n_previos": <n>, "siguiente_id": <int>, "estado": {...}}`, encadenado con `hash_previo = último hash del segmento anterior`. `estado` lo rellena la Tarea 3; aquí, `{}`.
  - `traza.verificar_familia(ruta) -> dict` (`{ok, roto_en: (segmento, indice) | None, motivo}`): recorre los segmentos en orden y exige continuidad entre ellos.
- Decisión: el mes es el de la hora UTC del reloj del daemon al escribir, no el `timestamp` de la alerta (una alerta atrasada no reabre un mes cerrado).

- [ ] **Paso 1: tests que fallan**
  - `test_rota_al_cambiar_de_mes`: con un reloj inyectado, un registro el 31/10 23:59 y otro el 01/11 00:00 → existen `t.202610.jsonl` y `t.jsonl`; el primero del activo es `inicio_segmento` con `segmento == "202611"`.
  - `test_cadena_continua_entre_segmentos`: `verificar_familia(...)["ok"] is True`; si se altera el último registro de octubre → `ok is False` y `roto_en[0] == "202610"`.
  - `test_rotacion_con_dos_escritores_no_rompe_la_cadena`: dos `Cadena(ruta=…)` sobre el mismo fichero (daemon y CLI) escriben alternadamente cruzando el cambio de mes → `verificar_familia` OK y un solo `inicio_segmento` por mes.
  - `test_sin_rotar_por_mes_no_cambia_nada`: `rotar_por_mes=False` → un solo fichero (compatibilidad con el laboratorio y la evaluación).
  - En `test_retener_trazas.py`: `test_poda_segmentos_cerrados_y_nunca_el_activo` (con `--max-meses 12` conserva 12 segmentos cerrados y el activo).
- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar. La rotación se hace dentro del `flock` de `Cadena.escribir` (renombrar + abrir el nuevo + escribir la cabecera), para que el segundo escritor vea el segmento nuevo al resincronizar. `retener_trazas` gana `--max-meses N`. El daemon activa `rotar_por_mes=True` solo con `--salida` fija en producción (`TRIAJE_ROTAR_TRAZA=1`, por defecto activo en `triaje.env.ejemplo`).
- [ ] **Paso 4:** todas las suites Python → OK.
- [ ] **Paso 5:** commit `feat(traza): rotación mensual con la cadena continua entre segmentos`.

### Tarea 3: el estado operativo cruza la rotación (contenciones por hash)

Hoy una contención se identifica por su índice en el fichero y `revertir_una` recibe ese índice. Con
segmentos, el índice deja de ser único y una contención de octubre no estaría en el segmento de noviembre.

**Ficheros:** modificar `prototipo/accion/contenciones.py` (`activas`), `prototipo/accion/revertir.py` (`revertir_una`, `revertir_todas`), `prototipo/servicio/stream.py` (`MemoriaDecisiones.desde_traza`, arranque), `prototipo/servicio/tablero.py` (`POST /api/revertir`), `visor/src/api.ts` y la vista de Contenciones; tests en `test_contenciones.py`, `test_revertir.py`, `test_traza_rotacion.py`, `visor/src/contenciones.test.ts`.

**Interfaces:**
- Consume: Tarea 2 (`inicio_segmento.estado`).
- Produce:
  - `contenciones.activas(registros, catalogo, arrastradas=())` devuelve cada contención con `"hash"` (el de su registro de decisión) además de `"indice"`; `arrastradas` son las que vienen del `estado` de la cabecera del segmento.
  - Reversiones nuevas llevan `"hash_revertido"`; las antiguas con `indice_revertido` se siguen respetando al leer.
  - `revertir_una(ruta, hash, …)` (antes `indice`); `POST /api/revertir {hash, confirmar}` (se sigue aceptando `indice` durante una versión, marcado como obsoleto en la referencia de la API).
  - `inicio_segmento.estado = {"contenciones": [...activas al cerrar...], "supresion": <MemoriaDecisiones serializada>, "siguiente_id": n}`.
  - Al arrancar, el daemon lee **solo el segmento activo** y su cabecera.

- [ ] **Paso 1: tests que fallan**
  - `test_contencion_de_octubre_sigue_activa_en_noviembre`: contención el 30/10, rotación, reinicio leyendo solo el activo → aparece en `activas(...)` con su `hash`; `revertir_una(ruta, hash, …)` la revierte y desaparece.
  - `test_revertir_por_hash_ignora_indices_repetidos`: dos segmentos con una contención en el índice 3 cada uno → revertir por hash solo toca la elegida.
  - `test_reversion_antigua_por_indice_se_respeta`: una traza antigua con `indice_revertido` sigue sin mostrar esa contención como activa.
  - `test_supresion_cruza_la_rotacion`: una repetición en noviembre de una decisión de octubre se suprime.
  - Visor: la fila de Contenciones envía `{hash}` al revertir.
- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar; `Cadena` pide el estado a un proveedor inyectado (`estado_fn() -> dict`) al rotar, para que `traza.py` no importe `accion/`.
- [ ] **Paso 4:** todas las suites Python y del visor → OK; lint en su línea base.
- [ ] **Paso 5:** commit `feat: las contenciones y la supresión cruzan la rotación de la traza`.

### Tarea 4: esquema de PostgreSQL y migraciones versionadas

**Ficheros:** crear `prototipo/migraciones/0001_esquema_inicial.sql`, `prototipo/servicio/almacen.py`, `prototipo/herramientas/bd.py`; modificar `bin/mdr` (`migrar`), `prototipo/tests/test_arquitectura.py` si hace falta registrar el módulo; tests `prototipo/tests/test_almacen_esquema.py` (integración).

**Interfaces:**
- Produce:
  - `almacen.conectar(dsn: str | None = None)` → conexión psycopg2 (`dsn` por defecto: `TRIAJE_PG`); falla con un mensaje claro si psycopg2 no está instalado.
  - `almacen.migrar(con) -> list[str]` aplica en orden los `NNNN_*.sql` no aplicados (tabla `esquema_version`), cada uno en su transacción; devuelve los aplicados.
  - `almacen.version(con) -> int`.
  - `mdr migrar` (como administrador de la BD) aplica las migraciones.
- Esquema `0001` (todo en el esquema `mdr`):
  - `esquema_version(version int primary key, aplicada_en timestamptz)`.
  - `registros(hash text, hash_previo text, segmento text, linea int, tipo text, ts timestamptz, id_decision bigint, doc jsonb, primary key (hash, ts)) partition by range (ts)`: espejo **íntegro** de la traza (evidencia); `id_decision` = la decisión a la que se refiere o `NULL`. Particiones mensuales creadas por el proyector.
  - `decisiones(id_decision bigint, ts timestamptz, activo text, familia text, clase text, prioridad smallint, confianza real, origen_ip inet, campana cidr, pais char(2), asn text, accion text, contencion text, requiere_humano bool, veredicto text, veredicto_por text, decidido_en timestamptz, espera_humana_s int, hash text, primary key (id_decision, ts)) partition by range (ts)` + índices `(ts)`, `(activo, ts)`, `(familia, ts)`, `(campana, ts)`, `(pais, ts)`.
  - `contenciones(hash text primary key, id_decision bigint, activo text, nodo text, accion text, params jsonb, desde timestamptz, revertida_en timestamptz, revertida_por text)`.
  - `casos(id_decision bigint unique, campana cidr unique, estado text, asignado text, actualizado_en timestamptz, check ((id_decision is null) <> (campana is null)))`: el caso es de una decisión o de una campaña /24, nunca de las dos; las notas se leen de `registros` (`tipo = 'actualizacion_caso'`).
  - `proyector_punto(nombre text primary key, segmento text, offset_bytes bigint, hash_ultimo text, actualizado_en timestamptz)`.
  - Vista materializada `resumen_diario(dia, familia, activo, pais, n, contenidas, fuera_sla)`.
  - Roles: `mdr_admin` (dueño; migra), `mdr_escritor` (INSERT en `registros` y `decisiones`; INSERT/UPDATE en `contenciones`, `casos`, `proyector_punto`), `mdr_lector` (SELECT). En `registros` **nadie** tiene UPDATE ni DELETE: `REVOKE` + disparador que lanza un error (la evidencia no se toca; se retira solo por partición entera, Tarea 8).

- [ ] **Paso 1: tests de integración que fallan** (con `TRIAJE_PG_PRUEBA`; sin ella se omiten avisando)
  - `test_migrar_crea_el_esquema_y_es_idempotente`: `migrar` dos veces → la segunda devuelve `[]`; `version == 1`.
  - `test_registros_no_admite_update_ni_delete`: como `mdr_escritor` y como `mdr_admin`, `UPDATE`/`DELETE` en `mdr.registros` lanzan error.
  - `test_lector_no_puede_escribir`: `INSERT` como `mdr_lector` → error de permisos.
  - `test_sin_psycopg2_mensaje_claro` (unitaria, con el import forzado a fallar): el error menciona `python3-psycopg2`.
- [ ] **Paso 2:** instalar el driver y crear la BD de pruebas (lo hace el usuario con `sudo`):
  `sudo apt install python3-psycopg2` y `sudo -u postgres createuser --createrole $USER && createdb mdr_pruebas`; exportar `TRIAJE_PG_PRUEBA=dbname=mdr_pruebas`. Ejecutar los tests → FALLAN.
- [ ] **Paso 3:** escribir la migración y `almacen.py`.
- [ ] **Paso 4:** tests de integración y la suite completa → OK; `test_arquitectura` OK.
- [ ] **Paso 5:** commit `feat(bd): esquema de PostgreSQL, roles y migraciones versionadas`.

### Tarea 5: el proyector (traza → PostgreSQL)

**Ficheros:** crear `prototipo/servicio/proyector.py`; modificar `prototipo/servicio/stream.py` (lanzarlo en un hilo si hay `TRIAJE_PG`) y `/healthz` en `tablero.py`; tests `prototipo/tests/test_proyector.py` (unitarios con una BD falsa + integración).

**Interfaces:**
- Consume: Tareas 2–4 (`traza.familia`, `almacen.conectar`, esquema).
- Produce:
  - `proyector.filas_de(registro: dict) -> dict` (unitaria, pura): la fila de `decisiones` (o `None` si el registro no es una decisión), con `campana = /24 del origen`, `pais`/`asn` del `enriquecimiento_origen`, e `id_decision = secuencia.numero_de(...)` (las trazas antiguas con `s1042` o `s1042~sup` se proyectan sin reescribirlas).
  - `proyector.proyectar_pendiente(con, ruta_traza, lote=500) -> int`: lee desde `proyector_punto`, verifica la continuidad (`hash_previo` del siguiente == `hash_ultimo`), inserta en lote con `ON CONFLICT DO NOTHING`, aplica reversiones y casos a `contenciones`/`casos`, crea la partición del mes si falta y avanza el punto **en la misma transacción**. Devuelve cuántos registros proyectó.
  - `proyector.Proyector(ruta, dsn).correr()`: bucle con reintento exponencial (1 s → 60 s) si la BD no responde; nunca lanza hacia el daemon.
  - `/healthz` añade `proyector: {retraso_registros, retraso_s, ultimo_error}` (o `null` sin BD).
  - Si la cadena está rota: se detiene, deja `ultimo_error` con el segmento y el índice, y escribe un aviso en la Consola; no proyecta lo siguiente.

- [ ] **Paso 1: tests que fallan**
  - `test_filas_de_una_decision` (unitaria): de un registro de decisión de fixture → `activo`, `familia`, `campana == "203.0.113.0/24"`, `pais == "US"`.
  - `test_filas_de_lo_que_no_es_decision`: `auditoria_conectividad`, `actividad_suprimida` → `None` en `decisiones` (pero sí van a `registros`).
  - `test_traza_antigua_con_prefijo_s`: un registro con `"id_decision": "s1042"` se proyecta con `id_decision = 1042`, y uno con `"s1042~sup"` va a `registros` con `id_decision = 1042`.
  - `test_proyecta_y_es_idempotente`: proyectar dos veces → mismas filas; segunda vez devuelve 0.
  - `test_bd_caida_y_vuelta_no_pierde_ni_duplica`: conexión que falla en mitad de un lote → reintento; al final, `count(*)` de `registros` == registros de la traza y ningún hash repetido.
  - `test_cadena_rota_detiene_la_proyeccion`: un registro alterado en mitad → se proyecta hasta el anterior y `ultimo_error` nombra el registro.
  - `test_reversion_marca_la_contencion`: decisión contenida + reversión → `contenciones.revertida_en` no nulo.
  - `test_el_daemon_no_espera_a_la_bd`: con un DSN a un puerto cerrado, el daemon procesa una alerta y escribe la traza en < 1 s.
- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** suites completas → OK.
- [ ] **Paso 5:** commit `feat(bd): proyector de la traza a PostgreSQL con punto de control`.

### Tarea 6: la consola y los informes leen de PostgreSQL

**Ficheros:** modificar `prototipo/servicio/tablero.py` (las lecturas de `/api/decisiones`, `/api/trazas`, `/api/metricas`, `/api/contenciones`, `/api/caso/<id>`, `/api/red` y `/api/pendientes` en lo que toca a histórico) y `prototipo/servicio/almacen.py` (consultas); test `prototipo/tests/test_almacen_consultas.py` (integración).

**Interfaces:**
- Consume: Tareas 4–5.
- Produce, en `almacen.py`, con la **misma forma de respuesta** que hoy da `tablero.py` (el visor no cambia):
  - `metricas(con, desde=None, hasta=None) -> dict` (lo que hoy devuelve `tablero.metricas`).
  - `ultimas_decisiones(con, n=50) -> list[dict]`, `trazas_ventana(con, limite) -> list[dict]`.
  - `contenciones_activas(con) -> list[dict]`, `caso(con, id) -> dict`.
  - `actividad_por_equipo(con, desde) -> dict` (para la vista Red).
- Regla: si `TRIAJE_PG` no está configurado o la BD no responde, `tablero.py` usa el camino actual (traza) y la respuesta lleva `"fuente": "traza"`; con BD, `"fuente": "bd"`. La consola funciona igual en ambos casos.

- [ ] **Paso 1: tests que fallan**
  - `test_paridad_metricas_con_y_sin_bd`: con la traza de fixture `prototipo/tests/fixtures/traza_paridad.jsonl` (se crea en este paso con `python3 -m prototipo.servicio.triaje_lote <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl>` sobre las alertas del banco y el perfil `bancario.yml`, más reversiones y casos añadidos con `casos.construir_actualizacion` y `revertir.revertir`; un mes completo y todas las familias), `almacen.metricas(...)` == `tablero.metricas(regs)` campo a campo (salvo `fuente`), con y sin periodo.
  - `test_paridad_contenciones_y_casos`: lo mismo para contenciones activas y para el caso de una decisión con tres actualizaciones.
  - `test_bd_caida_cae_a_la_traza`: con la BD inaccesible, `/api/metricas` responde 200 y `fuente == "traza"`.
  - `test_metricas_de_un_anio_rapidas`: con 1,8 M filas sintéticas cargadas por `COPY`, `metricas(desde=hace 1 año)` tarda < 5 s y la de un mes < 1 s (se omite con aviso si `TRIAJE_PG_PRUEBA_CARGA` no está).
- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar las consultas (agregados desde `resumen_diario` cuando el periodo es de días completos; detalle desde `decisiones`).
- [ ] **Paso 4:** suites Python y del visor → OK.
- [ ] **Paso 5:** commit `feat(bd): la consola y el informe consultan PostgreSQL, con la traza de respaldo`.

### Tarea 7: instalación, configuración y comprobación

**Ficheros:** modificar `deploy/instalar.sh` (dependencia `python3-psycopg2`; opción `--postgres-local`), `deploy/triaje.env.ejemplo` (`TRIAJE_PG`, `TRIAJE_ROTAR_TRAZA`), `deploy/mdr-triaje.service` (si hace falta `After=postgresql.service` en local), `prototipo/herramientas/configurar.py` (pregunta por la BD), `prototipo/herramientas/estado_instalacion.py` (comprobación de la BD), `prototipo/herramientas/bd.py` (`mdr bd`); tests en `test_configurar.py`, `test_estado_instalacion.py`, `test_instalar_sh.py`.

**Interfaces:**
- Consume: Tareas 4–5.
- Produce:
  - `TRIAJE_PG` = cadena de conexión **sin contraseña** (p. ej. `host=bd.cliente dbname=mdr user=mdr_escritor sslmode=verify-full sslrootcert=/etc/mdr/bd-ca.crt`); la contraseña va en `/var/lib/mdr/.pgpass` (0600, del usuario `triaje`).
  - `instalar.sh --postgres-local`: instala PostgreSQL, crea la BD `mdr` con *checksums*, los tres roles, acceso solo por socket local (`peer`) y ejecuta `mdr migrar`.
  - `mdr configurar`: nueva pregunta «Base de datos: 1) ninguna 2) local 3) servidor del cliente», valida la conexión y la versión del esquema antes de guardar.
  - `mdr estado`: punto `bd` (conexión, versión del esquema, retraso del proyector; `fallo` si hay `TRIAJE_PG` y no conecta, `aviso` si el retraso supera 5 min).
  - `mdr bd`: resumen (tamaño, particiones, filas por mes, retraso).

- [ ] **Paso 1: tests que fallan**
  - `test_configurar_bd_del_cliente`: respuestas «3» + cadena → `TRIAJE_PG` guardado sin contraseña; con una cadena que contiene `password=` → se rechaza y se vuelve a preguntar.
  - `test_estado_bd_sin_conexion_es_fallo` y `test_estado_bd_con_retraso_es_aviso`.
  - `test_instalar_postgres_local` (con órdenes simuladas): llama a `createdb … --data-checksums`, crea los tres roles y ejecuta `mdr migrar`.
  - `test_instalar_sin_psycopg2_lo_pide`: falta el driver → «Faltan dependencias» con `python3-psycopg2`.
- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** suites → OK; probar `instalar.sh --postgres-local` en un directorio de prueba como en `test_instalar_sh.py`.
- [ ] **Paso 5:** commit `feat(bd): instalación, configuración y comprobación de la base de datos`.

### Tarea 8: retención, reconstrucción y migración

**Ficheros:** `prototipo/herramientas/bd.py` (`reconstruir`, `podar`, `exportar`), `bin/mdr`; tests en `prototipo/tests/test_bd_herramientas.py` (integración).

**Interfaces:**
- Consume: Tareas 2, 4, 5.
- Produce:
  - `mdr reconstruir-bd`: vacía las proyecciones y el punto de control y reproduce toda la familia de segmentos (la vía para migrar de servidor, de versión o de proveedor: BD nueva vacía + `mdr migrar` + `mdr reconstruir-bd`).
  - `mdr podar-bd --conservar-meses N`: retira las particiones más antiguas que N meses (`DETACH` + `DROP`); por defecto N = 24. Nunca toca los segmentos de la traza (la evidencia se archiva aparte, Tarea 2).
  - `mdr exportar-bd <fichero>`: `pg_dump` del esquema `mdr` en formato personalizado, para llevarlo a otro servidor.

- [ ] **Paso 1: tests que fallan**
  - `test_reconstruir_da_lo_mismo`: proyectar, guardar `metricas()`, `reconstruir-bd`, comparar → idénticas.
  - `test_podar_quita_particiones_viejas_y_no_la_actual`: con 30 meses → quedan 24 y la del mes en curso.
  - `test_reconstruir_tras_migrar_de_servidor`: exportar en una BD, importar en otra vacía, comparar `metricas()`.
- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** suites → OK.
- [ ] **Paso 5:** commit `feat(bd): reconstrucción, retención por particiones y exportación`.

### Tarea 9: CI, rendimiento y documentación

**Ficheros:** `.github/workflows/ci.yml` (servicio PostgreSQL, `TRIAJE_PG_PRUEBA`, instalar `psycopg2`), `prototipo/herramientas/bd.py` (`mdr bd --medir`), `documentacion/07-fase7-documentacion-e-informe-final/manual-de-produccion.md` (sección «Base de datos»), `referencia-api.md` (`id_decision` numérico, `fuente`, `POST /api/revertir {hash}`, `/healthz.proyector`), `RUNBOOK.md`, `CHANGELOG.md`, `documentacion/04-fase4-diseno-de-arquitectura/integracion-en-produccion.md`.

- [ ] **Paso 1:** la CI levanta PostgreSQL y ejecuta las pruebas de integración (que ya no se omiten); comprobar en la ejecución que el número de pruebas omitidas es 0.
- [ ] **Paso 2:** `mdr bd --medir`: carga sintética de 1,8 M decisiones y mide la proyección (objetivo ≥ 2.000 registros/s) y las consultas (mes < 1 s, año < 5 s). Anotar las cifras medidas en el manual.
- [ ] **Paso 3:** manual de producción, sección «Base de datos»:
  - dónde vive (servidor del cliente o local);
  - conexión cifrada con `verify-full`;
  - los tres roles;
  - contraseña en `.pgpass`;
  - cifrado en reposo (disco o servicio gestionado);
  - `pgaudit`;
  - copias continuas con recuperación a un momento dado (WAL + `pg_basebackup`);
  - retención por meses;
  - cómo reconstruir y migrar;
  - qué pasa si la BD cae.

  Añadirla también a las secciones 3, 6, 11, 14 y 31 y a los anexos.
- [ ] **Paso 4:** referencia de la API, RUNBOOK, CHANGELOG (v1.9) e integración en producción; comprobador de enlaces a 0; PDF regenerado.
- [ ] **Paso 5:** commit `docs(bd): base de datos en el manual de producción y la referencia`.

---

## Fuera de este plan (a propósito)

- Almacenes analíticos (ClickHouse, OpenSearch) o un almacén central para un SOC de varios clientes: se alimentarían de la misma traza o de esta BD cuando haga falta.
- Replicación y alta disponibilidad de PostgreSQL: las administra el cliente (o el servicio gestionado); el MDR solo necesita una cadena de conexión.
- Guardar las alertas en bruto: ya las guarda el SIEM; la BD guarda la referencia (`id_alerta`).
