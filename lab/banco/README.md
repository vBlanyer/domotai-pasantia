# Laboratorio del banco

La red de `prototipo/perfiles/bancario.yml`, montada de verdad en Containerlab: servicios con
dependencias reales, un monitor de salud que ve las cascadas y cortafuegos sobre los que el conector
actúa. Diseño: `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md`.

## Levantar

    sh lab/banco/construir-imagen.sh      # una vez
    sh lab/lab.sh up banco                # no convive con la red pequeña
    sh lab/banco/banco.sh test            # conectividad y salud
    sh lab/banco/banco.sh cascada core-db # ver una cascada real y su recuperación
    sh lab/lab.sh down banco

El conector ejecuta desde `mdr-siem` (la IP de gestión del perfil):

    export TRIAJE_NODO_GESTION=clab-banco-mdr-siem

## Qué hay

| Pieza | Dónde |
|---|---|
| Nodos, IPs, servicios y dependencias (fuente única) | `lab/banco/red.py` |
| Servicio con salud transitiva | `lab/banco/servicio.py` |
| Monitor (línea de tiempo en `mdr-siem:/var/log/banco/salud.jsonl`) | `lab/banco/monitor.py` |
| Logs a Wazuh | `lab/banco/reenviador.py` |
| Resultados de la fase 0 | `lab/banco/verificaciones.md` |

La dependencia `atm → middleware` existe aquí y **no** en el perfil, a propósito (caso K3).
Los puertos de los servicios son nominales: servicios HTTP que imitan el puerto del servicio real.
