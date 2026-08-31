"""Núcleo de `auditar.sh`: nmap -> hallazgos.json.

Separa el parseo y la decisión de "escaneo fallido" (funciones puras,
probadas con unittest) de la E/S contra Docker (validada ejecutando el
script contra el laboratorio en vivo).
"""
import json
import re
import subprocess
import sys


def parsear_puertos(stdout):
    """Extrae {puerto, servicio, estado} de la salida de `nmap`."""
    puertos = []
    for m in re.finditer(r"^(\d+)/tcp\s+(\S+)\s+(\S+)", stdout, re.M):
        puertos.append({"puerto": int(m.group(1)), "servicio": m.group(3), "estado": m.group(2)})
    return puertos


def resultado_nodo(returncode, stdout):
    """Puertos del nodo si el escaneo tuvo éxito, o None si falló.

    I2: un escaneo fallido (returncode != 0: `docker exec` o `nmap` no
    corrieron) NUNCA se traduce en una lista vacía. Una lista vacía real
    significa "escaneado con éxito, sin puertos abiertos" (FP legítimo si
    una alerta ataca ese nodo); confundirla con un escaneo fallido voltearía
    en silencio un VP real a FP. Un fallo devuelve None para que el llamador
    OMITA la clave del nodo: `postura_de` trata la ausencia como caso gris.
    """
    if returncode != 0:
        return None
    return parsear_puertos(stdout)


def version_nmap(auditor):
    """Primera línea de `nmap --version`, o None si el comando falló."""
    r = subprocess.run(["docker", "exec", auditor, "nmap", "--version"],
                        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout.splitlines()[0].split(" (")[0]


def escanear_nodo(auditor, ip):
    r = subprocess.run(
        ["docker", "exec", auditor, "nmap", "-Pn", "--top-ports", "100", ip],
        capture_output=True, text=True)
    return resultado_nodo(r.returncode, r.stdout)


def main(argv):
    salida, auditor, ts = argv[1], argv[2], argv[3]
    pares = argv[4:]

    ver = version_nmap(auditor)
    if ver is None:
        # RF-09: sin versión de escáner registrada, los resultados dejan de
        # ser comparables entre campañas. Aborta en vez de escribir un
        # hallazgos.json con version_herramienta a ciegas.
        sys.exit("auditar: no se pudo obtener la versión de nmap; aborta")

    nodos = {}
    omitidos = []
    for par in pares:
        nombre, ip = par.split(":")
        r = escanear_nodo(auditor, ip)
        if r is None:
            omitidos.append(nombre)  # escaneo fallido: se omite, no se escribe []
            continue
        nodos[nombre] = r

    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"version_herramienta": ver, "timestamp": ts, "nodos": nodos},
                   f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in nodos.values())
    msg = f"hallazgos -> {salida} ({total} servicios, {len(nodos)} nodos)"
    if omitidos:
        msg += f" -- OMITIDOS por escaneo fallido (tratar como gris): {', '.join(omitidos)}"
    print(msg)


if __name__ == "__main__":
    main(sys.argv)
