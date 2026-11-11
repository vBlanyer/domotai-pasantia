"""Escanea la red del cliente con Nmap y guarda el descubrimiento que usa el asistente de red.

    sudo mdr descubrir --gestion 10.99.0.10 --rango 10.20.0.0/24 [--rango …] --externo 198.51.100.10 \\
        [--ritmo suave|normal] [--puertos 22,80,443] --salida descubrimiento.json

Para un equipo MDR donde el servicio no tiene privilegios para el traceroute: se ejecuta con sudo y la
consola lee el fichero. Escanear exige la autorización por escrito del cliente. Plan:
documentacion/05-fase5-implementacion-del-prototipo/plan-asistente-de-red.md (tarea 3).
"""
import argparse
import getpass
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
    a = ap.parse_args(argv)
    try:
        puertos = "comunes" if not a.puertos else [int(x) for x in a.puertos.split(",")]
        peticion = d.validar_peticion({"rangos": a.rango, "externo": a.externo, "ritmo": a.ritmo, "puertos": puertos})
    except ValueError as e:
        print(f"no se escanea: {e}")
        return 1
    operador = a.operador or os.environ.get("SUDO_USER") or getpass.getuser()
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        r = d.descubrir(peticion, d.ejecutor_nmap(), a.gestion, operador, ahora)
    except RuntimeError as e:
        print(f"el escaneo falló: {e}")
        return 1
    with open(a.salida, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    aviso = "" if r["traceroute"] else " · SIN caminos (traceroute necesita privilegios: usa sudo)"
    print(f"{len(r['equipos'])} equipos -> {a.salida}{aviso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
