"""Fuente única del laboratorio «oficina»: la red que el asistente de red debe descubrir.

Una oficina pequeña: fw-borde hacia internet, una DMZ (web y correo), fw-interno delante de la red
interna (aplicación, base de datos, NAS, impresora y un puesto) y el equipo del MDR en su propia red de
gestión. La topología (lab/topologias/oficina.clab.yml) y el arranque (oficina.sh) salen de aquí, y
lab/oficina/tests comprueba que coinciden. Plan: documentacion/05-fase5-implementacion-del-prototipo/
plan-asistente-de-red.md (tarea 1).

A propósito, NINGÚN equipo trae el usuario ni el sudoers del conector: el acceso se da con el paquete de
alta de la vista Conectividad, como en un cliente.
"""
import sys

GESTION = "10.99.0.10"
EXTERNO = "198.51.100.10"
RANGOS = ["172.16.10.0/24", "10.20.0.0/24", "10.0.0.0/24", "10.99.0.0/24"]

# Equipos con una sola interfaz de datos (eth1): IP, puerta y segmento.
NODOS = {
    "internet":     {"ip": "198.51.100.10", "gw": "198.51.100.1", "segmento": "198.51.100.0/24"},
    "mdr":          {"ip": "10.99.0.10",    "gw": "10.99.0.1",    "segmento": "10.99.0.0/24"},
    "srv-web01":    {"ip": "172.16.10.10",  "gw": "172.16.10.1",  "segmento": "172.16.10.0/24"},
    "srv-correo01": {"ip": "172.16.10.20",  "gw": "172.16.10.1",  "segmento": "172.16.10.0/24"},
    "srv-app01":    {"ip": "10.20.0.10",    "gw": "10.20.0.1",    "segmento": "10.20.0.0/24"},
    "srv-db01":     {"ip": "10.20.0.20",    "gw": "10.20.0.1",    "segmento": "10.20.0.0/24"},
    "nas01":        {"ip": "10.20.0.30",    "gw": "10.20.0.1",    "segmento": "10.20.0.0/24"},
    "impresora":    {"ip": "10.20.0.50",    "gw": "10.20.0.1",    "segmento": "10.20.0.0/24"},
    "puesto":       {"ip": "10.20.0.77",    "gw": "10.20.0.1",    "segmento": "10.20.0.0/24"},
}

# Cortafuegos: una IP por interfaz, y hacia dónde mandan lo que no es suyo.
CORTAFUEGOS = {
    "fw-borde":   {"interfaces": {"eth1": "198.51.100.1", "eth2": "10.99.0.1", "eth3": "172.16.10.1", "eth4": "10.0.0.1"},
                   "rutas": ["10.20.0.0/24 via 10.0.0.2"]},
    "fw-interno": {"interfaces": {"eth1": "10.0.0.2", "eth2": "10.20.0.1"},
                   "rutas": ["10.99.0.0/24 via 10.0.0.1", "172.16.10.0/24 via 10.0.0.1", "198.51.100.0/24 via 10.0.0.1"]},
}

# Servicios simulados (HTTP mínimo de lab/banco/servicio.py en cada puerto) y si el equipo tiene sshd.
SERVICIOS = {
    "srv-web01":    {"puertos": [80, 443],       "ssh": True},
    "srv-correo01": {"puertos": [25, 587, 993],  "ssh": True},
    "srv-app01":    {"puertos": [8443],          "ssh": True},
    "srv-db01":     {"puertos": [5432],          "ssh": True},
    "nas01":        {"puertos": [445],           "ssh": True},
    "impresora":    {"puertos": [80, 9100],      "ssh": False},
    "puesto":       {"puertos": [],              "ssh": False},
    "fw-borde":     {"puertos": [],              "ssh": True},
    "fw-interno":   {"puertos": [],              "ssh": True},
}


def orden_servicio(nodo):
    """Línea que arranca los servicios simulados del nodo, o "" si no presta ninguno."""
    s = SERVICIOS.get(nodo) or {}
    if not s.get("puertos"):
        return ""
    partes = ["python3 /opt/banco/servicio.py", f"--nombre {nodo}"]
    partes += [f"--puerto {p}" for p in s["puertos"]]
    partes.append("--registro /var/log/banco/access.log")
    return " ".join(partes)


def con_ssh():
    return [n for n, s in SERVICIOS.items() if s["ssh"]]


def main(argv):
    orden = argv[0] if argv else ""
    if orden == "servicio" and len(argv) == 2:
        print(orden_servicio(argv[1]))
    elif orden == "ssh":
        print(" ".join(con_ssh()))
    elif orden == "nodos":
        print(" ".join(sorted(set(NODOS) | set(CORTAFUEGOS))))
    elif orden == "ips":
        print(" ".join(f"{n}:{v['ip']}" for n, v in NODOS.items() if n not in ("internet", "mdr")))
    else:
        print("uso: python3 -m lab.oficina.red servicio <nodo> | ssh | nodos | ips", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
