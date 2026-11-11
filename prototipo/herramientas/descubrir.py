"""Escanea la red del cliente con Nmap y guarda el descubrimiento que usa el asistente de red.

    sudo mdr descubrir --gestion 10.99.0.10 --rango 10.20.0.0/24 [--rango …] --externo 198.51.100.10 \\
        [--ritmo suave|normal] [--puertos 22,80,443] --salida descubrimiento.json --autorizado

Para un equipo MDR donde el servicio no tiene privilegios para el traceroute: se ejecuta con sudo y la
consola lee el fichero. Escanear exige la autorización por escrito del cliente. Plan:
documentacion/05-fase5-implementacion-del-prototipo/plan-asistente-de-red.md (tarea 3).
"""
import argparse
import getpass
import ipaddress
import json
import os
import sys
from datetime import datetime, timezone

from prototipo.servicio import descubrimiento as d


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mdr descubrir", description="descubre la red del cliente con Nmap")
    ap.add_argument("--gestion", required=True, help="IP de este equipo MDR en la red del cliente")
    ap.add_argument("--rango", action="append", required=True)
    ap.add_argument("--externo", required=True, help="una dirección de fuera, para trazar la salida")
    ap.add_argument("--ritmo", default="suave", choices=("suave", "normal"))
    ap.add_argument("--puertos", default=None, help="lista de puertos (por defecto, los 1000 más comunes)")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--operador", default=None)
    ap.add_argument("--autorizado", action="store_true",
                    help="confirma que tienes la autorización por escrito del cliente para escanear estos rangos")
    a = ap.parse_args(argv)
    if not a.autorizado:
        print("no se escanea: confirma con --autorizado que tienes la autorización por escrito del cliente")
        return 1
    try:
        ipaddress.IPv4Address(a.gestion)
    except ValueError:
        print(f"no se escanea: --gestion no es una IPv4: {a.gestion}")
        return 1
    try:
        puertos = "comunes" if not a.puertos else [int(x) for x in a.puertos.split(",")]
        peticion = d.validar_peticion({"rangos": a.rango, "externo": a.externo, "ritmo": a.ritmo, "puertos": puertos})
    except ValueError as e:
        print(f"no se escanea: {e}")
        return 1
    operador = a.operador or os.environ.get("SUDO_USER") or getpass.getuser()
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        r = d.descubrir(peticion, d.ejecutor_nmap(), a.gestion, operador, ahora, origen="cli")
    except RuntimeError as e:
        print(f"el escaneo falló: {e}")
        return 1
    if os.path.exists(a.salida):
        os.unlink(a.salida)
    with os.fdopen(os.open(a.salida, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    os.chmod(a.salida, 0o600)
    aviso = "" if r["traceroute"] else " · SIN caminos (traceroute necesita privilegios: usa sudo)"
    print(f"{len(r['equipos'])} equipos -> {a.salida}{aviso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
