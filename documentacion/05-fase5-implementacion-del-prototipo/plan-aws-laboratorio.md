# Variante «laboratorio» del despliegue en AWS — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `variante = "laboratorio"` en `infra/aws` levanta en una sola máquina el banco, Wazuh y el MDR como en local, probado contra AWS Emulator; y los scripts del laboratorio arrancan sin nadie delante.

**Architecture:** Primero se arreglan los scripts del laboratorio (fallan con código de error, esperas con tope, comprobación de alertas de punta a punta, un arranque de servicio idempotente). Después `aws_instance.mdr` cambia de tipo, disco, plantilla de arranque y nombre según `variante`; el resto de `infra/aws` se reutiliza. Por último, escenarios E–G en el emulador, inventario, costes y guía.

**Tech Stack:** sh POSIX (dash) y bash, Python 3 `unittest` (sin pytest), OpenTofu, AWS Emulator, systemd, Containerlab 0.79.0, Docker.

**Spec:** [diseno-aws-laboratorio.md](diseno-aws-laboratorio.md)

## Global Constraints

- Con `variante = "mdr"` (por defecto) el plan es **idéntico** al de hoy: los inventarios `escenario-{a,b,d}.json` no cambian y A–D siguen pasando.
- Laboratorio exige `egreso_bootstrap = true`, `llm_habilitado = false`, `mdr_version` distinta de `1.9.1` y `laboratorio_commit` de 40 hexadecimales.
- Valores por defecto: `laboratorio_tipo = "t3.xlarge"`, `laboratorio_disco_gb = 40`, tope de espera a Wazuh 600 s, Containerlab `0.79.0`.
- Clon en `/opt/mdr-laboratorio`, etiqueta `v<mdr_version>`, repositorio `https://github.com/vBlanyer/domotai-pasantia`. Traza fija en `/var/lib/mdr/trazas-laboratorio.jsonl`. Unidad `mdr-laboratorio`. Token del admin en `/root/mdr-token-admin`.
- Plantillas: `set -euo pipefail`, sin `|| true`, reintentos en las descargas, fallo cerrado; nada de `$$(` suelto (`test_plantillas_sin_doble_dolar_suelto`).
- `reiniciar.sh` no se toca. Los scripts del laboratorio se usan en local igual que hoy.
- **No bajar ni levantar el banco ni el Wazuh del equipo** sin preguntar al usuario (comparten Wazuh); no tocar el daemon del 8787. La verificación en vivo de las tareas 3 y 4 es una parada para pedir permiso.
- Emulador sin telemetría y sin credenciales reales. Commits locales en `main`, con `git commit -F <fichero>`; sin push; nunca el PDF del informe.
- No se publica la v1.9.2 en este plan (es una decisión aparte del usuario).

## Review Focus

1. **Reiniciar con la misma traza:** tras parar y encender, el daemon sigue escribiendo en el mismo fichero: la cadena debe verificarse y no debe repetir `id_decision`. Prueba en la tarea 4.
2. **`comprobar-alertas` con el MDR ya en marcha:** el evento de prueba llega también al daemon. Debe salir de un origen que el perfil bancario no contenga (escáner autorizado) o, si no lo hay, quedar documentado qué hará el MDR. Prueba en la tarea 3.
3. **Script de arranque por encima de 16 KB:** AWS lo rechaza al crear la instancia. Comprobación en la tarea 6 (`comprobar.py`, E).
4. **Commit del clon que no coincide** (etiqueta movida o repositorio cambiado): el arranque se para antes de construir nada. Prueba en la tarea 5.
5. **Encender con el EBS ausente:** la unidad no arranca el laboratorio sin `/var/lib/mdr` (`RequiresMountsFor`). Prueba en la tarea 4.

---

### Tarea 1: `banco.sh test` falla de verdad

**Files:**
- Modify: `lab/banco/banco.sh` (orden `test`)
- Create: `lab/banco/tests/test_arranque_desatendido.py`

**Interfaces:**
- Produces: `sh lab/banco/banco.sh test` → código 0 si todo pasa; 1 si falla alguna comprobación, con la línea `banco.sh test: <n> comprobación(es) fallida(s)` en stderr. La salida por pantalla de cada comprobación no cambia.
- Produces (pruebas): en el fichero de pruebas, `_ejecutar(args: list[str], docker: str, env: dict = None) -> subprocess.CompletedProcess`, que pone delante del `PATH` un `docker` falso (cuerpo sh `docker`) y ejecuta `sh lab/banco/banco.sh *args`. Las tareas 2 y 3 lo reutilizan.

- [ ] **Paso 1: pruebas que fallan** — `TestTest`: `test_pasa_con_todo_sano` (curl 200, ping ok, salud `{"estados":{"core-db":"ok"}}` → código 0); `test_falla_si_un_servicio_esta_caido` (salud con `"core-db":"caido"` → código 1, `CAIDOS` en stdout, `1 comprobación` en stderr); `test_falla_si_un_cortafuegos_no_responde` (ping sale con 1 → código 1); `test_falla_sin_datos_de_salud` (salud vacía → código 1).
- [ ] **Paso 2:** `python3 -m unittest lab.banco.tests.test_arranque_desatendido` → las tres de fallo FALLAN (hoy sale 0).
- [ ] **Paso 3:** en `test`, un contador de fallos que suma en cada `|| echo "   FALLO"` y en `CAIDOS`; al final, si es mayor que 0, la línea a stderr y `exit 1`.
- [ ] **Paso 4:** la misma orden → todas pasan; y `python3 -m unittest discover -s lab/banco/tests -t .` sin regresiones.
- [ ] **Paso 5: commit** `fix(lab): banco.sh test termina con error si falla una comprobación`.

### Tarea 2: esperas a Wazuh con tope

**Files:**
- Create: `lab/scripts/esperar-wazuh.sh`
- Modify: `lab/scripts/wazuh-run.sh:34,71`, `lab/lab.sh:32`
- Test: `lab/banco/tests/test_arranque_desatendido.py`

**Interfaces:**
- Produces: fichero para `.` (source) que define `esperar_wazuh NOMBRE`: comprueba `wazuh-analysisd is running` cada `WAZUH_ESPERA_PASO` s (4 por defecto) hasta `WAZUH_ESPERA_MAX` s (600 por defecto). Si se agota: `Wazuh (NOMBRE) no arrancó en N s` y `docker logs --tail 30 NOMBRE` a stderr, `return 1`.

- [ ] **Paso 1: pruebas que fallan** — `TestEsperaWazuh`: `test_se_agota_con_error` (docker falso que nunca informa de analysisd, `WAZUH_ESPERA_MAX=2 WAZUH_ESPERA_PASO=1` → código distinto de 0 en menos de 10 s y `no arrancó` en stderr); `test_termina_cuando_wazuh_arranca` (docker falso que sí lo informa → código 0); `test_las_tres_esperas_usan_la_funcion` (ni `wazuh-run.sh` ni `lab.sh` contienen `until docker exec`; los dos hacen `. ` de `esperar-wazuh.sh` y llaman a `esperar_wazuh`).
- [ ] **Paso 2:** ejecutarlas → FALLAN (el fichero no existe).
- [ ] **Paso 3:** crear la función y sustituir las tres esperas (`wazuh-run.sh` con `"$NAME"`, `lab.sh` con `clab-red-cliente-wazuh`). Un fallo de la espera debe parar el script (`set -e` ya está).
- [ ] **Paso 4:** pasan; y `sh -n` de los tres scripts.
- [ ] **Paso 5: commit** `fix(lab): las esperas a Wazuh tienen tope y explican el fallo`.

### Tarea 3: `banco.sh comprobar-alertas`

**Files:**
- Modify: `lab/banco/banco.sh` (orden nueva y cabecera de uso)
- Test: `lab/banco/tests/test_arranque_desatendido.py`

**Interfaces:**
- Produces: `sh lab/banco/banco.sh comprobar-alertas` → 0 con `OK: Wazuh generó la alerta 100200` cuando aparece en `alerts.json` una alerta de la regla `100200` posterior al disparo; 1 si no llega en `ALERTAS_ESPERA_MAX` s (120 por defecto). Disparo: desde `clab-banco-auditor`, una conexión TCP sin banner SSH al `sshd` de un nodo por el plano de datos (sshd registra «Did not receive identification string» → reenviador → regla 100200). El constructor elige el destino alcanzable en el banco por defecto.
- Consumes: `_ejecutar` (tarea 1).

- [ ] **Paso 1: pruebas que fallan** — `TestComprobarAlertas`: `test_falla_si_la_alerta_no_llega` (docker falso: `alerts.json` nunca crece, `ALERTAS_ESPERA_MAX=2` → código 1); `test_ok_cuando_llega` (docker falso: después del disparo `alerts.json` tiene una línea nueva con `"id":"100200"` → código 0 y `OK:`); `test_no_cuenta_alertas_anteriores` (la 100200 ya estaba antes del disparo y no llega otra → código 1); `test_origen_del_evento` (Review Focus 2: el disparo sale de `clab-banco-auditor`, activo `auditor` de tipo `gestion` en `prototipo/perfiles/bancario.yml`, y `lab/banco/README.md` dice qué decide el MDR si ve ese evento estando en marcha; el constructor lo comprueba con el motor, sin laboratorio).
- [ ] **Paso 2:** ejecutarlas → FALLAN (orden desconocida).
- [ ] **Paso 3:** implementar la orden: líneas de `alerts.json` antes (`docker exec clab-red-cliente-wazuh wc -l`), disparo, sondeo de las líneas nuevas cada 2 s hasta el tope.
- [ ] **Paso 4:** pasan.
- [ ] **Paso 5 (PARADA):** pedir permiso al usuario para comprobarlo en vivo con su banco y su Wazuh levantados (no baja nada). Con permiso: `sh lab/banco/banco.sh comprobar-alertas` → `OK`. Sin permiso: ledger `Ruling:` y seguir.
- [ ] **Paso 6: commit** `feat(lab): banco.sh comprobar-alertas comprueba Wazuh de punta a punta`.

### Tarea 4: arranque de servicio del laboratorio

**Files:**
- Create: `lab/banco/servicio-mdr.sh` (bash), `lab/banco/mdr-laboratorio.service`
- Modify: `lab/banco/README.md` (sección «Como servicio»), `RUNBOOK.md` (una línea en §2 sobre `comprobar-alertas` y `servicio-mdr.sh`)
- Test: `lab/banco/tests/test_arranque_desatendido.py`

**Interfaces:**
- Produces: `lab/banco/servicio-mdr.sh` → `cd` a la raíz del repositorio; `banco.sh down` → `lab.sh up banco` → `banco.sh aprovisionar` → `banco.sh test` → `banco.sh comprobar-alertas` (cualquier fallo: sale con error); después, las mismas variables que `reiniciar.sh` (`TRIAJE_NODO_GESTION`, `TRIAJE_SALUD_CONTENEDOR`, `TRIAJE_GEOIP`, `TRIAJE_ASN`) y `exec` de la cola de alertas de Wazuh → `python3 -m prototipo.servicio.stream - prototipo/perfiles/bancario.yml lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json --salida "${TRIAJE_SALIDA:-/var/lib/mdr/trazas-laboratorio.jsonl}" --web`.
- Produces: unidad `mdr-laboratorio.service`: `EnvironmentFile=/etc/mdr/triaje.env`, `WorkingDirectory=/opt/mdr-laboratorio`, `ExecStart=/opt/mdr-laboratorio/lab/banco/servicio-mdr.sh`, `After=`/`Requires=docker.service`, `RequiresMountsFor=/var/lib/mdr`, `Restart=on-failure`, `RestartSec=30`, `WantedBy=multi-user.target`. La tarea 5 la instala.

- [ ] **Paso 1: pruebas que fallan** — `TestServicio`: `test_rehace_el_laboratorio_en_orden` (las seis órdenes aparecen en ese orden); `test_mismas_variables_que_reiniciar` (cada `export TRIAJE_…` de `reiniciar.sh` está en `servicio-mdr.sh` con el mismo valor); `test_traza_fija_en_el_disco`; `test_bash_estricto` (`set -euo pipefail` y `bash -n` limpio); `test_unidad` (los campos de arriba; Review Focus 5: `RequiresMountsFor=/var/lib/mdr`); `test_traza_fija_sin_ids_repetidos_tras_reinicio` (Review Focus 1: dos ejecuciones de `prototipo.servicio.stream` con `lab/portatil/alerta-muestra.jsonl`, `--sin-lab` y la misma `--salida` temporal → ningún `id_decision` de tipo `decision` repetido y `prototipo.servicio.traza` verifica la cadena entera).
- [ ] **Paso 2:** ejecutarlas → FALLAN. Si `test_traza_fija_sin_ids_repetidos_tras_reinicio` falla también **sin** los ficheros nuevos, es un fallo de producto (producción usa traza fija): PARADA, informar al usuario.
- [ ] **Paso 3:** escribir el script, la unidad y la documentación.
- [ ] **Paso 4:** pasan; `python3 -m unittest discover -s lab/banco/tests -t .` sin regresiones.
- [ ] **Paso 5 (PARADA):** el script baja y levanta el banco. Probarlo en vivo **solo** con permiso explícito del usuario; si no, ledger `Ruling:`.
- [ ] **Paso 6: commit** `feat(lab): servicio-mdr.sh y la unidad mdr-laboratorio (arranque desatendido)`.

### Tarea 5: la variante en OpenTofu

**Files:**
- Modify: `infra/aws/variables.tf`, `infra/aws/mdr.tf`, `infra/aws/produccion.tfvars.ejemplo`
- Create: `infra/aws/templates/laboratorio_user_data.sh.tftpl`
- Test: `prototipo/tests/test_infra_aws.py` (clase `TestLaboratorio`)

**Interfaces:**
- Produces: variables `variante` (string, `"mdr"`, `validation` en `["mdr","laboratorio"]`), `laboratorio_tipo` (`"t3.xlarge"`), `laboratorio_disco_gb` (number, 40), `laboratorio_commit` (string, `""`).
- Produces: en `aws_instance.mdr`, según `local.laboratorio = var.variante == "laboratorio"`: `instance_type`, `root_block_device.volume_size`, la plantilla y `tags.Name` (`"${var.proyecto}-laboratorio"`). Con `"mdr"`, los mismos valores de hoy. Nuevas `precondition`, con estos `error_message` exactos (las usa la tarea 6):
  - `La variante laboratorio necesita egreso_bootstrap = true (descarga Docker, Containerlab y la imagen de Wazuh).`
  - `La variante laboratorio necesita un MDR >= 1.9.2: la 1.9.1 no trae los arreglos del laboratorio.`
  - `La variante laboratorio no lleva GPU (llm_habilitado = false).`
  - `laboratorio_commit: los 40 caracteres hexadecimales del commit de la etiqueta v<mdr_version>.`
- Produces: la plantilla recibe `region`, `mdr_version`, `laboratorio_commit`, `paquete_url`, `paquete_sha256`, `secreto_traza_arn`, `secreto_operadores_arn` y `volumen`. Pasos del diseño (§ «Arranque de la máquina»): disco (el mismo bloque que la plantilla del MDR); `dnf install -y docker git python3 python3-pyyaml` y Docker activo; Containerlab `0.79.0`; `git clone --depth 1 --branch v${mdr_version}` y `git rev-parse HEAD` igual a `laboratorio_commit` (si no, para); paquete con `sha256sum -c` y su `visor/dist` copiado al clon; `construir-imagen.sh`; clave y operadores en `/etc/mdr/triaje.env` como la plantilla del MDR, token con `MDR_ENV=/etc/mdr/triaje.env /opt/mdr-laboratorio/bin/mdr analista alta admin > /root/mdr-token-admin`; copiar la unidad de la tarea 4 y `systemctl enable --now mdr-laboratorio`.

- [ ] **Paso 1: pruebas que fallan** — `TestLaboratorio`: `test_variables_y_valores_por_defecto`; `test_precondiciones` (los cuatro mensajes en `mdr.tf`); `test_arranque_del_laboratorio` (en la plantilla: `set -euo pipefail`, sin `|| true`, `--branch v${mdr_version}`, `rev-parse HEAD` comparado con `laboratorio_commit` antes de `construir-imagen.sh`, `sha256sum -c`, `visor/dist`, `0.79.0`, `systemctl enable --now mdr-laboratorio`, `/root/mdr-token-admin`); `test_mismo_disco_que_el_mdr` (el bloque del EBS por id y `nofail` es igual en las dos plantillas); `test_commit_distinto_para` (Review Focus 4: la comparación termina en `exit 1`, antes de cualquier `docker`).
- [ ] **Paso 2:** `python3 -m unittest prototipo.tests.test_infra_aws` → FALLAN las nuevas; las de antes pasan.
- [ ] **Paso 3:** implementar. Las cuatro variables nuevas también van en `produccion.tfvars.ejemplo` (`test_tfvars_cubre_las_variables`).
- [ ] **Paso 4:** pasan todas; `cd infra/aws && tofu fmt -check -recursive && tofu validate` → `Success!`.
- [ ] **Paso 5: commit** `feat(aws): variante laboratorio (banco, Wazuh y MDR en una máquina)`.

### Tarea 6: escenarios E, F y G en el emulador e inventario

**Files:**
- Modify: `infra/aws/emulador/probar.sh`, `infra/aws/emulador/comprobar.py`, `infra/aws/emulador/inventario.py`
- Regenerate: `infra/aws/inventario/` (añade `escenario-e.json`)

**Interfaces:**
- Consumes: variables y mensajes de la tarea 5.
- Produces: escenarios por defecto `A B C D E F G`. E: `$COMUNES -var egreso_bootstrap=true -var variante=laboratorio -var mdr_version=1.9.2 -var mdr_paquete_sha256=$ZEROS -var laboratorio_commit=<40 ceros>`. F: los de E con `egreso_bootstrap=false` y `mdr_paquete_url=s3://mdr-prueba/mdr-1.9.2.tar.gz` → rechazado con el mensaje del egreso. G: los de E con `mdr_version=1.9.1` → rechazado con el mensaje de la 1.9.2. C, F y G pasan por una sola función `rechazado ESCENARIO "mensaje"` (el bloque de C se reescribe con ella).
- Produces: `comprobar.py` E: `t3.xlarge`; raíz 40 GB `gp3` cifrada; sin `aws_instance.llm[0]`; NAT presente; `tags.Name` termina en `-laboratorio`; script de la API con `bash -n` limpio, `--branch v1.9.2`, el commit, `mdr-laboratorio` y el EBS por id; y (Review Focus 3) el script de arranque ocupa menos de 16384 bytes. `inventario.py`: E en `ESCENARIOS`.

- [ ] **Paso 1:** `sh infra/aws/emulador/probar.sh E F G` → falla (escenarios desconocidos).
- [ ] **Paso 2:** implementar.
- [ ] **Paso 3:** `MDR_INVENTARIO=<dir del scratchpad> sh infra/aws/emulador/probar.sh` → `EMULADOR: todo como se esperaba`, con E `N/N`, F y G rechazados por su mensaje.
- [ ] **Paso 4:** `python3 infra/aws/emulador/inventario.py <dir> infra/aws/inventario`; después `git diff --exit-code infra/aws/inventario/escenario-a.json infra/aws/inventario/escenario-b.json infra/aws/inventario/escenario-d.json` → sin cambios (con `"mdr"` todo es igual que hoy); `python3 -m unittest prototipo.tests.test_infra_aws` → OK.
- [ ] **Paso 5: commit** `test(aws): escenarios E, F y G (laboratorio) contra AWS Emulator`.

### Tarea 7: costes, guía y documentación

**Files:**
- Modify: `infra/aws/COSTES.md`, `infra/aws/DESPLIEGUE.md`, `infra/aws/README.md`, `CHANGELOG.md`
- Test: `prototipo/tests/test_infra_aws.py` (`TestLaboratorio`)

- [ ] **Paso 1: pruebas que fallan** — `test_costes_del_laboratorio` (`COSTES.md` tiene la fila de E con `t3.xlarge` y las tres formas de uso); `test_guia_del_laboratorio` (`DESPLIEGUE.md` tiene la sección `Variante laboratorio`, con `no se conecta a ningún cliente`, `stop-instances` y `banco.sh atacar`).
- [ ] **Paso 2:** ejecutarlas → FALLAN.
- [ ] **Paso 3:** escribir.
  - COSTES: `t3.xlarge` a 0,1824 $/h (`eu-west-1`) y 0,1664 $/h (`us-east-1`), oferta del 14/11/2026 consultada el 17/11. Raíz de 40 GB y traza de 20 GB, NAT, IP y 3 endpoints. Por hora, prueba de 8 h y de 24 h, mes 24/7, parar y encender (8 h × 22) y parada.
  - DESPLIEGUE: entrar (túnel y token), atacar, restaurar, vigilar, `comprobar-alertas`, parar y encender (unos minutos hasta que el laboratorio está listo; `journalctl -u mdr-laboratorio`), apagar. Aviso: no se conecta a ningún cliente.
  - README: `variante`, tabla de escenarios con E, F y G.
  - CHANGELOG: arreglos del laboratorio y la variante.
- [ ] **Paso 4:** `python3 -m unittest prototipo.tests.test_infra_aws` y `python3 -m unittest discover -s lab/banco/tests -t .` → OK.
- [ ] **Paso 5: commit** `docs(aws): variante laboratorio en costes, guía y README`.
