"""Escribe el perfil mínimo con el que arranca una instalación nueva (asistente de red).

    python3 -m prototipo.herramientas.perfil_minimo --gestion 10.99.0.10 --rango 10.20.0.0/24 [...] --salida perfil.yml

No pisa un fichero que ya exista. Plan: documentacion/05-fase5-implementacion-del-prototipo/
plan-asistente-de-red.md (tarea 2).
"""
import argparse
import os
import sys

import yaml

from prototipo.motor import perfil as perfilm


def main(argv=None):
    ap = argparse.ArgumentParser(description="perfil mínimo para empezar con el asistente de red")
    ap.add_argument("--gestion", required=True, help="IP del equipo MDR en la red del cliente")
    ap.add_argument("--rango", action="append", required=True, help="rango de la red del cliente (repetible)")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args(argv)
    if os.path.exists(a.salida):
        print(f"{a.salida} ya existe: no se pisa.")
        return 1
    try:
        p = perfilm.perfil_minimo(a.gestion, a.rango)
    except ValueError as e:
        print(f"no se escribe: {e}")
        return 1
    with open(a.salida, "w", encoding="utf-8") as f:
        f.write("# Perfil mínimo: solo el MDR y los rangos. El asistente de red de la consola propone el completo.\n")
        yaml.safe_dump(p, f, allow_unicode=True, sort_keys=False)
    print(f"perfil mínimo -> {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
