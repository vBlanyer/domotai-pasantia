#!/bin/sh
# Escanea los nodos del plano de datos con Nmap y emite hallazgos.json normalizado.
#
#   sh lab/scripts/auditar.sh <salida.json>
#
# Registra la versión de Nmap: si el escáner cambia entre campañas, los
# resultados dejan de ser comparables (RF-09).
set -e
SALIDA="${1:?uso: sh lab/scripts/auditar.sh <salida.json>}"
AUDITOR=clab-red-cliente-auditor
VER=$(docker exec $AUDITOR nmap --version 2>/dev/null | head -1 | sed 's/ (.*//')
TS=$(date -u +%Y-%m-%dT%H:%M:%S+0000)

# Nodos del plano de datos y su IP
NODOS="objetivo-vuln:192.168.1.30 puesto:192.168.1.10 iot:192.168.1.20 borde:192.168.1.1"

python3 - "$SALIDA" "$VER" "$TS" $NODOS <<'PY'
import subprocess, sys, json, re
salida, ver, ts = sys.argv[1], sys.argv[2], sys.argv[3]
nodos = {}
for par in sys.argv[4:]:
    nombre, ip = par.split(":")
    out = subprocess.run(
        ["docker","exec","clab-red-cliente-auditor","nmap","-Pn","--top-ports","100",ip],
        capture_output=True, text=True).stdout
    puertos = []
    for m in re.finditer(r"^(\d+)/tcp\s+(\S+)\s+(\S+)", out, re.M):
        puertos.append({"puerto": int(m.group(1)), "servicio": m.group(3), "estado": m.group(2)})
    nodos[nombre] = puertos
json.dump({"version_herramienta": ver, "timestamp": ts, "nodos": nodos},
          open(salida,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"hallazgos -> {salida} ({sum(len(v) for v in nodos.values())} servicios)")
PY
