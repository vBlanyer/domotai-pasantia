#!/bin/sh
# Wrapper de arranque del daemon MDR para systemd (#5 de la hoja de ruta a producción).
# systemd no hace pipes en ExecStart, así que el pipe SIEM -> stream vive aquí. Las variables
# salen del EnvironmentFile de la unidad (deploy/triaje.env.ejemplo).
#
# Si la fuente (tail) o el daemon mueren, el pipeline termina (con error si cayó python3, o
# limpiamente si cayó tail y python3 vio EOF). La unidad usa Restart=always, así que systemd lo
# reinicia en ambos casos; al reiniciar el daemon retoma su estado de la traza (#4), por eso
# TRIAJE_SALIDA debe ser una ruta FIJA.
set -eu

RAIZ="${TRIAJE_RAIZ:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
cd "$RAIZ"

: "${TRIAJE_ALERTS:?define TRIAJE_ALERTS: ruta del alerts.json del SIEM (se sigue con tail -F)}"
: "${TRIAJE_PERFIL:?define TRIAJE_PERFIL: perfil del cliente (prototipo/perfiles/<cliente>.yml)}"
: "${TRIAJE_HALLAZGOS:?define TRIAJE_HALLAZGOS: hallazgos de postura del auditor (JSON)}"
: "${TRIAJE_SALIDA:?define TRIAJE_SALIDA: ruta FIJA de la traza (retomar estado al reiniciar, #4)}"
PUERTO="${TRIAJE_WEB_PUERTO:-8787}"

tail -n0 -F "$TRIAJE_ALERTS" \
  | python3 -m prototipo.stream - "$TRIAJE_PERFIL" "$TRIAJE_HALLAZGOS" --web "$PUERTO" --salida "$TRIAJE_SALIDA"
