"""Lanzador de ataques del laboratorio del banco, por número, para demostraciones.

    sh lab/banco/banco.sh atacar        (o: python3 -m lab.banco.demo)

Lista los casos vivos del catálogo (`lab/banco/casos.py`) y lanza el que elijas contra la red, para
verlo decidir en el daemon/tablero. Reutiliza solo los DATOS del catálogo; no toca el prototipo.
Respeta los 60 s de silencio de la regla 5763 de Wazuh entre ataques, y ofrece deshacer/restaurar.
"""
import subprocess
import sys
import time

from lab.banco import casos, red

P = "clab-banco"
ESPERA_WAZUH = 65          # la regla 5763 de Wazuh se silencia 60 s tras dispararse


def casos_vivos():
    """Los casos de nivel vivo que lanzan algo (ataque real o preparación), en el orden del catálogo."""
    return [c for c in casos.CASOS if c["nivel"] == "vivo" and (c.get("ataque") or c.get("preparar"))]


def _exec(nodo, cmd, ejecutar=subprocess.run):
    return ejecutar(["docker", "exec", f"{P}-{nodo}", "sh", "-c", cmd], capture_output=True, text=True)


def menu(vivos):
    return "\n".join(f"  {i}. {c['id']} — {c['titulo']}" for i, c in enumerate(vivos, 1))


def lanzar(caso, ejecutar=subprocess.run):
    """Ejecuta la preparación (si la hay) y luego el ataque, vía docker exec."""
    for nodo, cmd in caso.get("preparar", []):
        _exec(nodo, cmd, ejecutar)
    if caso.get("ataque"):
        origen, cmd = caso["ataque"]
        _exec(origen, cmd, ejecutar)


def deshacer(caso, ejecutar=subprocess.run):
    for nodo, cmd in caso.get("deshacer", []):
        if cmd == "REARRANCAR":
            ejecutar(["docker", "exec", "-d", f"{P}-{nodo}", "sh", "-c", red.comando_servicio(nodo)])
        else:
            _exec(nodo, cmd, ejecutar)


def main(argv=None):
    vivos = casos_vivos()
    ultimo = 0.0
    try:
        while True:
            print("\n== Ataques del banco (para el daemon/tablero) ==")
            print(menu(vivos))
            print("  0. Salir")
            sel = input(f"Elige un ataque [0-{len(vivos)}]: ").strip()
            if sel in ("0", "", "q"):
                return 0
            try:
                caso = vivos[int(sel) - 1]
                if int(sel) < 1:
                    raise IndexError
            except (ValueError, IndexError):
                print("  opción no válida")
                continue
            if caso.get("ataque"):
                espera = ESPERA_WAZUH - (time.time() - ultimo)
                if ultimo and espera > 0:
                    print(f"  (esperando {int(espera)} s: la regla 5763 se silencia 60 s tras dispararse)")
                    time.sleep(espera)
            print(f"  lanzando {caso['id']} — {caso['titulo']}...")
            lanzar(caso)
            if caso.get("ataque"):
                ultimo = time.time()
            if caso.get("deshacer") and input("  ¿deshacer/restaurar el caso? [s/N] ").strip().lower().startswith("s"):
                deshacer(caso)
                print("  restaurado")
    except (KeyboardInterrupt, EOFError):
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
