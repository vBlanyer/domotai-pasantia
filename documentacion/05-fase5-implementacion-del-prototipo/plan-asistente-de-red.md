# Asistente de red — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Estado (11/11/2026): implementado en la rama `asistente-de-red`** y ensayado de punta a punta en el
> laboratorio `oficina`; no se integra en `main` hasta que el usuario lo pruebe. Decisiones del camino: la
> huella SSH sale de `ssh-keyscan` y el escaneo no usa `-sV` (el Nmap de Alpine no trae NSE); los nombres del
> SIEM se sugieren desde la traza y la cola de aprobaciones (el escaneo no genera alertas); un escaneo hecho
> con `mdr descubrir` también se revisa en la consola.

**Goal:** Que un técnico describa una red nueva al MDR desde la consola a partir de un escaneo con Nmap, y la
pruebe a mano en un laboratorio nuevo (`oficina`).

**Architecture:** El descubrimiento (Nmap con argumentos fijos, salida XML) y la propuesta (borrador →
`perfil.yml`, `postura.json`, `politica.yml`) son funciones puras en `prototipo/servicio/`; una API nueva
(`asistente_web.py`, mismo patrón que `conectividad_web.py`) las expone a una vista nueva del visor en tres
pasos. La consola **nunca escribe el perfil vivo**. Una instalación nueva arranca con un **perfil mínimo**.

**Tech Stack:** Python 3 (stdlib + PyYAML, `xml.etree` para la salida de Nmap), unittest; React/TS + zod +
vitest; Containerlab con la imagen `banco-nodo:1` (trae nmap, sshd, iptables, python3).

**Spec:** [`documentacion/04-fase4-diseno-de-arquitectura/asistente-de-red.md`](../04-fase4-diseno-de-arquitectura/asistente-de-red.md)
· Mockup: https://claude.ai/artifact/YFPUdzq8afwbqsHyyoFckA

## Global Constraints

- La consola nunca escribe `perfil.yml`, `postura.json` ni `politica.yml` del servicio: solo los ofrece para descargar.
- Escanear y guardar el borrador exigen operador identificado (mapa de tokens), como Conectividad; sin mapa, 403 salvo `TRIAJE_ASISTENTE_ABIERTO=1` (opt-in de laboratorio, como `TRIAJE_CONECTIVIDAD_ABIERTA`).
- Escanear exige `autorizado: true` en la petición; operador, rangos, dirección externa y hora van a la traza firmada (`tipo: "auditoria_asistente"`).
- Argumentos de Nmap fijos; del usuario solo entran: rangos IPv4 privados (`ipaddress.is_private`) con prefijo ≥ /22 (máximo 8 rangos), una IPv4 externa, `ritmo ∈ {"suave","normal"}`, `puertos = "comunes"` o lista de enteros 1–65535 (máximo 100). Nunca texto libre en la línea de órdenes.
- Un escaneo a la vez; plazo por equipo `120s` (como `mdr escanear`); plazo total de cada orden Nmap 1200 s.
- El escaneo y el conector salen del nodo de gestión en el laboratorio (`TRIAJE_NODO_GESTION` → `docker exec`); sin esa variable, del propio equipo.
- Nada inventado: un camino que el traceroute no ve queda «sin camino» y lo completa el técnico.
- El motor de decisión no cambia; `evaluacion/tests` debe dar las mismas cifras.
- Contrato de capas (`test_arquitectura`): todo el código nuevo de `servicio/` importa solo de `entrada`, `motor`, `accion`, `explicacion`, `servicio`.
- Español en todo texto visible; ninguna mención a «v2» sin enlazar `documentacion/00-general/v2-trabajo-aplazado.md`.
- No push; commits locales en la rama `asistente-de-red`.

## Review Focus

1. **Traceroute sin privilegios o cortafuegos mudo** (Nmap sin root, o un salto sin respuesta): el equipo queda con `saltos: null` o con un hueco; el borrador no inventa `gateway`, lo marca y la validación lo lista. → `test_traceroute_ausente_no_inventa_gateway` (tarea 4), `test_salto_mudo_queda_como_hueco` (tarea 3).
2. **El mismo cortafuegos visto por varias IPs** (una por interfaz, todas en los rangos): se agrupan por huella SSH y quedan como un solo cortafuegos con sus `interfaces`; sin huella, salen separados y con aviso. → `test_interfaces_de_un_cortafuegos_se_agrupan_por_huella` (tarea 4).
3. **Entradas hostiles en la petición de escaneo** (`"10.0.0.0/24 --script=x"`, `0.0.0.0/0`, un rango público, `puertos: "22;rm"`): 400 sin llegar nunca a la lista de argumentos. → `test_entradas_hostiles_no_llegan_a_nmap` (tarea 3), `test_escanear_rechaza_entradas_hostiles` (tarea 5).
4. **Nmap colgado o que falla a mitad**: el estado vuelve a «no escaneando» con el error, el descubrimiento anterior se conserva, y un segundo escaneo durante el primero da 409. → `test_fallo_de_nmap_conserva_el_descubrimiento_anterior`, `test_segundo_escaneo_simultaneo_409` (tarea 5).
5. **La IP del MDR dentro de los rangos escaneados**: no sale como equipo descubierto; entra como `mdr` en la zona «Gestión». → `test_el_mdr_no_es_un_equipo_descubierto` (tarea 4).

---

### Tarea 1: laboratorio `oficina`

**Files:**
- Create: `lab/oficina/__init__.py`, `lab/oficina/red.py`, `lab/oficina/oficina.sh`, `lab/oficina/README.md`, `lab/topologias/oficina.clab.yml`
- Test: `lab/oficina/tests/__init__.py`, `lab/oficina/tests/test_topologia.py`
- Modify: `.github/workflows/*.yml` (añadir `lab/oficina` al bucle de suites)

**Interfaces:**
- Produces: `lab.oficina.red.NODOS: dict[str, {"ip","gw","segmento"}]`, `SERVICIOS: dict[str, {"puertos": list[int], "ssh": bool}]`, `CORTAFUEGOS: dict[str, {"interfaces": dict[str, str]}]`, `RANGOS: list[str]`, `GESTION = "10.99.0.10"`, `EXTERNO = "198.51.100.10"`; `python3 -m lab.oficina.red servicio <nodo>` imprime la orden de arranque de sus servicios simulados (vacía si no tiene).

Red (fuente única en `red.py`; la topología debe coincidir):

| Nodo | IP | Puerta | Servicios simulados | sshd |
|---|---|---|---|---|
| `internet` | 198.51.100.10 | 198.51.100.1 | — | no |
| `fw-borde` | 198.51.100.1 · 10.99.0.1 · 172.16.10.1 · 10.0.0.1 | — | — | sí |
| `fw-interno` | 10.0.0.2 · 10.20.0.1 | 10.0.0.1 | — | sí |
| `mdr` | 10.99.0.10 | 10.99.0.1 | — (Nmap; aquí vivirán la clave y el known_hosts del conector) | no |
| `srv-web01` | 172.16.10.10 | 172.16.10.1 | 80, 443 | sí |
| `srv-correo01` | 172.16.10.20 | 172.16.10.1 | 25, 587, 993 | sí |
| `srv-app01` | 10.20.0.10 | 10.20.0.1 | 8443 | sí |
| `srv-db01` | 10.20.0.20 | 10.20.0.1 | 5432 | sí |
| `nas01` | 10.20.0.30 | 10.20.0.1 | 445 | sí |
| `impresora` | 10.20.0.50 | 10.20.0.1 | 80, 9100 | no |
| `puesto` | 10.20.0.77 | 10.20.0.1 | — | no |

`RANGOS = ["172.16.10.0/24", "10.20.0.0/24", "10.0.0.0/24", "10.99.0.0/24"]`. Rutas como el banco: datos por
las interfaces `eth1+`; `internet` sin ruta por defecto y con `eth0` bloqueado de salida; en cada nodo con
sshd o servicios, `iptables -A INPUT -i eth0 -p tcp -j DROP` (I2 del banco). Servicios con
`lab/banco/servicio.py` (HTTP en sus puertos), reenvío con `lab/banco/reenviador.py --nodo <nombre> --sshd …`
a Wazuh (`lab/scripts/wazuh-run.sh up`). **Sin** aprovisionar el conector.

- [x] **Step 1: Write the failing tests** en `lab/oficina/tests/test_topologia.py`:
  - `test_nombre_del_laboratorio`: el YAML tiene `name: oficina`.
  - `test_cada_nodo_tiene_su_ip_y_su_puerta`: para cada `NODOS[n]`, el `exec` de `n` en el YAML contiene `ip addr add {ip}/24` y una ruta `via {gw}`.
  - `test_los_cortafuegos_tienen_todas_sus_interfaces`: cada IP de `CORTAFUEGOS[f]["interfaces"]` aparece en el `exec` de `f`, y ambos llevan `net.ipv4.ip_forward: 1`.
  - `test_internet_sin_salida_real`: el `exec` de `internet` borra la ruta por defecto y bloquea `eth0` de salida.
  - `test_nadie_trae_el_conector`: ni el YAML ni `oficina.sh` mencionan `aprovisionar` ni `triaje` como usuario.
  - `test_servicios_simulados`: `red.orden_servicio("impresora")` contiene `--puerto 80` y `--puerto 9100`; `red.orden_servicio("puesto") == ""`.
  - `test_rangos_cubren_a_todos`: toda IP de `NODOS` salvo `internet` está en algún `RANGOS`.
- [x] **Step 2: Run** `PYTHONPATH=. python3 -m unittest discover -s lab/oficina/tests -p "test_*.py"` — Expected: FAIL (`ModuleNotFoundError: lab.oficina`).
- [x] **Step 3: Implement** `red.py`, `oficina.clab.yml`, `oficina.sh` con `up | down | status | test | atacar` (`up` aborta si el banco o la red pequeña están levantados, igual que `banco.sh`; `test` comprueba desde `mdr` que llega a cada IP de datos y que `internet` llega a `srv-web01:22` por `fw-borde`; `atacar` lanza desde `internet` una fuerza bruta SSH de 10 intentos con `sshpass` contra `srv-web01`) y `README.md` (qué es, levantar, bajar, que **no** se aprovisiona).
- [x] **Step 4: Run** las pruebas del Step 2 — Expected: OK.
- [x] **Step 5: Verificación en vivo** (con el banco y la red pequeña bajados): `sh lab/oficina/oficina.sh up && sh lab/oficina/oficina.sh test` — Expected: todas las comprobaciones en verde; `docker exec clab-oficina-mdr nmap -sn 10.20.0.0/24` lista 10.20.0.1, .10, .20, .30, .50 y .77.
- [x] **Step 6: Commit** `feat(oficina): laboratorio oficina para probar el asistente de red`.

### Tarea 2: perfil mínimo

**Files:**
- Modify: `prototipo/motor/perfil.py`, `prototipo/herramientas/configurar.py`
- Create: `prototipo/herramientas/perfil_minimo.py`
- Test: `prototipo/tests/test_perfil_minimo.py`, `prototipo/tests/test_configurar.py`

**Interfaces:**
- Produces: `perfil.perfil_minimo(ip_gestion: str, redes: list[str]) -> dict` → `{"version": "v0", "ip_gestion": ip, "redes_internas": redes, "activos": {"mdr": {"ip": ip, "funcion": "equipo MDR (plano de gestión)", "criticidad": "critica", "servicios_prestados": []}}, "red": {"zonas": {"Gestión": ["mdr"]}}, "continuidad": {"reversibilidad_obligatoria": True, "no_cortar_gestion": True}}`; ValueError si la IP o algún rango no es válido o la lista está vacía.
- Produces: `python3 -m prototipo.herramientas.perfil_minimo --gestion IP --rango R [--rango R…] --salida F` (no pisa un fichero existente; código 1 y mensaje).

- [x] **Step 1: Write the failing tests:**
  - `test_perfil_minimo_valida_sin_avisos`: `perfil.validar(perfil_minimo("10.99.0.10", ["10.20.0.0/24"])) == []`.
  - `test_perfil_minimo_rechaza_entradas_malas`: ValueError con `("10.99.0", ["10.20.0.0/24"])`, `("10.99.0.10", [])`, `("10.99.0.10", ["nope"])`.
  - `test_el_mdr_esta_en_gestion`: `red.zonas["Gestión"] == ["mdr"]` y `activos["mdr"]["ip"] == ip_gestion`.
  - `test_cli_no_pisa`: con la salida ya existente, código 1 y el fichero intacto.
  - En `test_configurar.py`: `test_sin_perfil_escribe_el_minimo_y_arranca` — `Guion(self.perfil, "m", "10.99.0.10", "10.20.0.0/24, nope, 172.16.10.0/24", "1", self.alerts, "", "")` → el perfil escrito es `perfil_minimo("10.99.0.10", ["10.20.0.0/24", "172.16.10.0/24"])`, se avisa de «nope», hay `systemctl restart`, y **no** se fija `TRIAJE_POLITICA` (la plantilla de política nombra equipos que el perfil mínimo no tiene).
  - Cambiar los tests existentes que copian la plantilla: la respuesta pasa de `"s"` a `"p"` (`test_sin_perfil_copia_la_plantilla_y_no_arranca`, `test_con_perfil_nuevo_instala_la_politica_…`, `test_perfil_nuevo_no_pisa_una_politica_que_ya_existe`).
- [x] **Step 2: Run** `PYTHONPATH=. python3 -m unittest prototipo.tests.test_perfil_minimo prototipo.tests.test_configurar` — Expected: FAIL.
- [x] **Step 3: Implement.** En `configurar`, si el perfil no existe: «No existe. ¿Empiezo con un perfil mínimo para el asistente de red (m) o copio la plantilla para editarla a mano (p)?», por defecto `m`. `m`: pregunta «IP de este equipo MDR en la red del cliente» y «Rangos de la red del cliente, separados por comas»; omite lo mal escrito con aviso; sin IP válida o sin ningún rango, no escribe nada y deja `perfil_listo = False`; si no, escribe el mínimo y el servicio arranca. `p`: lo de hoy (plantilla + política).
- [x] **Step 4: Run** las pruebas del Step 2 y la suite completa del prototipo — Expected: OK.
- [x] **Step 5: Commit** `feat(asistente): perfil mínimo para arrancar una instalación nueva`.

### Tarea 3: descubrimiento con Nmap

**Files:**
- Create: `prototipo/servicio/descubrimiento.py`, `prototipo/herramientas/descubrir.py`, `prototipo/tests/fixtures/nmap/` (XML de muestra)
- Modify: `bin/mdr` (orden `descubrir`)
- Test: `prototipo/tests/test_descubrimiento.py`

**Interfaces:**
- Produces: `validar_peticion(cuerpo: dict) -> dict` (normaliza `{"rangos","externo","ritmo","puertos"}`; ValueError con el motivo, según las Global Constraints).
- Produces: `argumentos_vivos(peticion) -> list[str]`, `argumentos_detalle(peticion, ips: list[str]) -> list[str]`, `argumentos_salida(peticion) -> list[str]`:
  - vivos: `["nmap", "-sn", *ritmo, "-oX", "-", *rangos]`
  - detalle: `["nmap", "-sV", "--version-light", "--script", "ssh-hostkey", "--traceroute", "--host-timeout", "120s", *ritmo, *puertos, "-oX", "-", *ips]` con `puertos = ["--top-ports", "1000"]` o `["-p", "22,80,…"]`
  - salida: `["nmap", "-sn", "--traceroute", *ritmo, "-oX", "-", externo]`
  - `ritmo`: suave `["-T3", "--max-rate", "100"]`, normal `["-T4"]`
- Produces: `parsear_xml(texto: str) -> list[dict]`, por equipo «up»: `{"ip", "dns", "mac", "fabricante", "puertos": [{"puerto": int, "servicio", "producto", "version"}], "huella_ssh": str|None, "saltos": list[str|None]|None}`; `saltos` son los saltos **sin** el propio equipo, en orden de TTL, `None` en un TTL sin respuesta; `saltos: None` si no hay `<trace>`.
- Produces: `ejecutor_nmap(entorno=os.environ) -> Callable[[list[str]], tuple[int, str]]` (con `TRIAJE_NODO_GESTION`, `docker exec <nodo> …`; sin ella, local; plazo 1200 s; sin shell; `conector._env_filtrado()`).
- Produces: `descubrir(peticion, correr, gestion: str, operador: str, ahora: str) -> dict` → `{"version": 1, "fecha", "operador", "gestion", "rangos", "externo", "ritmo", "puertos", "equipos": [...], "salida": list|None, "traceroute": bool}`; excluye `gestion` de `equipos`; lanza RuntimeError con el error de Nmap si una orden falla.
- Produces: `mdr descubrir --gestion IP --rango R… --externo IP [--ritmo suave|normal] [--puertos 22,80] --salida descubrimiento.json` (para producción sin privilegios en el servicio: lo corre `sudo`).

- [x] **Step 1: Fixtures.** Tres XML de Nmap escritos a mano con la forma real (`<host><status state="up"/><address addrtype="ipv4"/><address addrtype="mac" vendor=…/><hostnames><hostname name=… type="PTR"/></hostnames><ports><port protocol="tcp" portid=…><state state="open"/><service name product version/><script id="ssh-hostkey"><table><elem key="fingerprint">…</elem></table></script></port></ports><trace><hop ttl ipaddr/></trace></host>`), con la red de la tarea 1: `vivos.xml`, `detalle.xml` (incluye un salto ausente en un equipo y dos IPs de `fw-borde` con la misma huella), `salida.xml`.
- [x] **Step 2: Write the failing tests:**
  - `test_parsea_puertos_servicios_y_huella`, `test_parsea_saltos_sin_el_propio_equipo`, `test_salto_mudo_queda_como_hueco` (TTL 2 ausente → `[ "10.99.0.1", None ]`), `test_sin_trace_saltos_es_none`.
  - `test_argumentos_fijos`: los tres argv exactos de las Interfaces para una petición dada.
  - `test_entradas_hostiles_no_llegan_a_nmap`: ValueError con `rangos=["10.0.0.0/24 --script=x"]`, `["0.0.0.0/0"]`, `["8.8.8.0/24"]`, `["10.0.0.0/16"]`, 9 rangos, `externo="10.0.0.0/24"`, `ritmo="loco"`, `puertos="22;rm"`, `puertos=[0]`, 101 puertos.
  - `test_descubrir_excluye_al_mdr_y_junta_las_tres_pasadas` (con un `correr` falso que devuelve los fixtures).
  - `test_un_fallo_de_nmap_es_runtimeerror` (`correr` devuelve `(1, "…")`).
  - `test_ejecutor_por_nodo_de_gestion`: con `TRIAJE_NODO_GESTION=x`, el argv empieza por `["docker", "exec", "x", "nmap"]` (con `subprocess.run` simulado).
- [x] **Step 3: Run** `PYTHONPATH=. python3 -m unittest prototipo.tests.test_descubrimiento` — Expected: FAIL.
- [x] **Step 4: Implement** con `xml.etree.ElementTree`; el CLI reutiliza `validar_peticion`, `ejecutor_nmap` y `descubrir`.
- [x] **Step 5: Run** las pruebas — Expected: OK.
- [x] **Step 6: Verificación en vivo** (laboratorio arriba): `TRIAJE_NODO_GESTION=clab-oficina-mdr python3 -m prototipo.herramientas.descubrir --gestion 10.99.0.10 --rango 172.16.10.0/24 --rango 10.20.0.0/24 --rango 10.0.0.0/24 --rango 10.99.0.0/24 --externo 198.51.100.10 --salida /tmp/…/d.json` (en el scratchpad) — Expected: 10.99.0.10 no aparece; `srv-app01` (10.20.0.10) con `saltos == ["10.99.0.1", "10.0.0.2"]`; la impresora con 80 y 9100 y sin huella; `salida == ["10.99.0.1"]`. Si la salida real de Nmap difiere de los fixtures, corregir los fixtures para que la reflejen (y anotarlo como Ruling).
- [x] **Step 7: Commit** `feat(asistente): descubrimiento con Nmap (vivos, servicios, caminos)`.

### Tarea 4: propuesta (borrador, perfil, postura, política, validación)

**Files:**
- Create: `prototipo/servicio/asistente_red.py`
- Test: `prototipo/tests/test_asistente_red.py` (usa el descubrimiento de los fixtures de la tarea 3)

**Interfaces:**
- Consumes: el `dict` de `descubrimiento.descubrir`.
- Produces: `borrador_inicial(desc: dict) -> dict` → `{"version": 1, "basado_en": desc["fecha"], "gestion", "redes_internas": desc["rangos"], "salida": desc["salida"], "equipos": {ip: {"incluido": bool, "nombre": str, "zona": str|None, "papel": "servidor"|"cortafuegos"|"fragil"|"desconocido", "criticidad": "media", "no_tocar": False, "depende_de": [], "funcion": "", "gateway": ip|None, "interfaces": [ip], "servicios": [int], "deducido": bool, "sin_camino": bool}}}`.
- Produces: `aplicar_cambios(borrador: dict, cambios: dict) -> dict` (solo claves conocidas por equipo: `incluido, nombre, zona, papel, criticidad, no_tocar, depende_de, funcion, gateway`; ValueError con lo demás).
- Produces: `perfil_desde_borrador(borrador) -> dict`, `postura_desde(desc, borrador) -> dict` (formato de `escanear_postura`: `{"version_herramienta", "timestamp", "nodos": {nombre: [{"puerto", "servicio", "estado": "open"}]}}`), `politica_desde(borrador, fecha) -> dict`.
- Produces: `validar(borrador, catalogo) -> {"errores": [str], "avisos": [str]}` y `nombres_del_siem(registros: list[dict], perfil: dict) -> list[str]`.

Reglas de deducción (las fijan los tests; no las deciden ellos solos):
- **Cortafuegos:** IP que aparece como salto intermedio en algún `saltos` o en `salida`. Las IPs con la misma `huella_ssh` que un cortafuegos son **sus interfaces**: se quitan de la lista y van a `interfaces`; la clave del cortafuegos es la IP vista como salto. Sin huella no se agrupa (aviso).
- **Cadena hacia fuera:** los cortafuegos de `salida`, en orden: cada uno tiene de `gateway` el siguiente; el último no lleva (borde). Un cortafuegos que no está en `salida` toma de `gateway` el salto anterior a él en el camino donde aparece (`deducido: True`).
- **Equipo:** `gateway` = su último salto; `saltos: None` → `gateway: None`, `sin_camino: True`. `zona` propuesta: `"Zona " + subred /24`, igual para los que comparten `gateway` y subred.
- **Papel:** cortafuegos si lo es; `fragil` si no tiene 22 y tiene 9100, 515, 631 o 554; `servidor` si tiene 22; si no, `desconocido`. `incluido`: verdadero salvo `desconocido` sin puertos.
- **Nombre:** la parte antes del primer punto del DNS, o `""`.
- **Perfil:** activos = incluidos no cortafuegos + `mdr` (como `perfil_minimo`); `topologia` = servidores incluidos con `gateway`, sin `no_tocar` (`rol: host_victima`) + cortafuegos incluidos (`rol: firewall_perimetral`, `gateway` por nombre); `red.zonas` por nombre de zona + `"Gestión": ["mdr"]`; `red.enlaces`: cada activo → nombre de su cortafuegos (el `mdr` → el primero de `salida`), el cortafuegos borde → `internet`, cada cortafuegos → su `gateway`; `red.nodos = {"internet": {"tipo": "externo"}}`; frenos de `continuidad` como el mínimo; **sin** reglas de política.
- **Política:** `{"politica": {"version": 1, "aprobada_por": "[pendiente de aprobación]", "fecha"}, "confianza": {"administradores": [gestion], "socios_criticos": []}, "respuesta_automatica": {"certeza_minima": 0.9, "por_defecto": "con_analista", "si_afecta_a_un_servicio": "con_analista", "solo_observar": "con_analista", "equipos_propios": "con_analista"}}`.
- **Errores** (bloquean exportar): cada aviso de `perfil.validar(perfil)`; incluido sin nombre; nombres repetidos; un `gateway` hacia un cortafuegos excluido o inexistente; ningún cortafuegos sin `gateway` habiendo cortafuegos; dependencia hacia un equipo no incluido; `pe.validar_politica(politica, perfil, catalogo)`. **Avisos:** cada equipo incluido fuera de `topologia` («su contención va a los cortafuegos perimetrales: …»); cada `sin_camino`; cada `deducido`; cada descartado con puertos; `traceroute: False`.
- **`nombres_del_siem`:** los valores de `activo` de los registros de decisión (sin `tipo` o `tipo == "decision"`) que no están en `perfil["activos"]` ni son `"desconocido"`, por frecuencia descendente.

- [x] **Step 1: Write the failing tests:**
  - `test_el_mdr_no_es_un_equipo_descubierto`, `test_interfaces_de_un_cortafuegos_se_agrupan_por_huella`, `test_cadena_hacia_fuera` (`fw-interno.gateway == "10.99.0.1"`, borde sin `gateway`), `test_gateway_y_zona_de_cada_equipo`, `test_papeles` (impresora `fragil`, puesto `desconocido` y no incluido), `test_traceroute_ausente_no_inventa_gateway`.
  - `test_perfil_de_la_oficina_valida`: con nombres puestos a `srv-web01 … impresora` y `fw-borde`/`fw-interno`, `perfil.validar(perfil_desde_borrador(b)) == []`, `topologia["srv-app01"]["gateway"] == "fw-interno"`, `topologia["fw-interno"]["gateway"] == "fw-borde"`, `"gateway" not in topologia["fw-borde"]`, `"srv-db01" not in topologia` con `no_tocar`, e `impresora` fuera por frágil.
  - `test_la_red_dibuja_lo_mismo`: `red.red_de(perfil)` (prototipo/servicio/red.py) no devuelve avisos y tiene los nodos y zonas esperados.
  - `test_politica_valida_con_ese_perfil`, `test_postura_por_nombre`.
  - `test_errores_bloqueantes` (sin nombre, repetido, dependencia a excluido, gateway a excluido) y `test_avisos_fuera_de_cadena`.
  - `test_aplicar_cambios_rechaza_claves_desconocidas`, `test_nombres_del_siem`.
- [x] **Step 2: Run** `PYTHONPATH=. python3 -m unittest prototipo.tests.test_asistente_red` — Expected: FAIL.
- [x] **Step 3: Implement** según las reglas de arriba.
- [x] **Step 4: Run** las pruebas y `test_arquitectura` — Expected: OK.
- [x] **Step 5: Commit** `feat(asistente): de lo descubierto a una propuesta de perfil, postura y política`.

### Tarea 5: API del asistente

**Files:**
- Create: `prototipo/servicio/asistente_web.py`
- Modify: `prototipo/servicio/tablero.py` (rutas y `crear_servidor`), `prototipo/servicio/stream.py` (pasa la ruta de la traza), `prototipo/servicio/tablero.py:_NO_DECISIONES` (+ `auditoria_asistente`)
- Test: `prototipo/tests/test_asistente_web.py`

**Interfaces:**
- Consumes: tareas 3 y 4.
- Produces (ficheros junto a la traza): `asistente-descubrimiento.json`, `asistente-borrador.json` (escritura atómica, 0600).
- Produces: `instalar(srv, ruta_traza)`; `srv.asistente_correr` inyectable (por defecto `descubrimiento.ejecutor_nmap()`).
- Produces (HTTP):
  - `GET /api/asistente` → `{"escaneando": bool, "error": str|None, "descubrimiento": {...}|None, "borrador": {...}|None, "nombres_siem": [str], "por_defecto": {"gestion": perfil.ip_gestion, "rangos": perfil.redes_internas}}`
  - `POST /api/asistente/escanear` `{rangos, externo, ritmo, puertos, autorizado}` → 202 `{"escaneando": true}`; 403 sin operador; 400 entrada mala o `autorizado` no verdadero; 409 si ya hay uno. Corre en un hilo; al terminar guarda el descubrimiento **y un borrador inicial nuevo**; si falla, guarda solo el error.
  - `POST /api/asistente/borrador` `{cambios: {ip: {...}}}` → 200 con el borrador (403 sin operador; 400 si `aplicar_cambios` lanza).
  - `GET /api/asistente/propuesta` → `{"perfil_yaml", "postura_json", "politica_yaml", "validacion": {"errores","avisos"}, "red": estado_red(perfil_propuesto, [], [], None)}`; 404 sin borrador. Nunca escribe nada.
- Cada escaneo (inicio y fin) y cada cambio del borrador → `srv.estado.auditar_en_traza({"tipo": "auditoria_asistente", "operador", "accion", "detalle", "timestamp", "id_decision": "asistente~<ts>"})`.

- [x] **Step 1: Write the failing tests** (servidor real en puerto 0, `asistente_correr` falso con los fixtures):
  - `test_sin_operador_403`, `test_escanear_rechaza_entradas_hostiles`, `test_sin_autorizacion_400`.
  - `test_escanear_y_ver_el_borrador` (esperar al hilo; `GET` trae descubrimiento y borrador inicial).
  - `test_segundo_escaneo_simultaneo_409` (`correr` que bloquea en un `threading.Event`).
  - `test_fallo_de_nmap_conserva_el_descubrimiento_anterior`.
  - `test_borrador_persiste_tras_reiniciar` (otro `crear_servidor` con la misma ruta lo lee).
  - `test_propuesta_no_escribe_nada` (el perfil del servidor y los ficheros de `TRIAJE_PERFIL`/`TRIAJE_HALLAZGOS` no cambian; `red` trae nodos).
  - `test_el_escaneo_queda_en_la_traza` (registro `auditoria_asistente` con operador y rangos; `traza.verificar` válida) y que no cuenta como decisión.
- [x] **Step 2: Run** `PYTHONPATH=. python3 -m unittest prototipo.tests.test_asistente_web` — Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** la suite del prototipo — Expected: OK.
- [x] **Step 5: Commit** `feat(asistente): API del asistente de red (fail-closed, auditada)`.

### Tarea 6: vista «Asistente de red»

**Files:**
- Create: `visor/src/components/AsistenteRed.tsx`, `visor/src/components/AsistenteRed.css`, `visor/src/components/AsistenteRed.test.tsx`
- Modify: `visor/src/api.ts` (esquemas zod y `getAsistente`, `escanearRed`, `guardarBorrador`, `getPropuestaRed`), `visor/src/App.tsx` (entrada de menú `{ id: "asistente", nombre: "Asistente de red" }` en «Configurar», tras Políticas), `visor/src/datos.ts`/`trazas.ts`/`aprobaciones.ts` (`auditoria_asistente` no es decisión y es «sistema», con `describirSistema` → título «Asistente de red»)

Las tres pantallas del mockup, con estos comportamientos (lo visual, del mockup):
1. **Escanear:** rangos (chips con quitar/añadir, por defecto `por_defecto.rangos`), IP del MDR (`por_defecto.gestion`, solo lectura), dirección de fuera, ritmo, puertos, casilla de autorización; «Escanear» deshabilitado sin la casilla; mientras `escaneando`, aviso y sondeo cada 3 s; error visible.
2. **Revisar:** tabla por equipo con incluir, nombre (campo con sugerencias de `nombres_siem` vía `<datalist>`), IP, servicios, llega por, zona, papel, criticidad, «no tocar»; cada cambio llama a `guardarBorrador` (con un retardo de 600 ms); `MapaRed` con `propuesta.red`; dependencias por equipo; «Falta para exportar» = `validacion.errores`.
3. **Validar y exportar:** errores y avisos; descarga de los tres ficheros (Blob, como «Exportar propuesta» de Políticas); vista previa por pestañas; pasos siguientes; la frase «La consola no escribe el perfil vivo».

- [x] **Step 1: Write the failing tests** (vitest, `useSondeo` simulado como en `Politicas.test.tsx`):
  - «Escanear deshabilitado sin autorización»; «envía rangos, externo, ritmo y puertos»; «muestra el error del último escaneo».
  - «la tabla sale del borrador y sugiere nombres del SIEM»; «cambiar el nombre guarda el borrador».
  - «con errores no deja descargar»; «descarga perfil.yml» (Blob con el `perfil_yaml`); «avisa de los equipos fuera de la cadena».
  - En `datos.test.ts`/`trazas.test.ts`: `auditoria_asistente` no es decisión y es «sistema».
- [x] **Step 2: Run** `cd visor && npx vitest run src/components/AsistenteRed.test.tsx` — Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** `cd visor && npx vitest run && npx tsc --noEmit -p . && npm run build` — Expected: todo en verde.
- [x] **Step 5: Commit** `feat(asistente): vista Asistente de red en la consola`.

### Tarea 7: arranque en el laboratorio y documentación

**Files:**
- Modify: `lab/oficina/oficina.sh` (orden `mdr`), `lab/oficina/README.md`
- Modify: `documentacion/07-fase7-documentacion-e-informe-final/manual-de-usuario.md` (sección «Instalar una red nueva con el asistente (laboratorio oficina)»), `manual-de-produccion.md` (§6: respuesta `m` de `mdr configurar`; §7: «Con el asistente de red»; Anexo B: `mdr descubrir`), `RUNBOOK.md`, `CHANGELOG.md`, `deploy/README.md`, `documentacion/05-fase5-implementacion-del-prototipo/README.md`, este plan (estado)
- Test: `lab/oficina/tests/test_topologia.py` (+ `test_orden_mdr`)

`oficina.sh mdr`: crea `run/oficina/perfil.yml` con `perfil_minimo` si no existe y `run/oficina/postura.json` (`{"nodos": {}}`) si no existe; exporta `TRIAJE_NODO_GESTION=clab-oficina-mdr`, `TRIAJE_SSH_MODO=clave`, `TRIAJE_ASISTENTE_ABIERTO=1`, `TRIAJE_CONECTIVIDAD_ABIERTA=1`; mata el daemon anterior como `reiniciar.sh`; arranca `tail -F alerts.json | python3 -m prototipo.servicio.stream - run/oficina/perfil.yml run/oficina/postura.json --salida run/oficina/trazas-<fecha>.jsonl --web`. El recorrido del manual de usuario: levantar → `oficina.sh mdr` → Conectividad: generar la clave del conector → Asistente: escanear, revisar, exportar → copiar los tres ficheros a `run/oficina/` y `oficina.sh mdr` otra vez → Conectividad: por equipo, paquete de alta ejecutado con `docker exec` (simula al administrador del equipo), fijar huella, probar → `oficina.sh atacar` → la contención en la Consola y en Red.

- [x] **Step 1: Write the failing test** `test_orden_mdr`: `oficina.sh` contiene `TRIAJE_NODO_GESTION=clab-oficina-mdr`, `perfil_minimo`, `run/oficina/perfil.yml` y **no** contiene `aprovisionar`.
- [x] **Step 2: Run** — Expected: FAIL.
- [x] **Step 3: Implement** la orden y la documentación.
- [x] **Step 4: Run** todas las suites (`prototipo`, `evaluacion`, `lab/dataset`, `lab/banco`, `lab/portatil`, `lab/geo_demo`, `lab/oficina`, visor) — Expected: OK, y `evaluacion/tests` con las mismas cifras.
- [x] **Step 5: Ensayo en vivo** (lo que el usuario hará a mano, una vez, para que el manual no tenga huecos): seguir el recorrido del manual de usuario de punta a punta. Expected: la propuesta valida sin errores con los nombres reales; tras instalar y dar de alta, `oficina.sh atacar` acaba en una contención verificada en `fw-borde` o `srv-web01`, y la vista Red muestra las tres zonas y los dos cortafuegos. Cada paso que exija algo que el manual no dice se corrige en el manual (o en el código) y se anota como Ruling.
- [x] **Step 6: Commit** `docs(asistente): laboratorio oficina, recorrido y manuales`.

## Fuera de este plan

- Volver a escanear un cliente instalado y comparar con el perfil vigente (deriva).
- Editar zonas o cortafuegos en vivo; aplicar el perfil desde la consola.
- Descubrir dependencias entre servicios; equipos que no sean Linux con SSH.
- Integrar en `main`, actualizar el informe y el push: después de la prueba del usuario.
