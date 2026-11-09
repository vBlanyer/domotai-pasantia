#!/bin/sh
# Arranque del servicio MDR (lo invoca la unidad mdr-triaje.service). Las variables salen de
# /etc/mdr/triaje.env. Sigue el alerts.json del SIEM o, con TRIAJE_ESCUCHAR, recibe las alertas
# por la red. Si la fuente o el MDR caen, systemd lo reinicia; al reiniciar retoma de la traza las
# contenciones activas, por eso TRIAJE_SALIDA debe ser una ruta FIJA.
set -eu

RAIZ="${TRIAJE_RAIZ:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
cd "$RAIZ"

: "${TRIAJE_PERFIL:?define TRIAJE_PERFIL: perfil del cliente (/etc/mdr/perfil.yml)}"
: "${TRIAJE_HALLAZGOS:?define TRIAJE_HALLAZGOS: hallazgos de postura del auditor (JSON)}"
: "${TRIAJE_SALIDA:?define TRIAJE_SALIDA: ruta FIJA de la traza (retomar el estado al reiniciar)}"
PUERTO="${TRIAJE_WEB_PUERTO:-8787}"

# Recibir del SIEM por red: el receptor TCP/TLS del propio daemon, sin pipe.
if [ -n "${TRIAJE_ESCUCHAR:-}" ]; then
  set -- --escuchar "$TRIAJE_ESCUCHAR"
  [ -n "${TRIAJE_PERMITIR:-}" ] && set -- "$@" --permitir "$TRIAJE_PERMITIR"
  [ -n "${TRIAJE_TLS_CERT:-}" ] && set -- "$@" --tls-cert "$TRIAJE_TLS_CERT" --tls-clave "${TRIAJE_TLS_CLAVE:?TRIAJE_TLS_CERT exige TRIAJE_TLS_CLAVE}"
  [ -n "${TRIAJE_TLS_CA:-}" ] && set -- "$@" --tls-ca "$TRIAJE_TLS_CA"
  exec python3 -m prototipo.servicio.stream - "$TRIAJE_PERFIL" "$TRIAJE_HALLAZGOS" --web "$PUERTO" \
    --salida "$TRIAJE_SALIDA" "$@" </dev/null
fi

: "${TRIAJE_ALERTS:?define TRIAJE_ALERTS (alerts.json del SIEM) o TRIAJE_ESCUCHAR (recibir por red)}"
tail -n0 -F "$TRIAJE_ALERTS" \
  | python3 -m prototipo.servicio.stream - "$TRIAJE_PERFIL" "$TRIAJE_HALLAZGOS" --web "$PUERTO" --salida "$TRIAJE_SALIDA"
