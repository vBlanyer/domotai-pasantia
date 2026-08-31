#!/bin/sh
# Visor de alertas de Wazuh EN TIEMPO REAL, formateado y con color.
# Pensado para dejarlo en una terminal mientras atacas desde otra.
#
# Uso:  sh lab/scripts/ver-alertas.sh          (todas las alertas nuevas)
#       sh lab/scripts/ver-alertas.sh 5        (solo nivel >= 5, ignora el ruido)

MIN="${1:-1}"
echo "Vigilando alertas de Wazuh (nivel >= $MIN). Ctrl+C para salir."
echo "Ataca desde otra terminal y velas aparecer aqui."
echo "--------------------------------------------------------------"

docker exec clab-red-cliente-wazuh sh -c 'tail -n0 -f /var/ossec/logs/alerts/alerts.json' 2>/dev/null | \
python3 -u -c "
import sys, json
MIN=$MIN
C={'r':'\033[31m','y':'\033[33m','g':'\033[32m','b':'\033[1m','x':'\033[0m'}
for line in sys.stdin:
    try: a=json.loads(line)
    except: continue
    r=a.get('rule',{}); d=a.get('data',{})
    lv=r.get('level',0)
    if lv < MIN: continue
    col = C['r'] if lv>=10 else C['y'] if lv>=5 else C['g']
    ts=a.get('timestamp','')[11:19]
    print(f\"{col}{C['b']}[{ts}] NIVEL {lv:>2}{C['x']}{col}  regla {r.get('id')}  {r.get('description','')}{C['x']}\")
    det=[]
    if d.get('srcip'):   det.append(f\"origen={d['srcip']}\")
    if d.get('dstuser'): det.append(f\"usuario={d['dstuser']}\")
    fl=a.get('full_log','')
    import re
    m=re.search(r' (\\S+) sshd', fl)
    if m: det.append(f\"nodo={m.group(1)}\")
    if det: print('           '+'  '.join(det))
"
