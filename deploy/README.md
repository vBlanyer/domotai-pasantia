# Despliegue del daemon MDR (systemd + healthcheck)

Artefactos para correr el daemon como servicio supervisado en el nodo de gestión del cliente
(#5 de la [hoja de ruta a producción](../documentacion/04-fase4-diseno-de-arquitectura/hoja-de-ruta-a-produccion.md)).
Son plantillas: ajústalas a las rutas y al usuario del cliente.

| Fichero | Qué es |
|---|---|
| `arrancar-mdr.sh` | Wrapper del *pipe* `tail -F alerts.json \| python3 -m prototipo.stream … --web --salida <fijo>` (systemd no hace *pipes*). Lee las variables del `EnvironmentFile`. |
| `mdr-triaje.service` | Unidad systemd: `Restart=always` (resiliencia: reinicia aunque el daemon salga 0 tras un EOF de la fuente) + endurecimiento básico. |
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

## Recibir del SIEM por red (alternativa a `tail`)

Si el SIEM está en otra máquina y reenvía las alertas por TCP (en vez de compartir el `alerts.json`), el
daemon puede escuchar directamente, sin el *pipe* del wrapper:

```sh
python3 -m prototipo.stream - "$TRIAJE_PERFIL" "$TRIAJE_HALLAZGOS" --web --salida "$TRIAJE_SALIDA" \
  --escuchar 0.0.0.0:6514 --permitir 10.0.0.5,10.0.0.6 \
  [--tls-cert cert.pem --tls-clave clave.pem [--tls-ca ca.pem]]
```

`--permitir` es la **lista blanca** de IPs del SIEM (solo esas conexiones se aceptan; un `--permitir` vacío
aborta el arranque en vez de abrir) y es **obligatoria al escuchar fuera de loopback**: sin ella el arranque
aborta (solo `127.0.0.1` puede escuchar abierto). Con `--tls-ca` el receptor exige **certificado de cliente**
firmado por esa CA (mTLS): autentica al emisor, no solo cifra — la lista blanca deja de ser la única barrera.
El emisor envía un JSON de alerta por línea (el formato de `alerts.json`). El enmarcado syslog / formato CEF
es trabajo futuro. El receptor además acota las conexiones (64 en total, 8 por IP) y **cierra la conexión
ociosa** (15 min sin datos): el reenviador simplemente reconecta (su unidad lo hace sola); los rechazos y
cierres se avisan por stderr con freno (uno por minuto y motivo). **Ojo:** si pones un proxy TLS delante, el
receptor ve la IP del proxy, no la del SIEM, así que la lista blanca deja de distinguir al SIEM — en ese caso
restringe en el proxy (o usa `--tls-cert/--tls-clave` para TLS directo y que la IP de origen sea la real).

## Healthcheck

El daemon expone la salud del **propio MDR** en `GET /healthz` (distinto de `/api/salud`, que es la
salud de los servicios del cliente). Como liga solo a `127.0.0.1`, lo sondea un monitor **local**:

```sh
curl -fsS http://127.0.0.1:8787/healthz
# {"ok": true, "desde": "2026-10-07T10:00:00Z", "lazo_quietud_s": 0.3,
#  "ingesta_silencio_s": 12.0, "alertas": 142}
```

- `ok=false` cuando el **lazo principal** lleva demasiado tiempo sin iterar (colgado): un fallo que
  «el proceso existe» no detecta. `Restart=always` cubre la caída/salida; `/healthz` cubre el cuelgue.
- `ingesta_silencio_s` alto con la red activa sugiere que la **fuente** (SIEM) dejó de enviar. **Ojo:**
  `ok` mide solo la vitalidad del lazo, **no** el silencio de ingesta (un SIEM callado no es un MDR
  enfermo), así que una fuente muerta se vigila aparte, con un umbral sobre `ingesta_silencio_s`.

Ejemplo de sonda local cada minuto (systemd timer o cron) que alerta si el lazo no está sano o si la
ingesta lleva demasiado tiempo en silencio (ajusta el umbral a tu tráfico):

```sh
* * * * * curl -fsS http://127.0.0.1:8787/healthz | python3 -c 'import sys,json; d=json.load(sys.stdin); sys.exit(0 if d["ok"] and (d["ingesta_silencio_s"] or 0) < 900 else 1)' \
  || logger -p daemon.err "MDR /healthz: lazo no saludable o ingesta en silencio"
```

La autenticación/TLS del visor las pone la empresa delante (no hay login; ver la guía de integración).

## Retención de la traza

Para que `run/` no crezca sin límite, una tarea de mantenimiento **offline** poda los ficheros de traza
antiguos (nunca el que el daemon escribe, nunca uno con la cadena de hashes rota):

```sh
# simulación (no borra):
python3 -m prototipo.retener_trazas run --max 30
# aplicar (p. ej. cron semanal): conserva los 30 más recientes y nunca el fichero vivo
0 4 * * 0  cd /opt/mdr && . /etc/mdr/triaje.env && \
  python3 -m prototipo.retener_trazas run --max 30 --excepto "$TRIAJE_SALIDA" --aplicar
```

- También admite `--max-dias D` (poda lo más viejo que D días).
- **`--excepto <ruta>`** protege por nombre el fichero que el daemon está escribiendo (`$TRIAJE_SALIDA`);
  más fiable que inferir el activo por fecha.
- Verifica la cadena de cada fichero antes de borrarlo; si **no verifica**, lo conserva y avisa. Si la traza
  va firmada con HMAC, **el cron debe correr con el mismo `TRIAJE_TRAZA_CLAVE`** que el daemon (por eso el
  ejemplo hace `. /etc/mdr/triaje.env`); sin la clave, ningún fichero verifica y no se poda nada (sale un
  aviso, no borra por las dudas).

