#!/bin/sh
# Escanea los nodos del plano de datos con Nmap y emite hallazgos.json normalizado.
#
#   sh lab/scripts/auditar.sh <salida.json>
#
# Registra la versión de Nmap: si el escáner cambia entre campañas, los
# resultados dejan de ser comparables (RF-09).
#
# El parseo y la decisión de "escaneo fallido" viven en lab/scripts/auditor.py
# (funciones puras, probadas con unittest); este script solo hace la E/S
# contra Docker. Se ejecuta desde la raíz del repo para que el módulo resuelva.
set -e
SALIDA="${1:?uso: sh lab/scripts/auditar.sh <salida.json>}"
AUDITOR=clab-red-cliente-auditor
TS=$(date -u +%Y-%m-%dT%H:%M:%S+0000)

# Nodos del plano de datos y su IP
NODOS="objetivo-vuln:192.168.1.30 puesto:192.168.1.10 iot:192.168.1.20 borde:192.168.1.1"

python3 -m lab.scripts.auditor "$SALIDA" "$AUDITOR" "$TS" $NODOS
