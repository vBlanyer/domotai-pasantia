# Despliegue del daemon MDR (systemd + healthcheck)

Artefactos para correr el daemon como servicio supervisado en el nodo de gestión del cliente
(#5 de la [hoja de ruta a producción](../documentacion/04-fase4-diseno-de-arquitectura/hoja-de-ruta-a-produccion.md)).
Son plantillas: ajústalas a las rutas y al usuario del cliente.

| Fichero | Qué es |
|---|---|
| `arrancar-mdr.sh` | Wrapper del *pipe* `tail -F alerts.json \| python3 -m prototipo.stream … --web --salida <fijo>` (systemd no hace *pipes*). Lee las variables del `EnvironmentFile`. |
| `mdr-triaje.service` | Unidad systemd: `Restart=on-failure` (resiliencia) + endurecimiento básico. |
| `triaje.env.ejemplo` | Ejemplo de `EnvironmentFile` (fuente, perfil, `--salida` fijo, conector SSH, HMAC). |

## Instalar

```sh
sudo useradd --system --home /opt/mdr triaje
sudo cp -r <repo> /opt/mdr && sudo chown -R triaje:triaje /opt/mdr
sudo install -D -m 0600 deploy/triaje.env.ejemplo /etc/mdr/triaje.env   # y editarlo
sudo cp deploy/mdr-triaje.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now mdr-triaje
journalctl -u mdr-triaje -f          # ver el arranque y el feed
```

`--salida` debe ser una **ruta fija** (p. ej. `run/trazas-<cliente>.jsonl`): al reiniciar, el daemon
retoma de ahí su estado (supresión + contenciones activas, #4).

## Healthcheck

El daemon expone la salud del **propio MDR** en `GET /healthz` (distinto de `/api/salud`, que es la
salud de los servicios del cliente). Como liga solo a `127.0.0.1`, lo sondea un monitor **local**:

```sh
curl -fsS http://127.0.0.1:8787/healthz
# {"ok": true, "desde": "2026-10-07T10:00:00Z", "lazo_quietud_s": 0.3,
#  "ingesta_silencio_s": 12.0, "alertas": 142}
```

- `ok=false` cuando el **lazo principal** lleva demasiado tiempo sin iterar (colgado): un fallo que
  «el proceso existe» no detecta. `Restart=on-failure` cubre la caída dura; `/healthz` cubre el cuelgue.
- `ingesta_silencio_s` alto con la red activa sugiere que la **fuente** (SIEM) dejó de enviar.

Ejemplo de sonda local cada minuto (systemd timer o cron) que alerta si `ok` es falso:

```sh
* * * * * curl -fsS http://127.0.0.1:8787/healthz | grep -q '"ok": true' \
  || logger -p daemon.err "MDR /healthz: lazo no saludable"
```

La autenticación/TLS del visor las pone la empresa delante (no hay login; ver la guía de integración).
