"""Fuente unica de la red del banco: nodos, IPs, servicios y dependencias REALES.

La topologia (lab/topologias/banco.clab.yml), el arranque (banco.sh), el monitor y el auditor salen
de aqui, y los tests comprueban que coincide con prototipo/perfiles/bancario.yml. La dependencia
atm -> middleware existe en el laboratorio y NO en el perfil, a proposito: es el caso K3
(dependencia no declarada) del catalogo.
"""
import sys

# Plano de datos: IP y puerta de enlace (fw-core en cada segmento). Mismas IPs que bancario.yml.
NODOS = {
    "web-banking":    {"ip": "10.10.0.10",  "gw": "10.10.0.1"},
    "api-movil":      {"ip": "10.20.0.10",  "gw": "10.20.0.1"},
    "swift-alliance": {"ip": "10.30.0.10",  "gw": "10.30.0.1"},
    "middleware":     {"ip": "10.40.0.10",  "gw": "10.40.0.1"},
    "core-db":        {"ip": "10.50.0.10",  "gw": "10.50.0.1"},
    "hsm":            {"ip": "10.60.0.10",  "gw": "10.60.0.1"},
    "mdr-siem":       {"ip": "10.100.0.10", "gw": "10.100.0.1"},
    "auditor":        {"ip": "10.100.0.20", "gw": "10.100.0.1"},
    "taquilla":       {"ip": "10.200.0.10", "gw": "10.200.0.1"},
    "atm":            {"ip": "10.210.0.10", "gw": "10.210.0.1"},
}

# Servicios HTTP nominales (el puerto imita el del servicio real) y de quien dependen DE VERDAD.
SERVICIOS = {
    "core-db":        {"puertos": [1521],     "depende": []},
    "hsm":            {"puertos": [9000],     "depende": []},
    "middleware":     {"puertos": [8443],     "depende": ["core-db", "hsm"]},
    "web-banking":    {"puertos": [443, 80],  "depende": ["middleware"]},
    "api-movil":      {"puertos": [443],      "depende": ["middleware"]},
    "swift-alliance": {"puertos": [48002],    "depende": ["hsm"]},
    "atm":            {"puertos": [8080],     "depende": ["middleware"]},
}

NO_DECLARADAS = {("atm", "middleware")}


def _destino(nodo):
    return f"{NODOS[nodo]['ip']}:{SERVICIOS[nodo]['puertos'][0]}"


def comando_servicio(nodo):
    """Linea que arranca el servicio del nodo, o None si el nodo no presta servicio."""
    s = SERVICIOS.get(nodo)
    if s is None:
        return None
    partes = ["python3 /opt/banco/servicio.py", f"--nombre {nodo}"]
    partes += [f"--puerto {p}" for p in s["puertos"]]
    partes += [f"--depende {_destino(d)}" for d in s["depende"]]
    partes.append("--registro /var/log/banco/access.log")
    return " ".join(partes)


def args_monitor():
    return [f"{n}={_destino(n)}" for n in sorted(SERVICIOS)]


def nodos_auditor():
    return " ".join(f"{n}:{NODOS[n]['ip']}" for n in sorted(NODOS) if n not in ("mdr-siem", "auditor"))


def puertos_auditor():
    puertos = {22} | {p for s in SERVICIOS.values() for p in s["puertos"]}
    return ",".join(str(p) for p in sorted(puertos))


def main(argv):
    orden = argv[0] if argv else ""
    if orden == "servicio" and len(argv) == 2:
        print(comando_servicio(argv[1]) or "")
    elif orden == "monitor":
        print(" ".join(args_monitor()))
    elif orden == "nodos":
        print(nodos_auditor())
    elif orden == "puertos":
        print(puertos_auditor())
    elif orden == "servicios":
        print(" ".join(sorted(SERVICIOS)))
    else:
        print("uso: python3 -m lab.banco.red servicio <nodo> | monitor | nodos | puertos | servicios")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
