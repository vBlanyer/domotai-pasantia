# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Las **cifras canónicas de la evaluación** (clasificación, priorización, continuidad de v1.0) **no
se mueven** entre versiones: todo lo posterior a v1.0 se diseñó para no alterarlas (ver el informe,
capítulo de resultados, y `evaluacion/resultados/`).

## [Sin publicar]

### Cambiado
- **Identificadores de decisión estructurados: `BCO-20261123-0042`** (prefijo del cliente, día en UTC y
  orden en ese día), en lugar de `s23`.
  - **No se repiten** entre ficheros de traza ni entre instalaciones, y dicen de qué cliente y de qué día
    son.
  - **Prefijo:** `prefijo_id` en el perfil (el del banco, `BCO`); sin él, `20261123-0042`.
  - **Secuencia:** vuelve a 0001 cada día y continúa al retomar la traza.
  - **Actividad propia del MDR:** `BCO-20261123-P0005`, con su propia secuencia; los derivados conservan
    su sufijo (`~sup`, `~tope`).
  - **Trazas antiguas:** con `s23`, se siguen leyendo.
  - **Evaluación:** su `d4` no cambia; las cifras canónicas no se mueven.
- **Políticas: el Resumen en tres columnas y los intocables con candado.** El Resumen cuenta la
  política con una frase y tres columnas: lo que el MDR contiene solo, lo que espera a un analista y lo
  que nunca hace solo. Usa nombres legibles («Fuerza bruta», «core-db · base de datos del core»), y el
  texto de `mdr explicar-politica` pasa a un desplegable. La pestaña «Intocables» desaparece: cada
  servicio intocable lleva un candado en la fila de su equipo, y lo general va al Resumen.
  `/api/politica` añade `funcion` a cada intocable y `externos_desconocidos` a la confianza.
- **`automatizacion_efectiva` coincide con el motor.** La postura por familia solo endurece: «con certeza»
  sobre una familia que de base espera a un analista ya no se pinta como automática, y un freno del
  código con «con analista» sigue siendo un freno.
- **Las dos variantes de AWS en dos carpetas** (`infra/aws/mdr/`, producción, e `infra/aws/laboratorio/`,
  pruebas), autosuficientes sobre un módulo común (`infra/aws/modulos/base/`): cada una con sus variables,
  su estado, su guía, sus costes, su inventario, sus escenarios del emulador y sus pruebas. Desaparece la
  variable `variante`. Lo propio de la GPU (rol, perfil, grupo de seguridad) solo se crea con
  `llm_habilitado = true`. El arranque de cada máquina no cambia. Guía corta de instalación:
  `infra/aws/INSTALAR.md`.
- **Raíz del repositorio más limpia:** el mapa de carpetas de `STRUCTURE.md` pasa al README (sección
  «Cómo está organizado el repositorio») y las observaciones de la revisión del 15/11 pasan a
  `documentacion/05-fase5-implementacion-del-prototipo/observaciones-revision-15-11.md`, junto a su plan.

### Corregido
- **Banco: los ataques rotados ya no dejan IPs pegadas, y cada nodo tiene su clave SSH de host.**
  - **IPs pegadas:** el lanzador añadía una IP por ataque con origen rotado (`ip addr add`) y nadie la quitaba.
    Había 409 acumuladas en taquilla, middleware e internet, y el asistente de red las encontraba como
    equipos. Ahora las quita el «deshacer» del caso, y `banco.sh restaurar` quita todas las IP secundarias de
    los nodos (las de Containerlab son primarias).
  - **Claves de host:** todos los nodos compartían la clave de la imagen, así que fijar una huella no
    distinguía un equipo de otro. `up` genera una por nodo, una sola vez por contenedor. Para un banco ya
    levantado está `banco.sh claves-propias`, y después `aprovisionar` fija las huellas nuevas.
- **Asistente de red: los fallos de la prueba completa del 23/11.** Se probó con un escaneo real del banco
  (8 subredes, 185 equipos).
  - **Caminos:** cuando muchos equipos comparten camino, nmap no repite en el XML los saltos que ya trazó
    para otro, y 121 de 185 salían «sin camino». Ahora se completan con los del equipo que los trazó, solo si
    todos los candidatos coinciden y prefiriendo su subred; si no, el hueco se queda. En vivo: 177 de 177
    con camino.
  - **«Llega por» se puede editar:** el técnico indica el cortafuegos de un equipo. Descartar un cortafuegos,
    o cambiarle el papel, reengancha lo que salía por él a su siguiente salto. No se admite un ciclo ni que
    un cortafuegos salga por sí mismo.
  - **La tabla ya no enseña lo que no se guardó:** cada campo válido se guarda y el inválido se queda escrito y
    marcado con su motivo. Antes un campo malo tiraba el lote entero sin que la tabla lo reflejara. Además, un
    fallo de red reintenta con el siguiente cambio, y pasar a «Validar y exportar» o salir de la vista guarda
    antes lo pendiente.
  - **`sudo mdr descubrir` deja el fichero al dueño del directorio**, el usuario del servicio, conservando el
    0600. Antes quedaba de root y la consola lo ignoraba sin avisar. Un fichero del asistente ilegible o
    dañado se explica en la vista y no da 500.
  - **«Validar» aplica las reglas de `mdr validar-perfil`:** los avisos del mapa cuentan como errores y un
    ciclo entre cortafuegos se señala.
  - **La dirección de fuera tiene que ser de internet** y los rangos, redes del cliente (RFC 1918 o 100.64/10).
    Antes una dirección interna invertía la cadena sin avisar. Un router del proveedor en el camino de salida
    se avisa y, si se descarta, su red sale de las redes internas.
  - **Reescanear conserva lo escrito** para las mismas IPs, también lo editado durante el escaneo, y la vista
    avisa del escaneo en marcha.
  - **La vista ya no se queda en «Cargando…»:** el estado traía una clave `error` y el sondeo tomaba cada
    respuesta buena por un fallo. Un error de la propuesta se dice en vez de «Comprobando…».
  - **Sin rastro en la traza no se escanea, y el escaneo no queda «en marcha» para siempre.**
  - **Una IP ya no es interfaz de dos cortafuegos a la vez.**
- **Una contención que desaparece del equipo ya no silencia al atacante.** El MDR daba por contenido lo
  que había contenido alguna vez: si la regla desaparecía fuera del MDR (un reinicio del equipo, alguien
  que vacía el cortafuegos, `banco.sh restaurar`), las repeticiones del ataque se suprimían como «ya
  decidido (contenida)» aunque llegaran al equipo. En la tanda del 23/11, 198.51.100.10 (en vigilancia)
  seguía probando contraseñas contra web-banking sin que nadie lo viera.
  - **Ahora:** al repetirse algo contenido, el MDR vuelve a comprobar la regla en el equipo. Lo hace como
    mucho una vez cada 5 minutos por decisión, y no en los 5 minutos siguientes a contener. Tras reiniciar
    el daemon, comprueba en la primera repetición.
  - **Si la regla ya no está**, la anota como contención **perdida** en la traza: es una reversión sin
    comando, con `perdida: true`. Deja de listarse como activa y el ataque se decide de nuevo, con la
    política vigente (un origen vigilado va al analista).
  - **Si no se puede comprobar** (sin conexión, sin permisos), la supresión sigue como estaba.
  - **En el visor**, Decisiones la marca «perdida» y el 7.º paso cuenta que la detectó el MDR. En Trazas,
    «Quién» es el MDR.
- **Las repeticiones sin IP de origen dejan rastro.** Un FIM, una DoS o un malware que se repetía mientras
  su tarjeta esperaba al analista recibía un id. La Consola lo anunciaba «En cola» y la cola lo sumaba
  sin decir nada a la tarjeta que ya había: ese id no existía en la traza y dejaba huecos en la
  numeración (`BCO-20261123-0012`…`0021` en la tanda del 23/11). Ahora se suma a la tarjeta antes de
  triarlo, queda como `actividad_suprimida` («pendiente del analista») y no gasta id.
- **Cortar una sesión ya no suprime la siguiente intrusión del mismo atacante.** `MATAR_CONEXION` es
  transitoria: corta la sesión de ese momento, no impide la siguiente. La memoria de supresión la
  recordaba como una contención, y un nuevo login exitoso del mismo origen salía «ya decidido» sin
  cortarse (tanda del 23/11, `s19~sup`). Ahora las acciones transitorias no se recuerdan.
- **Revertir una contención en la consola ya no deja al atacante «ya decidido» sin bloquear.** La
  memoria de supresión solo excluía lo revertido al arrancar; una reversión hecha durante la sesión no
  le llegaba, y las repeticiones del mismo origen se suprimían sin que hubiera bloqueo (tanda del 23/11:
  D1 desde 198.51.100.11 e INTRUSION desde 198.51.100.10, 10 alertas cada uno, sin contener). Ahora
  `/api/revertir` y `/api/revertir-todo` avisan al lazo y la memoria olvida esas decisiones
  (`MemoriaDecisiones.olvidar`).
- **La cuarentena (`AISLAR_NODO`) ya no deja al MDR sin acceso al equipo aislado.** Cortaba todo lo que
  salía del equipo, también sus respuestas al MDR, así que el MDR no podía verificar la cuarentena ni
  deshacer nada en él (23/11: dos reversiones de web-banking fallaron así). Ahora es
  `iptables -A FORWARD -s {ip_nodo} ! -d {ip_gestion} -j DROP`. Sin una IPv4 en `ip_gestion`, se veta.
  - Una cuarentena creada antes del cambio se revierte con su comando de entonces
    (`reversion_cmd_anterior`).
  - **Tras actualizar, el envoltorio `mdr-accion` de los cortafuegos debe reinstalarse:** Conectividad
    lo marca como deriva; en el banco, `banco.sh aprovisionar`.
  - Probado en vivo: la cuarentena aísla web-banking de api-movil, pero no del MDR.
- **El panel derecho de cada vista tiene su propio scroll** (Aprobaciones, Decisiones, Trazas,
  Contenciones, Incidentes, Conectividad y Red): se queda a la vista y no alarga la página. Su alto es lo
  que queda visible desde donde empieza (debajo de las cifras y los filtros), así su final se alcanza sin
  bajar la página (`useAjusteInspectores`). Comprobado en Chromium: acaba a 12 px del borde inferior.
- **Banco: las tandas ya no dejan web-banking sin acceso para el MDR.** El caso E1 corta a propósito el
  SSH del MDR hacia web-banking para probar la escalada, y las tandas automática y continua lo lanzaban
  sin deshacerlo: todos los ataques siguientes a web-banking fallaban en el equipo. Ahora las tandas
  dejan fuera los casos que preparan un fallo (`demo.casos_de_tanda`). E1 sigue en el menú, y si no se
  deshace, el lanzador avisa.
- **El origen se ve igual en Aprobaciones y en Decisiones** (componente común `BloqueOrigen`): IP, equipo
  atacado, alcance, ubicación y «lo que ya pasó con este origen». Antes Decisiones solo mostraba la IP y
  sus distintivos, y la sección desaparecía sin enriquecimiento.
- **Banco: `MATAR_CONEXION` ya funciona.** La imagen `banco-nodo:1` no traía `ss` (iproute2) y cortar la
  sesión de un intruso fallaba siempre con «ss: not found». Además, el plazo de conexión SSH del
  conector es configurable (`TRIAJE_SSH_PLAZO_CONEXION`, 5 s por defecto) y el banco lo sube a 15 s:
  bajo una fuerza bruta contra el sshd del equipo, el MDR lo daba por caído a los 5 s.
- **La escalada al cortafuegos ya no se veta por el papel del equipo atacado.** Si contener en el propio
  equipo fallaba (p. ej. el SSH no respondía a tiempo durante una fuerza bruta), la escalada a fw-core y
  fw-edge comprobaba el papel de Conectividad del equipo ATACADO (un servidor, sin bloqueo en
  cortafuegos) y salía vetada siempre: web-banking quedaba sin contener. Ahora cuenta el papel del
  equipo donde se ejecuta cada salto (`perfil.filtrar(..., nodo_ejecucion=)`).
- **Decisiones ve la misma ventana que Red y Trazas** (los últimos 500 registros, no 50): al pivotar
  desde Red a las decisiones de un equipo ya no faltan sus ataques.
- **Reclasificar tiene «Volver».** Desde el submenú de clases se vuelve al menú de veredicto sin decidir
  nada. Antes, una respuesta que no era una clase **rechazaba** la decisión.
- **Trazas: lo más reciente arriba** y chip **«Reversiones»**; la Consola también tiene el filtro
  «Reversiones» (las reversiones siguen saliendo en «Ejecución»).
- **La observación de Aprobaciones se ve mejor:** rótulo propio, más alta y con borde de color.
- **El estado de la conexión dice lo mismo en la cabecera y en el menú** («en vivo · cada 2 s»).
- **Recargar la página ya no devuelve al Panel.** La vista activa va en la URL (`#/politicas`,
  `#/aprobaciones`…): al recargar se queda donde estaba, y atrás/adelante del navegador recorren las
  vistas. Una vista de detalle (perfil del atacante, grafo del incidente) vuelve tras recargar a la vista
  de la que sale, porque su contexto no viaja en la URL.
- **Políticas abre en «Resumen».** La pestaña «En castellano» pasa a llamarse «Resumen» y es la primera:
  al entrar se ve la política entera en frases. Sobra el botón «Leer en castellano», que solo abría esa
  pestaña.
- **La nota del analista ya se ve donde se busca.** La nota opcional de Aprobaciones se guardaba en la
  traza, pero solo se veía dando un rodeo (cronología de Incidentes o grafo del incidente). Ahora sale en
  Decisiones, en el paso «Analista» (con quién la escribió y cuándo), y en Trazas el registro «Caso
  actualizado» muestra su texto. Al decidir, el aviso confirma «Nota guardada en la traza» o, si no se
  pudo guardar, lo dice y devuelve el texto para no perderlo.

### Añadido
- **«Revertir y vigilar» cumple lo que promete.** Una IP en la Watchlist sale marcada ⚑ en Aprobaciones y
  en Decisiones (en la fila y, con su nota, en el bloque de origen). La Consola avisa con
  `⚑ origen en vigilancia: IP → equipo · nota` cada vez que vuelve.
  - **Opcional, apagado por defecto:** con `respuesta_automatica.origenes_vigilados: con_analista` en
    `politica.yml` (perfil: `continuidad.vigilados`), todo lo que venga de una IP vigilada espera a un
    analista, con el motivo en la tarjeta.
  - **Cómo llega al motor:** en el perfil (`origenes_vigilados`), que el servicio rellena desde
    `watchlist.json` en cada incidente; el motor no lee ficheros.
  - **Dónde se ve:** el Resumen de Políticas y `mdr explicar-politica` lo cuentan.
  - **Activado en el perfil del banco y recomendado en `deploy/politica.ejemplo.yml`:** si el analista
    revirtió un bloqueo porque dudaba, lo coherente es que el MDR le pregunte antes de volver a bloquear.
    Con la Watchlist vacía no cambia nada, y las cifras de la evaluación no se mueven.
- **La cola de Aprobaciones sobrevive al reinicio.** Al encolar, el registro `pendiente` de la traza guarda
  la tarjeta: la decisión, la alerta y, en una escalada, desde dónde se escala. Al arrancar, las tarjetas
  sin resolver vuelven a la cola con su id y su hora de encolado (el SLA no vuelve a cero), y se
  resuelven igual que antes del reinicio. Solo se restaura con la consola web y desde una traza que
  verifica; si no, se anotan como «pendiente perdida», como antes (fail-closed). Las pendientes escritas
  antes de este cambio no llevan la tarjeta y se siguen perdiendo.
- **`reiniciar.sh` retoma la traza más reciente** en vez de empezar siempre otra: si no, la cola no
  volvía (se restaura desde la traza que se retoma). La numeración ya continúa al retomar una traza, así
  que los ids no se repiten. `--traza-nueva` empieza otra a propósito.
- **La reversión se ve donde se cuenta la historia de la decisión.** En Decisiones, una decisión
  revertida ya no sale como «contenida»: tiene el desenlace «revertida», su filtro, y el paso «Ejecución»
  dice cuándo, quién y por qué se revirtió. En Trazas, el inspector de una reversión enseña quién, por
  qué, qué deshace, el comando exacto y su resultado (y la salida si falló), y la decisión enlaza su
  reversión por la posición en la cadena, no por el id. En «Cómo se decidió», la reversión es un 7.º
  paso propio: cuándo, quién, por qué, el comando y su resultado, un enlace a Trazas y, si el mismo
  origen volvió a atacar el mismo equipo y se contuvo de nuevo, en qué decisión. El paso «Ejecución»
  sigue contando solo lo que pasó al ejecutar.
- **«Análisis ampliado» en la ficha de Aprobaciones**: al encolar una decisión para el analista, el MDR
  reúne por reglas, sin modelo, el contexto que antes había que buscar a mano: qué más hizo ese origen en
  la última hora (con el reconocimiento previo y los equipos tocados), qué tiene abierto el equipo atacado
  según el último escaneo y su criticidad, la ficha del playbook de la familia, y una lista de «antes de
  aprobar, comprueba» (origen interno, cascada, reconocimiento previo, varios equipos, servicio que no
  figura abierto, acción vetada). Cita sus fuentes y **no cambia la decisión**; si falla, la ficha sale
  igual, sin la sección (`prototipo/explicacion/analisis_ampliado.py`).
- **Consultar el despliegue por MCP contra el emulador** (`MDR_MCP=1 sh infra/aws/emulador/probar.sh`):
  el servidor MCP de API de AWS, en local, solo lectura y sin telemetría, pregunta por lo creado en cada
  escenario (instancias, endpoints, NAT, perfiles, discos) y se le niega parar la instancia. Ensayo del
  diagnóstico del primer despliegue real; instrucciones en `infra/aws/README.md`.
- **Simulacro del laboratorio** (`infra/aws/laboratorio/simulacro/simulacro.sh`): el arranque real de la
  variante laboratorio en una «máquina» Amazon Linux 2023 vacía con `systemd`, aislada del equipo. Se monta
  sola (Docker, Containerlab 0.79.0, la v1.9.2 verificada por su commit, disco, clave y token, unidad
  `mdr-laboratorio`), levanta banco, Wazuh y MDR, contiene un ataque, se reinicia y lo vuelve a contener:
  22 de 22. Es la primera vez que ese arranque se ejecuta entero. `--mantener` deja la consola en
  `http://127.0.0.1:18787`.

## [1.9.2] — 2026-11-17 · despliegue en AWS: MDR y laboratorio

### Añadido
- **Prueba del despliegue contra AWS Emulator** (`infra/aws/emulador/`): `plan`, `apply` y `destroy` de
  los `.tf` reales en cuatro escenarios (con egreso, sin egreso con secretos, GPU con 1.9.1 rechazada,
  GPU), con comprobaciones sobre el estado y el arranque. Sin cuenta ni coste.
- **Para el despliegue oficial** (`infra/aws/`): inventario de lo que crea cada escenario
  (`inventario/`, JSON y tabla), costes con precios oficiales de `eu-west-1` y `us-east-1`
  (`COSTES.md`), plantilla de variables (`produccion.tfvars.ejemplo`), estado remoto en S3
  (`backend.tf.ejemplo`) y guía paso a paso con las cuotas (`DESPLIEGUE.md`).
- **Variante «laboratorio» del despliegue en AWS** (`variante = "laboratorio"`): la instancia del MDR
  levanta el laboratorio del banco, su Wazuh y el MDR para probar el MDR antes de un cliente, y lo rehace
  en cada encendido (`lab/banco/servicio-mdr.sh`, unidad `mdr-laboratorio`). Escenarios E, F y G en el
  emulador; costes y guía. Necesita un MDR ≥ 1.9.2.
- `banco.sh comprobar-alertas`: comprueba que Wazuh genera alertas de punta a punta.
- Al rehacer el laboratorio, las contenciones de la sesión anterior se anotan en la traza como revertidas
  (`revertir.anotar_desaparecidas`, `lab.banco.rehecho`): el MDR vuelve a decidir los ataques repetidos y
  la consola no lista contenciones que ya no existen. Probado en vivo con dos arranques sobre la misma
  traza.

### Corregido
- **Identificadores de decisión repetidos tras reiniciar**: cada arranque del daemon volvía a `s1` y,
  como producción escribe siempre en la misma traza, un reinicio dejaba identificadores repetidos (la
  cadena seguía siendo válida). Ahora sigue la numeración de la traza que retoma.
- Laboratorio preparado para arrancar sin nadie delante: `banco.sh test` termina con error si falla una
  comprobación, y las esperas a Wazuh tienen tope (10 min) y enseñan el motivo.
- **Despliegue en AWS** (`infra/aws/`, puntos #6–#12, #18 y #19 de la revisión del 15/11): el arranque
  instala el paquete del release verificado por su huella con `instalar.sh` (consola incluida, código de
  root), exige el disco de la traza, firma la traza y protege la consola con token (Secrets Manager o
  generados) y, con GPU, conecta el modelo y el embedder del RAG; la GPU compila llama.cpp con CUDA y
  sirve los dos modelos verificados. El arranque anterior fallaba por sintaxis (un doble dólar que
  `templatefile` no escapa) y no instalaba `openssh-clients`. Simulacro del arranque en
  `amazonlinux:2023` (`infra/aws/simulacro/`). Sin `apply` real.
- `TRIAJE_CON_LLM=1` en `triaje.env` arranca el daemon con el modelo de lenguaje (también en el
  equipo local).

## [1.9.1] — 2026-11-16 · revisión final de la consola

### Corregido
- La demo sin laboratorio (`--sin-lab`) ya no omite todas las contenciones: los recortes de Conectividad
  (equipo sin clave del host fijada) no se aplican con el ejecutor simulado.
- Los registros «Pendiente de aprobación» llevan el origen (sale del contexto de la decisión) y la
  vista Trazas lo muestra.
- Textos de Conectividad y del alta de equipos al día con el envoltorio `mdr-accion`.

## [1.9] — 2026-11-16 · entrega final

### Añadido
- **El RAG agéntico con cinco generadores** (informe, `tab:modelos`; `evaluacion/resultados/rag-agentico-modelos/`):
  Llama 3.2 1B, Qwen2.5 3B y Foundation-Sec-8B-Instruct en local, y Claude Haiku y Sonnet. Ninguno
  mejora con claridad la consulta fija; la diferencia está en la justificación. El banco del RAG separa
  los textos del modelo de los de la plantilla, cuenta los que cayeron a ella y admite `--plazo`.
- Manual de producción: las carpetas del MDR instalado, en el equipo MDR y en cada equipo del cliente.

### Seguridad
- **Envoltorio `mdr-accion` del conector** (#13 de la revisión del 15/11): las reglas de sudoers con
  comodines admitían argumentos extra (`iptables -A INPUT -s 1.2.3.4 --modprobe=<programa> -j DROP`
  ejecutaba ese programa como root; `passwd -l *` admitía `root`). Ahora el sudoers del conector solo
  permite `/usr/local/sbin/mdr-accion`, generado desde el catálogo (`catalogo --envoltorio`), que valida
  cada argumento por su tipo y ejecuta exactamente una acción del catálogo; lo demás sale con 126. El
  paquete de alta (script, Ansible) y el aprovisionamiento del laboratorio lo instalan; la prueba de
  Conectividad exige que sudo solo permita el envoltorio y compara `mdr-accion --reglas` con el papel. Los
  equipos dados de alta antes salen como privilegio de más o sin aprovisionar hasta volver a ejecutar su
  paquete de alta.
- Endurecimiento del envoltorio y del alta (revisión final): las IP solo sin prefijo (nada de `/0`);
  el usuario real del conector nunca se bloquea; los valores de servicio/cuenta no pueden empezar
  por «-»; `continuidad.limite_banda` se valida al cargar el perfil y se normaliza a minúsculas; el
  script de alta borra sus temporales si falla y avisa (y cierra) si `/usr/local/sbin` es escribible
  por otros; el playbook de Ansible aparta los sudoers antiguos del conector como el script.
- La consola envía `X-Frame-Options: DENY` y `Content-Security-Policy: frame-ancestors 'none'` (#14), y
  el arranque avisa si la consola no tiene autenticación (#15).

### Corregido
- Las aprobaciones pendientes quedan en la traza (`pendiente`) y, si el servicio se reinicia antes de
  resolverlas, se anotan como `pendiente_perdida` y se avisan al arrancar (#1).
- El índice del RAG cubre de nuevo las 35 fichas del corpus, con una prueba que lo vigila (#2).
- La API responde 400 (no 500) a un cuerpo JSON que no es un objeto (#22); prueba `test_receptor`
  estable (#17).

### Añadido
- **Asistente de red** (rama `asistente-de-red`): una vista de la consola que describe una red nueva a
  partir de un escaneo con Nmap (equipos, puertos, caminos por traceroute y huellas SSH) y **propone**
  `perfil.yml`, `postura.json` y `politica.yml` para descargar; la consola nunca escribe el perfil vivo.
  Escanear exige operador identificado y la autorización del cliente, y queda en la traza firmada.
  `mdr configurar` ofrece un **perfil mínimo** para arrancar sin describir la red; `mdr descubrir` escanea
  desde la línea de órdenes. Laboratorio nuevo **`oficina`** (`lab/oficina/`) para ensayar la instalación
  en un cliente; ensayado de punta a punta.
- **`politica.yml`, la política de la empresa** en términos de negocio (en quién se confía, qué se
  automatiza, qué no se toca nunca), aparte del perfil técnico y traducida a sus claves al arrancar
  (`TRIAJE_POLITICA`). Una política inválida, o una regla en los dos ficheros, impide arrancar; cada
  arranque anota versión, aprobador y huella en la traza. Órdenes `mdr validar-politica`,
  `explicar-politica` (en frases) y `migrar-politica`; línea «política» en `mdr estado`. La vista
  Políticas dice el origen de cada valor, lista los cambios de consola pendientes con «Volver a la
  política» y exporta la propuesta de la versión siguiente. Plantillas separadas:
  `deploy/perfil.ejemplo.yml` (solo la red) y `deploy/politica.ejemplo.yml`; `mdr configurar` instala la
  política junto a un perfil nuevo y pregunta por administradores y socios críticos. Las instalaciones
  con las reglas en el perfil siguen igual.

### Cambiado
- **Recortes ante fallos validados en el banco** (11/11/2026, `evaluacion/resultados/validacion-recortes-2026-11-11/`):
  ninguna contención se pierde; un equipo que descarta el SSH del MDR pasa de ~33 s a ~19 s y los fallos
  repetidos de ~31 s a ~7 s, y cortar una conexión que el equipo no puede ejecutar, de ~17 s a ~10 s. Los
  cinco recortes quedan **encendidos por defecto** (`=0` los apaga).
- **Conector:** no pasa ninguna variable `TRIAJE_*` a `ssh` ni a `docker exec` (antes, una lista de cuatro secretos).

- **Evaluación ampliada (R1 + R2):** partición de evaluación de 417 alertas (209 soportadas) con otro
  equipo (`iot`), otro servicio (FTP), atacante externo, legítimos desde orígenes no declarados y los
  ataques lentos del experimento de octubre; verdad declarada por el experimento y diseño fijado antes de
  medir. P 0,931 · R 0,667 · F1 0,777 (baseline 0,800) · FP 0,038; sin los ataques lentos, R 1,000 y F1
  0,964 (n=300: 0,978 · 1,000 · 0,009); 4 contenciones automáticas indebidas (técnico legítimo del proveedor).
- **Evaluación aparte en el banco** (perfil bancario, `lab/campañas-banco/`, `lab/banco/campana_evaluacion.py`):
  40/2/3/0; los 2 FP son los legítimos y uno se bloquea solo. `evaluacion.campana --dataset` para usar otro conjunto.
- **Prioridad del reconocimiento** rebajada a 2 (R2); la prioridad esperada admite excepciones por familia.

### Corregido
- **La consola ya no puede aflojar** lo que el perfil (o ahora `politica.yml`) deja en manos de un
  analista: antes, en Políticas, poner AUTO una familia, zona o equipo cerrados en la base los abría (y
  un equipo podía saltarse el HUMANO de su zona). Ahora el POST responde 400, y una entrada así en un
  `politica-operativa.yml` antiguo se ignora al arrancar; tampoco cuenta como cambio pendiente ni
  entra en la propuesta.
- `lab/banco/fallos.py`: los casos «sshd» y «clave-host» no paraban ni recargaban el sshd del banco.
- Postura: `vsftpd`, `proftpd` y `pure-ftpd` casan con el protocolo `ftp` del auditor (un ataque real al
  FTP expuesto salía «no expuesto»).
- `lab/dataset/construir.py`: ignora las carpetas de `lab/campañas` sin `campaña.yml`.

### Añadido
- `lab/banco/validar_recortes.py`: arnés reproducible de la validación de los recortes.
- `lab/scripts/campana-ampliacion.sh`: campañas de la ampliación R1 (señuelo telnet en `iot`, reenvío de `vsftpd.log`).

## [1.8] — 2026-11-10 · cierre del proyecto

### Añadido
- **Plan de manejo de fallos de contención (fases 0–6):** cada contención fallida se clasifica (F1–F10)
  con su causa en lenguaje claro y su evidencia, en la Consola, Decisiones, Trazas y «Te toca»; las que
  pueden ser un ataque (clave del host cambiada, contención deshecha, regresión) se marcan aparte;
  Conectividad se entera de las contenciones reales que fallan. Cinco **recortes** opcionales
  (`TRIAJE_FALLO_RAPIDO`, `TRIAJE_PRECHECK_APROVISIONADO`, `TRIAJE_ESCALADA_SOLO_APROVISIONADOS`,
  `TRIAJE_MEMORIA_FALLOS`, `TRIAJE_ACCION_NO_EJECUTABLE`): **experimentales, apagados por defecto**.
- **Red:** mapa ramificado (una red tras su propio cortafuegos, en su rama), dependencias dentro de una
  zona y avisos del perfil roto; **escalada de respaldo** al perímetro cuando falta el `gateway`.
- **Producción:** `deploy/instalar.sh` (instala, actualiza, desinstala), `deploy/empaquetar.sh` (paquete
  del cliente desde el último commit) y la herramienta `mdr` (`configurar`, `estado`,
  `analista alta|baja|lista`, `escanear`, `instalar-geoip`, `instalar-asn`, `validar-perfil`,
  `validar-alertas`, `verificar-traza`, `podar-trazas`). Perfil de cliente genérico
  (`deploy/perfil.ejemplo.yml`).
- **Postura con Nmap** (`mdr escanear`): sin postura, los ataques a servicios quedan con confianza 0,5 y
  no se automatizan.
- **Geolocalización y ASN reales**, offline, con las bases DB-IP Lite (`TRIAJE_GEOIP`, `TRIAJE_ASN`); sin
  base no se inventa nada. Atribución de la licencia al pie del menú.
- **Manuales:** de usuario (laboratorio y consola) y de producción (para el cliente), ambos en PDF.

### Cambiado
- La **pausa de la automatización persiste** (`pausa.json`, junto a la traza): sobrevive al reinicio.
- El **SLA** de la consola es el del daemon (`TRIAJE_SLA_SEG`), el mismo de métricas e informe.
- **Conectividad:** la auditoría se encadena en la traza firmada (`auditoria_conectividad`); interruptor
  `TRIAJE_CONECTIVIDAD_DESACTIVADA`; sustituir una clave del host ya fijada exige confirmarlo
  explícitamente (`reemplazar`); `TRIAJE_CONECTIVIDAD` fuera del directorio de estado impide arrancar.
- Las alertas de un agente Wazuh real sin línea syslog (FIM: `syscheck`) se asignan al agente.
- Estado de servicios lee el monitor del cliente (`TRIAJE_SALUD`); sin él, «sin datos».

### Corregido
- `deploy/triaje.env.ejemplo`: systemd no quita comentarios al final de la línea, así que cada variable
  arrastraba el suyo (incluido un token de consola y una clave de traza conocidos). Ahora cada
  comentario va en su línea y `mdr configurar` escribe el fichero.
- `infra/aws/.gitignore` no ignoraba `*.tfvars` (comentario al final del patrón).
- El paquete del cliente se colaba datos sin versionar (52 MB del corpus MITRE).
- El mapa de IPs del laboratorio podía asignarse a un equipo de un perfil de cliente sin IP.
- `mdr escanear --equipos` borraba la postura del resto.

## [1.7] — 2026-11-09

### Añadido
- **Conectividad completa:** alta de equipos desde la consola (inventario, papel y reglas, paquete de
  alta en script, playbook de Ansible o sudoers, verificación de la clave del host), **papel por
  equipo** (servidor, cortafuegos, puesto) que acota el sudoers, **deriva del sudoers** (lo que sobra y lo
  que falta, con paquete de corrección) y **rotación de la clave del conector** sin dejar a ningún
  equipo sin acceso.

## [1.6] — 2026-11-04

### Añadido
- **Acceso a la consola por token:** pantalla de entrada, un token por operador
  (`TRIAJE_CONSOLA_OPERADORES`), límite de intentos, y **quién decidió** cada aprobación, reversión y
  cambio (no repudio).

## [1.5] — 2026-11-04

### Añadido (consola)
- **Editor de Políticas de respuesta:** postura de automatización por familia, zona y equipo, que solo
  puede **quitar** automatización respecto al perfil; overlay operativo auditado y cambio en vivo.
- **Rediseño de la consola:** menú por actividad con contadores, Panel con «Te toca», bandeja de
  Aprobaciones, Contenciones, Decisiones e Incidentes nuevos, Red en árbol, Trazas con inspector y
  prueba de la cadena, Estado de servicios con frescura y cascada, **Informe en PDF** como documento A4.
  Resumen ejecutivo y Campañas se funden en Informe e Incidentes.


### Automatización
- **CI con GitHub Actions** (`.github/workflows/ci.yml`): en cada push/PR a `main` corre las mismas
  puertas que en local — las **6 suites Python**, el **gate del visor** (typecheck + vitest + build) y la
  **validación de la IaC** (`tofu fmt -check` + `tofu validate`, sin tocar ninguna cuenta AWS). Sin
  secretos ni credenciales.

### Documentación
- **Informe (LaTeX) al día con v1.3/v1.4 + AWS**, sin tocar lo canónico: conteos de pruebas en la
  metodología (motor 1061, visor 281) y el párrafo del visor en las conclusiones ampliado a las **quince
  vistas** y a lo nuevo (trabajar por **incidente** = campaña /24 con su caso, **línea de tiempo** del
  ataque, **playbook** de solo lectura por familia, **resumen ejecutivo** por periodo), más una mención
  al **despliegue como IaC (OpenTofu) validada**. Resultados (ip6) y resumen (ip0) siguen congelados. PDF recompilado.

### Añadido (infraestructura / despliegue)
- **IaC del despliegue en AWS (fase 1)** en [`infra/aws/`](infra/aws/) con **OpenTofu**: VPC con subred
  **privada** + endpoints VPC (SSM + S3), EC2 del **MDR** (daemon + visor, `systemd` de `deploy/`) + EBS
  cifrado para la traza, EC2 **GPU opcional** para el LLM (`llm_habilitado`, apagado por defecto por
  coste), rol IAM mínimo (SSM + lectura de secretos) y acceso del analista por **túnel SSM** (sin puerto
  público). Distingue **runtime sin egreso** (RNF-01) del **bootstrap** (egreso temporal opcional,
  `egreso_bootstrap`, o AMI horneada / artefactos en S3). **Validada** con `tofu validate` (OpenTofu
  1.13.2, proveedor AWS 5.100.0) — fase 1 completa; falta el `apply` real (decisión del tutor
  industrial). No toca el motor ni el canónico. Doc: el diseño `despliegue-aws-opentofu.md` y el
  **briefing para el tutor industrial** `briefing-reunion-despliegue-aws.md`.

## [1.4] — 2026-10-28 · Operación estilo MDR comercial: incidentes, políticas, cronología y resumen ejecutivo

Cuatro vistas que acercan el prototipo a cómo opera un MDR comercial, todas **aditivas** (no tocan el
motor de decisión ni las cifras canónicas de la evaluación): trabajar **por incidente** (campaña /24)
con su propio caso, un **playbook** de solo lectura por familia, la **línea de tiempo** del ataque
(detección + respuesta) y un **resumen ejecutivo** por periodo para dirección. Cierra el desarrollo del
visor por nuestra parte (cambios futuros, solo por consejo del tutor). v1.4 no re-basa v1.0/v1.1/v1.2/v1.3.

### Añadido (visor)
- **Vista «Resumen ejecutivo» (para dirección)**: una página por **periodo** (reusa `getMetricas{desde,
  hasta}`; coherente, no mezcla con la ventana viva) con titulares de negocio (amenazas, tasa FP,
  contenidas en automático vs a revisión humana, MTTR mediano, % dentro de SLA), **top amenazas por
  familia** y **top ubicaciones por país**, acciones tomadas y cobertura ATT&CK; exportable a PDF.
  `metricas()` se amplía (aditivo) con `por_familia` (de `contexto.familia`) y `por_pais`
  (`actores.geolocalizar` **offline**, memoizado). `Kpi`/`Tarjeta` extraídos a `bits.tsx` (sin duplicar
  con «Métricas e informe»). No toca el motor ni el canónico.
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
  no puede): `docs/pruebas/evaluar-llm-en-gpu.md`.
