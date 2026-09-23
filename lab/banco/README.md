# Laboratorio del banco

La red de `prototipo/perfiles/bancario.yml`, montada de verdad en Containerlab: servicios con
dependencias reales, un monitor de salud que ve las cascadas y cortafuegos sobre los que el conector
actúa. Diseño: `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md`.

## Levantar

    sh lab/banco/construir-imagen.sh      # una vez
    sh lab/lab.sh up banco                # no convive con la red pequeña
    sh lab/banco/banco.sh aprovisionar    # minimo privilegio del conector (hace falta tras cada up)
    sh lab/banco/banco.sh test            # conectividad y salud
    sh lab/banco/banco.sh cascada core-db # ver una cascada real y su recuperación
    sh lab/banco/banco.sh vigilar         # panel en vivo: servicios en verde/rojo
    sh lab/banco/banco.sh atacar          # lanzador de ataques por número (para demos)
    sh lab/lab.sh down banco

Prueba manual completa (casos, limpieza y reinicio): [`docs/pruebas/08-laboratorio-banco.md`](../../docs/pruebas/08-laboratorio-banco.md).

`aprovisionar` es necesario después de **cada** `up`: containerlab recrea los contenedores desde
cero, así que el usuario `triaje` y su `sudoers` (que deja el aprovisionamiento) no sobreviven de
una sesión a otra. Ejecuta `lab/scripts/aprovisionar-minimo-privilegio.sh` contra los nodos sobre
los que actúa el conector (los ocho con servicio, más `fw-core` y `fw-edge`).

El conector ejecuta desde `mdr-siem` (la IP de gestión del perfil):

    export TRIAJE_NODO_GESTION=clab-banco-mdr-siem

**H3 (límite conocido):** el modo por contraseña del conector (`ejecutor_ssh_lab`) sigue fijo al
usuario `msfadmin` de la red pequeña (Metasploitable). En el banco solo funciona el modo por
clave (`ejecutor_por_defecto`, el que deja `aprovisionar`).

`AUDITOR_PUERTOS` se lee del entorno (la sesión del banco la fija para incluir los puertos
nominales del banco, p. ej. 1521/9000/48002). Recuerda hacer `unset AUDITOR_PUERTOS` después de
una sesión del banco, antes de volver a auditar la red pequeña — si no, el auditor de la red
pequeña escanearía también esos puertos.

## Qué hay

| Pieza | Dónde |
|---|---|
| Nodos, IPs, servicios y dependencias (fuente única) | `lab/banco/red.py` |
| Servicio con salud transitiva | `lab/banco/servicio.py` |
| Monitor (línea de tiempo en `mdr-siem:/var/log/banco/salud.jsonl`) | `lab/banco/monitor.py` |
| Panel de salud en la terminal (lee el monitor) | `lab/banco/panel.py` |
| Logs a Wazuh | `lab/banco/reenviador.py` |
| Resultados de la fase 0 | `lab/banco/verificaciones.md` |

La dependencia `atm → middleware` existe aquí y **no** en el perfil, a propósito (caso K3).
Los puertos de los servicios son nominales: servicios HTTP que imitan el puerto del servicio real.

## Banco de pruebas (plan 2)

    python3 -m lab.banco.pruebas              # catálogo sin laboratorio (decision/inyectada/perfil), segundos
    python3 -m lab.banco.pruebas --con-vivo   # además los casos de extremo a extremo (necesita el banco levantado)
    python3 -m lab.banco.pruebas --caso K1 --con-vivo
    python3 -m lab.banco.pruebas --guias      # genera docs/pruebas/banco/<caso>.md

Cada caso declara su **nivel**: `decision` (clasificación y filtro, llamando al motor sin lab),
`inyectada` (una acción entregada al filtro del perfil, sin lab), `perfil` (solo lógica del perfil) o
`vivo` (extremo a extremo por Wazuh y el conector). Resultados: **OK**, **FALLO**, **BLOQUEADO** (el
laboratorio no estaba limpio) y **OMITIDO** (falta un requisito, p. ej. el modelo). K1 codifica en su
propia expectativa un fallo conocido del prototipo (predice cascada `[]` aunque los servicios caen de
verdad): cuenta OK mientras el fallo persista. Catálogo y diseño: spec §4 y §6.

El catálogo (`lab/banco/casos.py`) y el ejecutor (`lab/banco/pruebas.py`) cubren clasificación, filtro
por perfil, cascada y los cinco casos de extremo a extremo de la guía manual; los casos que exigen el
modelo LLM o carga a escala quedan como OMITIDO. La última corrida completa (21 OK) está en
`lab/campañas/2026-09-22-banco-regresion/`.

## Aislamiento (endurecido en la revisión final)

`internet` pierde su ruta por defecto real y bloquea la salida por `eth0` (la red de gestión de
Docker le da salida real de otro modo; ver la cabecera de `lab/topologias/banco.clab.yml`). Cada
nodo del plano de datos añade además, en cada `up`, `iptables -A INPUT -i eth0 -p tcp -j DROP`:
sshd y los servicios HTTP nominales solo son alcanzables por el plano de datos (10.x, a través de
`fw-edge`/`fw-core`), no directamente por la red de gestión — sin esta regla, cualquier nodo con
acceso a la red de gestión se saltaba los dos cortafuegos. `docker exec` y el syslog UDP hacia
Wazuh no usan esa red y no se ven afectados. Detalle y evidencia en vivo en
`lab/banco/verificaciones.md` (sección final).
