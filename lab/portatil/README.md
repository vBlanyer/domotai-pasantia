# `lab/portatil/` — la demo en Docker plano (sin Containerlab)

Empaqueta la validación de portabilidad del 21/10: **el ciclo completo del MDR corre en cualquier
máquina con Docker**, sin instalar Containerlab. Dos contenedores (nodo de gestión + host
monitorizado), el aprovisionamiento de mínimo privilegio **oficial** (usuario `triaje` + sudoers
generado del catálogo cerrado), una alerta real grabada, y el lazo con el conector SSH de verdad:

```sh
sh lab/portatil/demo.sh          # ciclo completo; cuando pregunte, responde 1 (aprobar)
sh lab/portatil/demo.sh down     # apagar y limpiar
```

Qué hace, paso a paso: levanta los nodos (`docker compose`, construyendo `banco-nodo:1` de
[`lab/banco/Dockerfile`](../banco/Dockerfile) si no existe) → aprovisiona el conector con
[`aprovisionar-minimo-privilegio.sh`](../scripts/aprovisionar-minimo-privilegio.sh) (sus tres
comprobaciones incluidas) → genera el perfil (el empresarial con el activo apuntando al contenedor,
en `run/portatil/`) → normaliza la [alerta de muestra](alerta-muestra.jsonl) (fuerza bruta SSH 5760
grabada de la campaña real) → `prototipo.servicio.lazo` decide `vp_intento_acceso`, el origen interno exige
**tu aprobación**, y al aprobar aplica `BLOQUEAR_IP` por SSH, **verifica** la regla en el objetivo y
la deja trazada → la demo enseña la regla `iptables` desde dentro del contenedor y **revierte** con
`prototipo.accion.revertir`, dejando el objetivo limpio y el ciclo entero en `run/portatil/traza.jsonl`.

## Requisitos y lecciones de plataforma

- Docker con el plugin compose; Python 3 + PyYAML (lo mismo que el repo).
- El objetivo necesita `CAP_NET_ADMIN` (el compose ya lo declara): sin ella, `iptables` falla con
  «you must be root» aunque el sudo funcione. Containerlab se la da a sus nodos sin pedirla.
- La dependencia real del conector es **Docker, no Containerlab**: el SSH sale del nodo de gestión
  vía `docker exec` (`TRIAJE_NODO_GESTION`). Para un host sin Docker haría falta un ejecutor SSH
  directo (seam pequeño, aislado en `prototipo/accion/conector.py`).
- `prototipo.servicio.lazo`/`triaje` por lotes consumen alertas **normalizadas** (`prototipo.entrada.ingesta`);
  el daemon en vivo (`prototipo.servicio.stream`) normaliza solo.

## Variante viva (detección real, opcional)

El manager de Wazuh ya corre en Docker plano (nunca fue un nodo de Containerlab): el mismo
[`wazuh-run.sh`](../scripts/wazuh-run.sh) acepta la red y el nombre por variables, conservando los
defaults del laboratorio:

```sh
# La subred de compose la asigna Docker (no se asume): se deriva para la lista blanca del syslog.
SUBRED=$(docker network inspect portatil_default -f '{{(index .IPAM.Config 0).Subnet}}')
# WAZUH_PUERTOS="": sin puertos publicados en el host (el syslog viaja por la red de compose),
# así este manager convive con el del laboratorio si estuviera levantado.
WAZUH_NOMBRE=portatil-wazuh WAZUH_RED=portatil_default WAZUH_PERMITIR="$SUBRED" WAZUH_PUERTOS="" \
  sh lab/scripts/wazuh-run.sh up
```

`demo.sh down` también retira `portatil-wazuh` si quedó levantado.

Con el manager arriba: arranca el reenviador del objetivo (`/opt/banco/reenviador.py`, ya está en
la imagen) apuntando a la IP del manager, genera unos intentos de login fallidos de prueba contra
el objetivo, y alimenta el daemon con `wazuh-run.sh alerts` o con `--escuchar` (ver
[deploy/README.md](../../deploy/README.md)). Es el mismo camino del banco, en la red de compose.

## Qué NO cubre

La topología **enrutada** del banco: fw-core como punto de contención del borde, cascadas de
dependencias, bloqueo de egreso (exfiltración) y aislamiento en el FORWARD. Para eso está el
laboratorio Containerlab ([`lab/topologias/banco.clab.yml`](../topologias/banco.clab.yml) +
[RUNBOOK](../../RUNBOOK.md)). Esta demo prueba la **portabilidad del sistema**, no sustituye al banco.
