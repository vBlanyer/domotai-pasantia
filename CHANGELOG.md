# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Las **cifras canónicas de la evaluación** (clasificación, priorización, continuidad de v1.0) **no
se mueven** entre versiones: todo lo posterior a v1.0 se diseñó para no alterarlas (ver el informe,
capítulo de resultados, y `evaluacion/resultados/`).

## [No publicado] — posterior a v1.3

### Añadido (visor)
- **Vista «Incidentes» (trabajar por incidente, no por alerta)**: cada incidente es una **campaña de
  origen /24** (las IPs rotadas de un atacante = una sola historia; reutiliza `campanasDe`), con su
  propio **caso** (estado/responsable/notas) a nivel incidente. Reutiliza la maquinaria de casos
  existente (`/api/caso`, `PanelCaso`) con una **clave sintética URL-safe** `inc:<prefijo/24>` (p. ej.
  `inc:203.0.113`), que el prefijo `inc:` separa de los casos por decisión; **cero backend**. Drill-down
  «detalle de incidente» con KPIs, la **línea de tiempo** del incidente y el panel de caso. `PanelCaso`
  se extrajo a su propio módulo para reutilizarlo. Helper `datos.claveIncidenteDe`.
- **Línea de tiempo del incidente/atacante** (`LineaTiempo` + `datos.cronologiaDe`): la cronología de
  un ataque mezclando la **detección** (decisiones) con la **respuesta** (reversión de contención, hitos
  del ciclo de caso), ordenada por tiempo. Helper puro desde el feed; el helper `eventosDeEntidad`
  correlaciona las respuestas (que no llevan `origen_ip`) por el `id_decision` de las decisiones de la
  entidad. Estrenada en el **perfil de atacante**; la reutilizará el detalle de incidente. Sin backend.
- **Vista «Políticas» (playbook de solo lectura)**: por cada familia de amenaza, la clase que representa,
  la acción del **catálogo cerrado** que se propone, su impacto, el nivel de **automatización**
  (automática / auto si confianza / requiere humano / nunca automática) y los vetos/condiciones. Nuevo
  endpoint `GET /api/politica` (`tablero.politica_resumen(catalogo, perfil)`) que deriva el playbook
  **estáticamente** del catálogo + el perfil reutilizando el clasificador real (`analisis.clasificar`) y
  la misma regla de continuidad que el filtro del motor; componente `Politicas.tsx` + `getPolitica`/
  `PoliticaFamiliaSchema`. **Nota honesta**: los matices por actor/IP (terceros de confianza, externo
  desconocido, excepciones por activo) se refinan en tiempo de ejecución y no se reflejan en esta vista
  estática. Solo lectura; no toca el motor ni el canónico.

## [1.3] — 2026-10-28 · Geolocalización de orígenes, demo observable y endurecimiento

Posterior a v1.2: **geolocalización de los orígenes** (mapamundi en «Ubicaciones», métricas en curso/
total/mitigados con conteo sobre los puntos y filtro, hover, y ubicación + filtro por ubicación en
«Aprobaciones»), una **demo de geolocalización observable** sin contenedores, el **cierre de un
fail-open** en la verificación de `MATAR_CONEXION` y el informe al día. No toca el motor de decisión
evaluado, así que las cifras canónicas siguen intactas (v1.3 no re-basa v1.0/v1.1/v1.2).

### Documentación
- **Informe (LaTeX) al día con el estado posterior a v1.2**, sin tocar las cifras canónicas ni el
  capítulo de resultados: conteos de pruebas actualizados en la metodología (motor 1053, evaluación 63,
  dataset 39, banco 156, portátil 14, geolocalización 12, visor 268) y el párrafo del visor en las
  conclusiones ampliado a las **doce vistas** y a las últimas incorporaciones (consola en vivo con el
  porqué y la respuesta paso a paso + diario del operador, Red por dispositivo, geolocalización offline
  sobre mapamundi, campañas, perfil de atacante, watchlist, enriquecimiento con ASN y rDNS opt-in, todo
  **sin egreso**). El resumen (registro congelado de la Fase 6) no se toca. PDF recompilado.

### Añadido (visor)
- **Mapamundi en la vista «Ubicaciones»**: el mapa pasó de una caja con rejilla a un **mapamundi con
  las siluetas de los continentes** (Natural Earth 110m, dominio público), dibujadas como paths SVG
  inline en la MISMA proyección equirectangular que los marcadores (`x = lon+180`, `y = 90−lat`), así
  que los puntos caen sobre el continente correcto. Es un **asset de build** (`visor/src/worldmap.ts`,
  siluetas pre-proyectadas); el producto sigue **sin dependencias ni egreso**.
- **Filtro de métricas en «Ubicaciones» + conteo sobre los puntos**: los marcadores ahora llevan
  **encima el número de ataques** de la métrica elegida, y un filtro de tres valores dimensiona/numera
  el mapa: **En curso** (recibidos aún no contenidos), **Total** (recibidos) y **Mitigados**
  (contención «contenida»). Partición limpia: `total = en curso + mitigados`. La tabla gana las tres
  columnas (resaltando la activa) y los botones muestran las cifras **globales** (todas las ubicaciones,
  incluidas lab/internas de la tabla); el mapa numera solo las geolocalizadas. `datos.ubicacionesDe`
  calcula `mitigados`/`enCurso` por ubicación (additivo, sin tocar el motor).
- **Hover y navegación en «Ubicaciones»**: al pasar el ratón por un punto del mapa sale una **tarjeta**
  que sigue al cursor con el desglose (en curso · total · mitigados · IPs). Las **filas de país** de la
  tabla son **clicables** y pivotan **según el filtro activo**: «En curso» → **Aprobaciones** (la cola a
  atender), «Total»/«Mitigados» → **Decisiones filtradas por ese país** (`filtrarDecisiones` ahora
  también busca el país del enriquecimiento geo). Los números sobre los puntos son `pointer-events-none`
  y no seleccionables (antes el texto interceptaba el hover y se podía copiar).
- **Ubicación del origen en «Aprobaciones» + filtro propio por ubicación**: cada tarjeta de la cola
  muestra ahora la IP, el activo y la **ubicación/alcance** del origen (badges). Aprobaciones tiene un
  **filtro propio** (un selector con las ubicaciones presentes en la cola, «Todas» para quitar) y la
  **ubicación de cada tarjeta es un enlace** (`📍 … · filtrar`) que fija ese filtro; «En curso» desde el
  mapa de Ubicaciones lo **siembra** con ese país. El filtro usa `ubicacionLabelDe` (misma etiqueta que
  el mapa: país real o cubo lab/interna…), así cubre todas las ubicaciones, no solo países. Backend:
  `/api/pendientes` incluye `enriquecimiento_origen` por ítem (`_vista_pendiente(p, perfil)`; mismo shape
  que el feed). El esquema Zod del enriquecimiento se extrajo a `EnriquecimientoOrigenSchema` y se reusa
  en decisiones y pendientes.

## [1.2] — 2026-10-28 · Cobertura de familias, consola MDR y expansión del visor

Posterior a v1.1 (2026-10-14 → 2026-10-28): cobertura de **las 10 familias**, **consola MDR**
(aviso + ciclo de caso + feed vivo con caja negra narrada), gran **expansión del visor** (12 vistas:
geolocalización/Ubicaciones, campañas, perfil de atacante, watchlist, SLA, riesgo, ATT&CK honesta),
enriquecimiento del origen (**ASN offline + rDNS opt-in**), la **demo de geolocalización** sin
contenedores y el cierre del **fail-open de `MATAR_CONEXION`**. No toca el motor de decisión evaluado,
así que las cifras canónicas siguen intactas (v1.2 no re-basa v1.0/v1.1).

### Añadido
- **Familias 6 a 10** (de 5 a **10**), cada una con su patrón de respuesta del catálogo cerrado:
  - integridad de ficheros / FIM → `AISLAR_NODO` (cuarentena en el borde).
  - denegación de servicio / DoS → `LIMITAR_BANDA` (contención gradual).
  - acceso consumado (login tras fuerza bruta) → `MATAR_CONEXION` (cortar la sesión viva).
  - exfiltración / C2 → `BLOQUEAR_DESTINO` (bloquear el egreso al destino en el borde).
  - malware / rootkit → `AISLAR_NODO`.
- **Consola MDR**: aviso al analista (notificación del navegador + distintivo en la pestaña + SLA
  «pendiente desde hace X» en la cola) y **ciclo de vida del caso** (estado nuevo→en revisión→
  resuelto, responsable y notas, como registros `actualizacion_caso` encadenados).
- **Matriz ATT&CK por cobertura de familia** en el visor; el lanzador del banco cubre las 10 familias.
- Escalada a **revisión humana de un `no_soportada` grave** (opt-in del perfil).
- **Barrido del umbral de confianza (RF-07)**: curva escalado↔bloqueos indebidos y su lectura
  (`evaluacion/resultados/barrido-umbral.md`).
- Documentación: `STRUCTURE.md`, cuadro de alcance (§8 de estado-y-riesgos), este `CHANGELOG.md`.

### Cambiado
- Limpieza de estructura: `documentacion/archivo/` → `documentacion/material-superado/`; archivo de
  proceso reubicado; `README`/informe al día (10 familias y cifras de tests actuales).
- **`prototipo/` reorganizado en subpaquetes por capa** (26/10): los 37 módulos viven ahora en
  `entrada/ motor/ accion/ explicacion/ servicio/ herramientas/` (la taxonomía del capítulo de
  arquitectura), con los datos (`perfiles/`, `corpus/`, `*.yml`) en la raíz del paquete. **Los CLIs
  cambian de ruta**: `python3 -m prototipo.servicio.stream`, `prototipo.accion.catalogo --sudoers`,
  `prototipo.herramientas.validar_reglas`, … (scripts, deploy, demos y docs vivos actualizados en la
  misma pasada; los documentos congelados citan las rutas planas antiguas). También: mapa del paquete
  en su README y retirado el dato huérfano `ilustrativas.jsonl` (demo RNF-14 antigua; nada lo leía).
- **Las capas son contrato**: `tests/test_arquitectura.py` fija la dirección de los imports (solo
  hacia dentro) con las 4 dependencias ascendentes vigentes congeladas como excepciones — una nueva
  rompe la suite. De paso cayó un import muerto (`motor/perfil` → `accion/catalogo`, sin uso).
- **Dos adelantos de v2** (26/10): el `main()` por lotes de `triaje` vive ahora en
  `servicio/triaje_lote` (CLI: `python3 -m prototipo.servicio.triaje_lote`) y `motor/` queda
  importable standalone — las excepciones del contrato bajan de 4 a 2 (ambas, la traza como formato
  transversal); y **`TRIAJE_SSH_MODO=directo`**: el conector hace SSH desde el propio host, sin
  `docker exec` (clave/known_hosts del host, mismas opciones endurecidas, fail-closed sin clave) —
  desplegable en VM/bare-metal sin Docker, validado en vivo contra la demo portátil.
- **«v2» tiene por fin un registro**: [documentacion/00-general/v2-trabajo-aplazado.md]
  (todo lo aplazado conscientemente a después de la entrega, con su porqué; antes eran menciones
  dispersas sin un sitio donde buscarlas).
- Agente ReAct: optimalidad validada con un modelo capaz y reproducibilidad probada (documentado).

### Corregido
- Hallazgos de revisión adversarial (Opus) por familia: verificación invertida de acciones
  transitorias; `AISLAR_NODO` que no se ejecutaba; veto de gestión/anti-self-DoS en
  `BLOQUEAR_DESTINO`; `/api/trazas` ahora arrastra los campos del ciclo de caso.
- **Dos caídas del daemon** (auditoría 20/10): una línea de JSON con anidamiento hostil (bajo el
  tope de 1 MiB) lanzaba `RecursionError` fuera del `except`, y un lote con timestamps de zona
  mixta (aware+naive) rompía la agrupación fuera de la barrera. El parseo tolerante de línea JSONL
  vive ahora en un solo sitio (`ingesta.parsear_linea`, usado por todas las fronteras) y la
  agrupación normaliza la zona con el mismo patrón que la ráfaga (`rafaga._instante`).

### Seguridad / Robustez
- **Fail-open de `MATAR_CONEXION` corregido (verificación de contención transitoria).** El post-check
  de una acción `transitoria` daba por **cortada** la conexión cuando `rc != 0`; así, un **fallo** del
  chequeo (ss ausente `rc 127`, SSH caído `rc 255`, timeout `rc 124`) se leía como corte exitoso aunque
  la sesión del intruso siguiera **viva** — y la revisión destapó que, con el pipe `ss … | grep`, hasta
  un `ss` roto dejaba al grep devolver `rc 1` sobre entrada vacía (interpretado como «cortada»). Ahora
  la verificación **lista** las conexiones (`ss -tunap`) y el match (¿sigue la IP?) se hace sobre la
  **salida** con palabra completa (no confunde `192.168.1.10` con `.100`): solo cuenta como contenida si
  el listado **corrió** (`rc 0`) y la IP **no aparece**. Un fallo del chequeo ahora **falla cerrado**.
  Afecta a `verificacion.confirmar` y `conector.ejecutar_orden` (los dos sitios); `MATAR_CONEXION` no es
  `nunca_automatica`, así que el fail-open podía darse en automático. Tests: `test_verificacion` /
  `test_conector` (fail-closed ante `rc 127/255/124/2`, corte efectivo, prefijo de IP).
- **Receptor de red**: cierre de la conexión ociosa (15 min sin datos: una conexión muda ya no
  retiene su slot), tope de conexiones **por IP** (8: un emisor comprometido no monopoliza los 64
  slots), rechazos y cierres **con rastro** en el log (frenado: uno por minuto y motivo),
  `--permitir` **obligatorio al escuchar fuera de loopback** (fail-closed) y **mTLS opcional**
  (`--tls-ca`: exige certificado de cliente — autentica al emisor, no solo cifra).
- **Cola de pendientes acotada** (tope 500): un atacante que fabrique claves infinitas (un `srcip`
  distinto por alerta) ya no agota la memoria; al tope se desaloja la tarjeta menos severa y más
  vieja (nunca una en curso), contado y con aviso.

### Visor (auditoría 20/10)
- **Fallos distinguidos**: «daemon caído», «token rechazado (401)» y «respuesta que no valida» ya no
  se confunden — cada uno con su mensaje; al perder la conexión, las vistas conservan los últimos
  datos recibidos (congelados, con aviso) en vez de vaciarse; un registro malformado se descarta sin
  tirar la lista entera.
- **SLA sin drift**: «pendiente hace X» se calcula contra la hora del daemon (cabecera `Date`), no
  contra el reloj del navegador.
- **Etiquetas de clase unificadas** en una sola fuente (`datos.etiquetaClase`): las donas ya muestran
  «Exfiltración / C2» y «Malware» (antes el id crudo); color **por identidad de la clase**, estable.
- El **ciclo de caso** se pliega en el servidor (`GET /api/caso/<id>`, sobre el fichero completo):
  no «rejuvenece» al salir de la ventana de trazas, el panel no descarga la traza entera y refleja
  el cambio al instante tras guardar; la verificación de cadena pasa de cada 2 s a cada 30 s.
- Operable con **teclado**: la fila de Decisiones/Trazas se enfoca y expande con Enter/Espacio;
  aviso de «últimas N de M decisiones»; KPI «esperando aprobación» clicable; matriz ATT&CK completa
  al imprimir el informe; tooltip de los gráficos con el tema oscuro.

### Seguridad / Robustez (M5 + Bajas de la auditoría 20/10)
- **No repudio sin resquicio (M5)**: con mapa de operadores, SOLO el token identifica — el usuario
  del token compartido ya no puede atribuir su veredicto/reversión/nota a cualquier nombre; el
  campo del cuerpo (sin mapa) y el `id` del caso quedan acotados (64).
- **Des-bloqueo en masa con gesto y candado**: `POST /api/revertir-todo` exige `confirmar: true`
  (400 sin él) y rechaza concurrentes (409) — dos a la vez duplicaban los `iptables -D`; sus SSH
  ahora se anotan como **actividad del MDR** (la `ActividadMDR` se comparte con el lazo): su eco
  ya no se triaja como alerta fantasma.
- **CORS/Origin por puerto exacto**: una página local en otro puerto (otro dashboard, un dev-server
  con XSS) ya no puede leer ni forzar la API; el visor en dev es **opt-in** (`TRIAJE_CORS_DEV=5173`,
  ver RUNBOOK) — con el puerto dev siempre abierto, cualquier proceso local podía ligarlo en
  producción y heredar el CORS.
- Terminal del analista **sin secuencias de control** (los campos del log del atacante y del export
  del cliente se imprimen saneados); el banner avisa si falta `TRIAJE_TRAZA_CLAVE` (cadena sin
  firma); los 500 ya no filtran el detalle de la excepción al cliente; la traza batch de
  `prototipo.servicio.lazo` nace 0600.

### Añadido (portabilidad)
- **`lab/portatil/`: la demo en Docker plano, sin Containerlab** — compose de dos nodos (gestión +
  objetivo, construidos del Dockerfile del banco) y `demo.sh` con el ciclo completo: alerta real
  grabada → decisión → aprobación humana → `BLOQUEAR_IP` por SSH con el mínimo privilegio oficial →
  verificación → reversión. Validado de punta a punta (21/10). Lecciones de plataforma documentadas:
  el objetivo necesita `CAP_NET_ADMIN`; la dependencia del conector es Docker (no Containerlab);
  el lazo por lotes consume alertas normalizadas. `wazuh-run.sh` ahora es parametrizable
  (`WAZUH_NOMBRE`/`WAZUH_RED`/`WAZUH_PERMITIR`, defaults del lab intactos) para la variante viva.

### Añadido (banco de pruebas)
- **El lanzador de ataques deja de ser una caja negra**: muestra el comando EXACTO que se inyecta en
  cada nodo (`↳ <nodo> $ <comando>`) —la preparación, el ataque y el deshacer—, no solo el título.
  Es `demo.ejecutor_detallado`, que envuelve el ejecutor y narra cada `docker exec` antes de lanzarlo
  sin cambiar qué se ejecuta. Sale **por defecto en TODAS las modalidades** (menú, `auto` y la tanda
  `continuo`/soak); `--sin-detalle`/`-q` lo silencia en las tandas (tecla `v` en el menú).
- **Tanda CONTINUA / soak** (`sh lab/banco/banco.sh atacar continuo`, alias `soak`, o la tecla `c`
  del menú): lanza ataques **variados sin fin** —barajando TODA la batería en cada vuelta y rotando
  la IP de origen— hasta `Ctrl+C`, para ejercitar el camino detección→triaje→respuesta del MDR de
  forma sostenida. Restaura el banco cada N ataques (`--restaurar-cada`, def. 20; reusa `banco.sh
  restaurar`) para que no se degrade; `--gap` separa los ataques, `--semilla` fija el orden
  (reproducible, RNF-03) y `--vueltas` lo acota. Al parar, un resumen por familia. El orden rotado
  de la IP nunca se reutiliza, así la supresión y los bloqueos previos no ahogan la tanda.
- **Demo de geolocalización observable, SIN contenedores** (`lab/geo_demo/`): en el laboratorio real
  los ataques vienen de IPs del lab/documentación que —por diseño honesto— no geolocalizan, así que la
  vista «Ubicaciones» sale vacía. Esta demo **simula** el caso de producción: `generador.py` fabrica una
  campaña **sintética** de ataques con IPs **públicas** de ~12 países (de la misma tabla de muestra que
  usa el enriquecimiento) y `geo-demo.sh` las inyecta en vivo por el **pipeline real** (normalizador →
  motor → traza → visor), de modo que el mapa se encienda. Solo Python; no toca el motor ni el corpus
  (traza aparte, `run/trazas-geo-demo.jsonl`); escenario claramente etiquetado («[DEMO SINTÉTICA]» en el
  evento crudo). `--continuo`/`--por-pais`/`--pausa`/`--semilla` (reproducible, RNF-03). Suite `lab/geo_demo/tests`.

### Añadido (visor)
- **Ubicaciones de origen** (12ª vista) + **geolocalización OFFLINE**: `actores.geolocalizar` resuelve
  el país de una IP pública con una **tabla de muestra** curada (`prototipo/corpus/geoip-muestra.json`,
  sin dependencias ni egreso; sustituible por GeoLite2); las privadas/documentación/loopback no
  geolocalizan. La vista agrupa los ataques recibidos por **país real / red interna / laboratorio /
  pública sin geo** con un **mapa equirectangular ligero** (marcadores por país) y una tabla
  (ubicación · ataques · IPs · gravedad). El país real sale también en el enriquecimiento de la IP
  (OrigenBadges). Honesto: con datos de laboratorio (IPs de documentación) el mapa sale vacío y lo dice.
- **ASN/organización OFFLINE + rDNS OPT-IN** del origen: `actores.asn_de` resuelve el ASN y la
  organización de una IP pública con una **tabla de muestra** curada (`prototipo/corpus/asn-muestra.json`,
  alineada con la de GeoIP; sin dependencias ni egreso) y el enriquecimiento la expone como un badge
  más (`OrigenBadges`). El **DNS inverso** (`actores.rdns`, `GET /api/rdns?ip=`) está **apagado por
  defecto**: solo consulta si `TRIAJE_RDNS` está activo —una consulta DNS es egreso, contra RNF-01— y
  solo para IPs públicas; se pide **bajo demanda** desde el perfil del atacante (nunca en el sondeo),
  cachea solo los positivos (un fallo transitorio no condena a la IP) y restaura el timeout global del
  socket. Con el opt-in apagado el perfil muestra «sin resolución (rDNS desactivado o sin PTR)».
- **Cobertura ATT&CK honesta**: la matriz muestra también, en gris y «fuera de alcance», las tácticas
  de Enterprise que no cubrimos por diseño (Desarrollo de recursos, Recolección), con un titular
  «12 de 14 tácticas» — para que la cobertura no parezca un hueco cuando es alcance deliberado.
- **Mi cola** en Decisiones: un filtro «Solo mías» que deja solo las decisiones cuyo **caso está
  asignado al operador actual** (reutiliza `estadoDeCasos` + `operadorActual`; deshabilitado si no hay
  operador puesto). Sin backend nuevo.
- **Acciones en bloque en Aprobaciones**: casilla por tarjeta y una barra para **rechazar** o
  **aprobar las seleccionadas** de una vez (aprobar con confirmación, porque ejecuta contención).
  Reutiliza el POST `/api/aprobar` por decisión con la respuesta correcta según el tipo de pendiente
  (`respuestaPara`); al terminar, un resumen de cuántas se aplicaron. Sin backend nuevo.
- **Watchlist / IoC local** (11ª vista): una lista de indicadores (IP o CIDR) que el analista marca
  como maliciosos — alta/baja desde el visor, persistida en `watchlist.json` (junto a `--salida`) vía
  `GET`/`POST /api/watchlist`. El visor marca con **⚑** los orígenes que coinciden en la tabla de
  atacantes y en el perfil de atacante. Es una **anotación del analista**: NO toca el motor ni las
  métricas (la lista de amenazas del cliente sigue en el SIEM). Backend: `prototipo/servicio/watchlist.py`
  (almacén JSON atómico, valida IP/CIDR con `ipaddress`); frontend: `datos.enWatchlist` (coincidencia
  exacta o por /24).
- **Riesgo por entidad** (asesor y explicable): una insignia «Riesgo: bajo/medio/alto/crítico» en el
  panel del equipo y en el perfil de atacante, con los **factores** que lo elevaron en el tooltip
  (gravedad del peor ataque, volumen, decisiones pendientes, contención sin confirmar, criticidad del
  activo / nº de equipos atacados). Fórmula transparente sobre señales objetivas, en cliente
  (`datos.riesgoEquipo` / `riesgoAtacante`); no un número mágico.
- **Tiempos de respuesta / SLA** en Métricas: además del MTTR medio, ahora el **MTTR mediano**, el
  **% dentro de SLA** (umbral configurable con `TRIAJE_SLA_SEG`, def. 15 min) y los **SLA incumplidos**
  —al estilo de los dashboards comerciales—, calculados de los timestamps de la cola humana
  (`recibido_en`→`resuelto_en`). Backend: `metricas` devuelve `mttr_mediano_seg` + bloque `sla_*`.
- **Runbook por familia en la tarjeta**: el detalle de una decisión muestra ahora los **pasos de
  respuesta recomendados** para esa familia (qué contuvo, qué verificar, qué investigar, cómo
  reclasificar/revertir) — aflora el conocimiento del RUNBOOK junto a la `recomendacion` del motor.
  En cliente, con `datos.pasosRunbook(clase)`.
- **Perfil de atacante** (página de entidad, drill-down): al pulsar una IP en la tabla de atacantes
  del panel de Red se abre su ficha — ataques totales, **equipos atacados** (con cuántas veces y la
  última), gravedad máxima, ventana temporal, el enriquecimiento (alcance/clasificación/geo) y la
  tendencia por día —, con pivote a sus decisiones. En cliente, con `datos.perfilAtacante`.
- **Vista «Campañas»** (attack story, 10ª vista): los ataques agrupados por **bloque de origen /24 a
  través de todos los equipos** — una campaña que rota IPs contra varios activos aparece como una sola
  fila, con sus **objetivos** (a qué equipos pegó y cuántas veces), nº de IPs, gravedad y ventana
  temporal. Pulsar un bloque pivota a Decisiones filtradas por él. En cliente, con `datos.campanasDe`.
- **Panel del equipo más accionable** (vista Red): la tabla de atacantes se **rankea por gravedad**
  (prioridad del peor ataque de cada origen, con su badge, y desempate por nº de ataques), cada **IP
  es clicable** y pivota a Decisiones **filtradas por esa IP** (seguir el hilo del atacante), y la
  **lista de eventos cruda pasa a un bloque plegable** con títulos de sección, para que el panel se
  lea como resumen → correlación → detalle. `atacantesDe` expone `prioridad`; Decisiones acepta
  `textoInicial` para sembrar el filtro al pivotar.
- **Correlación de atacantes por dispositivo** (vista Red): al pinchar un equipo, su panel lista los
  **orígenes que lo han atacado** con el **nº de veces** que cada IP lo golpeó, su alcance
  (interno/externo) y —correlación entre dispositivos, al estilo de los MDR comerciales— **en cuántos
  equipos más** ha pegado esa misma IP. En cliente, con el helper `atacantesDe` (cuenta los ataques
  RECIBIDOS por relación `objetivo`, agrupa por `origen_ip` y cruza el feed completo para el «también
  en N equipos»). Con **muchos orígenes** (una campaña que rota IPs del mismo bloque), se **agrupa
  por subred /24** (conmutador «por IP / por subred», por subred por defecto): una campaña = una fila
  con su nº de IPs (`agruparPorSubred`). Y el pie deja de ser texto muerto: **«Ver los N orígenes en
  Decisiones →»** pivota a la lista completa, paginada y filtrable.
- **Más información de la IP atacante** en el detalle de una decisión y en el grafo del incidente:
  alcance (interno/externo), si está inventariada, clasificación de la IP (pública/privada/de
  documentación/loopback), tercero de confianza, origen legítimo y ubicación. El enriquecimiento lo
  calcula el backend (`actores.enriquecer_origen`) **reutilizando** el actor que el motor ya
  determina (`impacto_determinado.actor`) + la stdlib `ipaddress`; se expone como
  `enriquecimiento_origen` en `/api/decisiones` y `/api/trazas` y se pinta con el componente
  `OrigenBadges`. La **geolocalización** es un *seam offline opcional* (sin dependencia nueva): hoy
  devuelve `null`, así que las IPs de documentación/internas se muestran como «sin geolocalización» y
  las públicas como «sin base GeoIP cargada»; punto de extensión documentado para enchufar una
  GeoLite2. Additivo: no cambia ninguna decisión ni el texto del motivo.
- **Datos por dispositivo en la vista Red**: al pinchar un equipo, su panel muestra ahora, además de
  la lista de eventos, dos gráficas propias: **donut por clase** y **tendencia por día**, calculadas
  en cliente de la traza filtrada por ese equipo (`relaciones`), reutilizando `Donut`/`Tendencia` de
  `charts.tsx` y el helper `agruparPorDia`. Los conteos del equipo quedan en la fila de actividad
  (recibidos / originados / contenidos aquí / pendientes + último visto), sin duplicarlos. Se quitó
  el recorte a 30 de `Red.tsx` para no truncar las agregaciones (la lista del panel sigue mostrando
  los 30 más recientes).
- **Paginación** de las listas largas (Trazas y Decisiones): control «Anterior / página X de Y /
  Siguiente» con **selector de filas por página (10 / 20 / 50, por defecto 20)**, paginado en cliente
  sobre el feed que ya llega acotado; la página y el tamaño viven en el componente y no se reinician
  con el sondeo, y vuelven a la primera página al cambiar el filtro o el tamaño. El selector aparece
  en cuanto la lista supera el tamaño mínimo (10) aunque quepa en una página; el prev/siguiente, solo
  con más de una. Helper puro `paginar` (expone `desde`) en `datos.ts` + componente `Paginador.tsx`.
- **Revertir una contención concreta** desde su fila en «Contenciones activas», no solo el
  des-bloqueo en masa: cada fila tiene un botón «Revertir» con confirmación que llama al nuevo
  `POST /api/revertir {indice, confirmar}` (`revertir.revertir_una`), que des-bloquea esa sola
  contención por su índice de traza sin tocar las demás. Serializado con el kill switch (mismo
  lock), con atribución de operador y su línea `↶` en la Consola. Un índice que ya no es una
  contención activa → `409`.
- **La Consola narra la caja negra**: el porqué de cada decisión (señales: ráfaga/umbral, postura
  del auditor, origen legítimo; y la política con su motivo cuando no permite en automático) y la
  respuesta paso a paso (`▶` orden con su comando exacto, idempotencia, `✔/✗` verificación honesta,
  `⇪` escalada al cortafuegos, `↶` des-bloqueo en masa), con chip de filtro «Ejecución». Formateadores
  puros sobre el registro estructurado: la traza sigue siendo la verdad.
- **El diario del operador en la Consola**: los gestos humanos también dejan línea — `✓/✋/↻`
  veredictos con el nombre de quién decidió (aprobada → qué se ejecuta; rechazada/reclasificada →
  retenida sin ejecutar; el veredicto de una escalada manda sobre el de la tarjeta), `⏻` kill
  switch (narra solo el **cambio**, con operador; reenvíos idempotentes sin ruido), `☰` ciclo de
  caso (estado/asignado/nota, por quién) y `[inicio]` el contexto del arranque en el feed (perfil,
  justificador, ejecutor y si la traza queda anclada y firmada — lo que el banner solo decía en la
  terminal). Validado en vivo (arranque + pausa idempotente por HTTP).
- **Vista «Consola»** (9ª): el registro vivo del daemon dentro del visor — incidentes, decisiones,
  bloqueos con su comando SSH, verificaciones, supresiones, reversiones y avisos, con filtros por
  tipo, búsqueda y auto-scroll que se pausa al subir. Servido incremental por `GET /api/consola?desde=N`
  desde un buffer circular acotado (1.000 líneas, saneadas de caracteres de control) que alimenta el
  mismo `escribir` que ya narraba la terminal.

### Documentación (barrido de la auditoría 20/10)
- Desfases corregidos en los docs vivos: RUNBOOK §3C ya describe las **10 familias / 13 ataques** del
  lanzador y §7 recoge la lección de Wazuh (el guard no recarga reglas nuevas en un manager vivo; la
  IP cambia tras `up`); `estado-y-riesgos` y la guía de operación al día (957/63 tests, 10 familias y
  8 patrones); enlace `material-superado/` reparado; «80/20» → **300/300 por campaña** (README y
  `particion.yml`); cabecera de `prototipo/README` actualizada (ya no es solo el 5A offline).
- Informe de tesis: conteos de pruebas al día en metodología y la **consola MDR** (aviso al analista,
  tiempo de espera y ciclo de vida del caso) incorporada a conclusiones; PDF recompilado.

## [1.1] — 2026-10-14 · Endurecimiento, robustez y congruencia

Sobre v1.0, **sin mover las cifras canónicas** (V1.1 no re-basa v1.0).

### Añadido
- Autenticación **opcional** de la consola por token (`TRIAJE_CONSOLA_TOKEN`) y **no repudio** del
  operador en la traza.
- Señal de vigilancia *low-and-slow* (asesora; adaptación B de la recomendación #1 del informe).
- Recomendaciones del informe: **#2** (clase propia del reconocimiento, versión segura) y **#3**
  (invariante de cobertura del corpus de descarte).

### Seguridad / Robustez
- Pool de hilos acotado del modo agente, entorno filtrado al conector, HMAC opcional de la cadena de
  la traza, conector *fail-closed*, frontera de `stdin` segura (del pentest del propio MDR, 19
  hallazgos; se cerraron los de severidad crítica/alta/media).

## [1.0] — 2026-10-13 · Entrega final de la pasantía

Hito funcional y de evaluación.

### Añadido
- **Motor de triaje**: ingesta → clasificación → política determinista → filtro del perfil de
  cliente → traza encadenada → acción con validación humana. **El LLM justifica, no decide.** 5 familias.
- **Justificador LLM + RAG local** (1B por defecto; 8B en GPU como objetivo), **daemon en vivo**,
  **visor web** (consola SOC), **laboratorio Containerlab** con Wazuh, **dataset etiquetado** (600
  alertas) y **marco de evaluación** frente al baseline de reglas.
- Traza auditable (cadena de hashes, RF-09), kill switch, reversión, `/healthz`, kit de despliegue
  systemd.

### Limitaciones conocidas
- **Clasificador con ajuste fino bloqueado** por falta de un dataset suficientemente variado (la
  empresa no lo aportó): el clasificador es un árbol de decisión, no un codificador entrenado.
- Ejecutar el **LLM 8B** como justificador exige una máquina con **GPU** (el portátil de desarrollo
  no puede): `EVALUAR-LLM-EN-GPU.md`.
