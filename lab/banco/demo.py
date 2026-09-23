"""Lanzador de ataques del laboratorio del banco, por número, para demostraciones.

    sh lab/banco/banco.sh atacar        (o: python3 -m lab.banco.demo)

Lista los casos vivos del catálogo (`lab/banco/casos.py`) y lanza el que elijas contra la red, para
verlo decidir en el daemon/tablero. Reutiliza solo los DATOS del catálogo; no toca el prototipo.
Respeta los 60 s de silencio de la regla 5763 de Wazuh entre ataques, y ofrece deshacer/restaurar.

Con la tecla `r` se activa la **IP de origen rotativa**: cada ataque sale desde una IP nueva de la
misma subred del atacante (alias en la interfaz de datos + `ssh -b`), para poder repetir el mismo
ataque sin chocar con la supresión del MDR ni con el bloqueo previo, como un atacante que rota IPs.
"""
import subprocess
import sys
import time

from lab.banco import casos, red

P = "clab-banco"
ESPERA_WAZUH = 65          # la regla 5763 de Wazuh se silencia 60 s tras dispararse
IFACE_DATOS = "eth1"       # la interfaz del plano de datos en los nodos del banco


def casos_vivos():
    """Los casos de nivel vivo que lanzan algo (ataque real o preparación), en el orden del catálogo."""
    return [c for c in casos.CASOS if c["nivel"] == "vivo" and (c.get("ataque") or c.get("preparar"))]


def rotable(caso):
    """Un caso admite IP de origen rotativa si lanza un ataque con origen y destino conocidos."""
    return bool(caso.get("ataque") and caso.get("origen") and caso.get("destino_ip"))


def ip_rotada(base_ip, n):
    """Una IP nueva en la /24 de `base_ip`, hosts 11.. para no pisar el gateway (.1), el nodo base
    (.10) ni la difusión (.255). Determinista: el n-ésimo lanzamiento usa .{11+n}."""
    subred = base_ip.rsplit(".", 1)[0]
    host = 11 + (n % 240)          # 11..250, todos válidos y distintos de .1/.10/.255
    return f"{subred}.{host}"


def ataque_rotado(caso, src_ip):
    """El ataque del caso, pero desde `src_ip` (alias en la interfaz de datos + `ssh -b`)."""
    nodo = caso["ataque"][0]
    return casos.fuerza_bruta_atada(nodo, caso["destino_ip"], src_ip, iface=IFACE_DATOS)


def deshacer_rotado(caso, src_ip):
    """Las reglas de deshacer del caso con la IP base sustituida por la rotada, para retirar el
    bloqueo que el MDR aplicó a `src_ip` (no a la IP base)."""
    base = caso.get("origen", "")
    return [(nodo, cmd.replace(base, src_ip) if base else cmd) for nodo, cmd in caso.get("deshacer", [])]


def _exec(nodo, cmd, ejecutar=subprocess.run):
    return ejecutar(["docker", "exec", f"{P}-{nodo}", "sh", "-c", cmd], capture_output=True, text=True)


def menu(vivos):
    return "\n".join(f"  {i}. {c['id']} — {c['titulo']}" for i, c in enumerate(vivos, 1))


def lanzar(caso, ejecutar=subprocess.run, src_ip=None):
    """Ejecuta la preparación (si la hay) y luego el ataque, vía docker exec. Con `src_ip`, lanza
    el ataque desde esa IP de origen nueva (rotación); sin él, comportamiento actual."""
    for nodo, cmd in caso.get("preparar", []):
        _exec(nodo, cmd, ejecutar)
    if caso.get("ataque"):
        origen, cmd = ataque_rotado(caso, src_ip) if src_ip else caso["ataque"]
        _exec(origen, cmd, ejecutar)


def deshacer(caso, ejecutar=subprocess.run, src_ip=None):
    reglas = deshacer_rotado(caso, src_ip) if src_ip else caso.get("deshacer", [])
    for nodo, cmd in reglas:
        if cmd == "REARRANCAR":
            ejecutar(["docker", "exec", "-d", f"{P}-{nodo}", "sh", "-c", red.comando_servicio(nodo)])
        else:
            _exec(nodo, cmd, ejecutar)


def main(argv=None, leer=input, ejecutar=subprocess.run, dormir=time.sleep):
    vivos = casos_vivos()
    ultimo = 0.0
    rotar = False
    contadores = {}                 # subred -> nº de lanzamientos rotados (para IPs nuevas contiguas)
    try:
        while True:
            print("\n== Ataques del banco (para el daemon/tablero) ==")
            print(menu(vivos))
            print(f"  r. IP de origen rotativa: {'ON' if rotar else 'OFF'}  "
                  "(cada ataque desde una IP nueva; esquiva supresión y bloqueo previo)")
            print("  0. Salir")
            sel = leer(f"Elige [0-{len(vivos)}, r]: ").strip().lower()
            if sel in ("0", "", "q"):
                return 0
            if sel == "r":
                rotar = not rotar
                continue
            try:
                caso = vivos[int(sel) - 1]
                if int(sel) < 1:
                    raise IndexError
            except (ValueError, IndexError):
                print("  opción no válida")
                continue

            # IP de origen: rotada (si procede) o la base del caso.
            src = None
            if rotar and rotable(caso):
                subred = caso["origen"].rsplit(".", 1)[0]
                n = contadores.get(subred, 0)
                src = ip_rotada(caso["origen"], n)
                contadores[subred] = n + 1

            # La espera de 60 s solo hace falta al repetir desde la MISMA IP; con IP nueva no aplica.
            if caso.get("ataque") and src is None:
                espera = ESPERA_WAZUH - (time.time() - ultimo)
                if ultimo and espera > 0:
                    print(f"  (esperando {int(espera)} s: la regla 5763 se silencia 60 s tras dispararse)")
                    dormir(espera)

            desde = f" desde {src}" if src else ""
            print(f"  lanzando {caso['id']} — {caso['titulo']}{desde}...")
            lanzar(caso, ejecutar=ejecutar, src_ip=src)
            if caso.get("ataque") and src is None:
                ultimo = time.time()
            if caso.get("deshacer") and leer("  ¿deshacer/restaurar el caso? [s/N] ").strip().lower().startswith("s"):
                deshacer(caso, ejecutar=ejecutar, src_ip=src)
                print("  restaurado")
    except (KeyboardInterrupt, EOFError):
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
