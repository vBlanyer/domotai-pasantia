"""Campaña de la evaluación aparte en el banco, con la verdad declarada por el experimento.

    python3 -m lab.banco.campana_evaluacion <id-campaña>

Diseño fijado antes de medir: documentacion/06-fase6-evaluacion-del-prototipo/evaluacion-banco-2026-11.md.
Requiere el banco levantado (sh lab/banco/banco.sh up) y SIN el daemon del MDR en marcha: la campaña mide
lo que el motor decide sobre las alertas, no lo que contiene en vivo. Deja la campaña en
lab/campañas-banco/<id>/ (fuera de lab/campañas: no se mezcla con el conjunto canónico).
"""
import json, os, subprocess, sys, time
from datetime import datetime, timezone

from lab.banco import casos, demo

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WZ = "clab-red-cliente-wazuh"
P = "clab-banco"
SSH = ("-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 "
       "-o PubkeyAuthentication=no -o PreferredAuthentications=password")
CASO = {c["id"]: c for c in casos.CASOS}

# (id, caso del banco o None, IP de origen rotada o None, verdad, motivo)
ATAQUES = [
    ("BD1", "D1", "198.51.100.60", "VP", "fuerza bruta externa contra web-banking"),
    ("BRC", "RECON", "198.51.100.61", "VP", "reconocimiento externo de web-banking"),
    ("BTN", "TELNET", "198.51.100.62", "VP", "conexiones al telnet expuesto de atm"),
    ("BEX", "EXPLOIT", "198.51.100.63", "VP", "inyección SQL contra web-banking"),
    ("BA1", "A1", None, "VP", "fuerza bruta desde la taquilla (10.200.0.10)"),
    ("BK1", "K1", None, "VP", "fuerza bruta desde el middleware comprometido (10.40.0.10)"),
]
# Legítimos: un error de contraseña y un acceso correcto con la cuenta real de la imagen (cliente).
LEGITIMOS = [
    ("BL1", "internet", "198.51.100.70", "10.20.0.10", "FP", "técnico externo legítimo contra api-movil"),
    ("BL2", "taquilla", "10.200.0.11", "10.10.0.10", "FP", "empleado de taquilla legítimo contra web-banking"),
]


def ahora():
    return subprocess.run(["docker", "exec", WZ, "date", "-u", "+%Y-%m-%dT%H:%M:%S"],
                          capture_output=True, text=True, check=True).stdout.strip()


def dexec(nodo, cmd):
    return subprocess.run(["docker", "exec", f"{P}-{nodo}", "sh", "-c", cmd], capture_output=True, text=True)


def acceso_legitimo(nodo, ip, destino):
    dexec(nodo, f"ip addr add {ip}/24 dev {demo.IFACE_DATOS} 2>/dev/null; true")
    for clave in ("Cliente2026x", "Cliente2026"):          # el error de tecleo y el acceso correcto
        dexec(nodo, f"sshpass -p '{clave}' ssh -b {ip} {SSH} cliente@{destino} true >/dev/null 2>&1; true")
        time.sleep(2)


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    cid = argv[1]
    dest = os.path.join(RAIZ, "lab", "campañas-banco", cid)
    os.makedirs(dest, exist_ok=True)
    inicio = ahora()
    for eid, caso, ip, _, motivo in ATAQUES:
        print(f"== {eid}: {motivo}", flush=True)
        demo.lanzar(CASO[caso], src_ip=ip)
        time.sleep(3)
    for eid, nodo, ip, destino, _, motivo in LEGITIMOS:
        print(f"== {eid}: {motivo}", flush=True)
        acceso_legitimo(nodo, ip, destino)
    print("   esperando al reenvío…", flush=True)
    time.sleep(60)
    cierre = ahora()

    alertas = subprocess.run(["docker", "exec", WZ, "cat", "/var/ossec/logs/alerts/alerts.json"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    n = 0
    with open(os.path.join(dest, "alerts.json"), "w", encoding="utf-8") as f:
        for linea in alertas:
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if d.get("timestamp", "") >= inicio:
                f.write(linea.strip() + "\n"); n += 1
    print(f"{n} alertas en la ventana", flush=True)

    verdad = [{"origen": ip or CASO[caso]["origen"], "desde": inicio, "hasta": cierre, "etiqueta": et,
               "motivo": f"{eid}: {m}"} for eid, caso, ip, et, m in ATAQUES]
    verdad += [{"origen": ip, "desde": inicio, "hasta": cierre, "etiqueta": et, "motivo": f"{eid}: {m}"}
               for eid, _, ip, _, et, m in LEGITIMOS]
    ficha = {"id": cid, "fecha": datetime.now(timezone.utc).date().isoformat(), "familia": "varias",
             "proposito": "evaluación aparte en el banco (perfil bancario); verdad declarada por el experimento",
             "diseno": "documentacion/06-fase6-evaluacion-del-prototipo/evaluacion-banco-2026-11.md",
             "auditor": {"ips": ["10.100.0.20"], "cuando": cierre + "+0000"},
             "legitimos": {"ips": ["10.100.0.10", "10.100.0.20"]},
             "verdad": verdad}
    import yaml
    with open(os.path.join(dest, "campaña.yml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(ficha, f, allow_unicode=True, sort_keys=False)

    print("== Auditando la postura (hallazgos.json)", flush=True)
    nodos = subprocess.run(["python3", "-m", "lab.banco.red", "nodos"], capture_output=True, text=True,
                           cwd=RAIZ, check=True).stdout.split()
    env = dict(os.environ, TRIAJE_AUDITOR=f"{P}-auditor", AUDITOR_NODOS=" ".join(nodos))
    subprocess.run(["sh", os.path.join(RAIZ, "lab", "scripts", "auditar.sh"), os.path.join(dest, "hallazgos.json")],
                   env=env, cwd=RAIZ, check=True)
    print(f"== Campaña {cid} lista en {dest}", flush=True)


if __name__ == "__main__":
    main(sys.argv)
