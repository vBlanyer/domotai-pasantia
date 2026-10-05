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
    """Un caso admite IP de origen rotativa si lanza un ataque desde un origen conocido."""
    return bool(caso.get("ataque") and caso.get("origen"))


def ip_rotada(base_ip, n):
    """Una IP nueva en la /24 de `base_ip`, hosts 11.. para no pisar el gateway (.1), el nodo base
    (.10) ni la difusión (.255). Determinista: el n-ésimo lanzamiento usa .{11+n}."""
    subred = base_ip.rsplit(".", 1)[0]
    host = 11 + (n % 240)          # 11..250, todos válidos y distintos de .1/.10/.255
    return f"{subred}.{host}"


def ataque_rotado(caso, src_ip):
    """El ataque del propio caso, pero desde `src_ip`: alias en la interfaz de datos y el cliente
    (ssh, nc o curl) atado a esa IP. Antes solo sabía rotar una fuerza bruta SSH."""
    nodo, cmd = caso["ataque"]
    alias = f"ip addr add {src_ip}/24 dev {IFACE_DATOS} 2>/dev/null; "
    return nodo, alias + casos.atar_a_ip(cmd, src_ip)


def deshacer_rotado(caso, src_ip):
    """Las reglas de deshacer del caso con la IP base sustituida por la rotada, para retirar el
    bloqueo que el MDR aplicó a `src_ip` (no a la IP base)."""
    base = caso.get("origen", "")
    return [(nodo, cmd.replace(base, src_ip) if base else cmd) for nodo, cmd in caso.get("deshacer", [])]


def _exec(nodo, cmd, ejecutar=subprocess.run):
    return ejecutar(["docker", "exec", f"{P}-{nodo}", "sh", "-c", cmd], capture_output=True, text=True)


def menu(vivos):
    return "\n".join(f"  {i}. {c['id']} — {c['titulo']}" for i, c in enumerate(vivos, 1))


LINEA_A_MEDIDA = "  a. Ataque a medida (elige equipo objetivo, servicio y origen)"
IP_EXTERNA = "198.51.100.10"       # el atacante externo, la misma que usan los casos de internet


def _elegir(leer, prompt, opciones, etiqueta):
    """Imprime `opciones` numeradas (etiqueta(opcion) -> texto) y devuelve la elegida, o None si se
    cancela (0/intro) o la entrada no es válida."""
    for i, o in enumerate(opciones, 1):
        print(f"    {i}. {etiqueta(o)}")
    sel = (leer(prompt) or "").strip().lower()
    if sel in ("0", "", "q"):
        return None
    try:
        return opciones[int(sel) - 1] if int(sel) >= 1 else None
    except (ValueError, IndexError):
        print("  opción no válida")
        return None


def elegir_a_medida(leer):
    """Pregunta equipo objetivo, tipo de ataque (solo los que tienen sentido para ese equipo) y
    origen (internet o un equipo interno), y devuelve un caso a medida listo para `lanzar`. None si
    se cancela en cualquier paso."""
    objetivos = sorted(red.NODOS)
    print("\n  Equipo objetivo:")
    obj = _elegir(leer, f"  objetivo [1-{len(objetivos)}, 0=cancelar]: ",
                  objetivos, lambda n: f"{n} ({red.NODOS[n]['ip']})")
    if obj is None:
        return None
    puertos = red.SERVICIOS.get(obj, {}).get("puertos", [])
    tipos = casos.tipos_para(puertos)
    print(f"\n  Tipo de ataque contra {obj}:")
    tipo = _elegir(leer, f"  ataque [1-{len(tipos)}, 0=cancelar]: ", tipos, lambda t: t["titulo"])
    if tipo is None:
        return None
    origenes = ["internet"] + [n for n in objetivos if n != obj]
    print("\n  Origen del ataque:")
    org = _elegir(leer, f"  origen [1-{len(origenes)}, 0=cancelar]: ", origenes,
                  lambda n: "internet (atacante externo)" if n == "internet" else f"{n} ({red.NODOS[n]['ip']})")
    if org is None:
        return None
    origen_nodo, origen_ip = ("internet", IP_EXTERNA) if org == "internet" else (org, red.NODOS[org]["ip"])
    puerto = next((p for p in puertos if p in casos.PUERTOS_WEB), None)
    return casos.caso_a_medida(tipo["clave"], origen_nodo, origen_ip, obj, red.NODOS[obj]["ip"], puerto)


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
    sin_deshacer = {}               # origen -> caso que atacó desde él y no se deshizo (puede estar bloqueado)
    try:
        while True:
            print("\n== Ataques del banco (para el daemon/tablero) ==")
            print(menu(vivos))
            print(LINEA_A_MEDIDA)
            print(f"  r. IP de origen rotativa: {'ON' if rotar else 'OFF'}  "
                  "(cada ataque desde una IP nueva; esquiva supresión y bloqueo previo)")
            print("  0. Salir")
            sel = leer(f"Elige [0-{len(vivos)}, a, r]: ").strip().lower()
            if sel in ("0", "", "q"):
                return 0
            if sel == "r":
                rotar = not rotar
                continue
            if sel == "a":
                caso = elegir_a_medida(leer)
                if caso is None:
                    continue
            else:
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

            origen = caso.get("origen")
            if rotar and caso.get("ataque") and not rotable(caso):
                print(f"  (el caso {caso['id']} no admite IP rotativa: sale desde {origen})")
            if caso.get("ataque") and src is None and origen in sin_deshacer:
                print(f"  ⚠ {origen} ya atacó en {sin_deshacer[origen]} sin deshacer: puede que el MDR la haya "
                      "bloqueado y este ataque no llegue. Usa r (IP rotativa) o sh lab/banco/banco.sh restaurar.")

            desde = f" desde {src}" if src else ""
            print(f"  lanzando {caso['id']} — {caso['titulo']}{desde}...")
            lanzar(caso, ejecutar=ejecutar, src_ip=src)
            if caso.get("ataque") and src is None:
                ultimo = time.time()
                if origen:
                    sin_deshacer[origen] = caso["id"]
            if caso.get("deshacer") and leer("  ¿deshacer/restaurar el caso? [s/N] ").strip().lower().startswith("s"):
                deshacer(caso, ejecutar=ejecutar, src_ip=src)
                if src is None:
                    sin_deshacer.pop(origen, None)
                print("  restaurado")
    except (KeyboardInterrupt, EOFError):
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
