"""Descubrimiento de la red del cliente con Nmap, para el asistente de red.

Tres pasadas de Nmap y una de ssh-keyscan, SIEMPRE con argumentos fijos: del técnico solo entran rangos
privados, una dirección externa, el ritmo y la lista de puertos, validados aquí antes de tocar la línea de
órdenes. Salen del equipo del MDR por la red del cliente (en el laboratorio, `docker exec` en el nodo de
gestión: desde la interfaz de gestión de Containerlab todo estaría a un salto y no se vería ningún
cortafuegos).

1. Quién hay: `nmap -sn` sobre los rangos.
2. Qué ofrece y por dónde se llega: puertos (tabla de servicios de Nmap) y `--traceroute` por equipo.
3. Por dónde se sale: `--traceroute` hacia la dirección externa.
4. Quién es quién: la huella SSH de cada equipo con el puerto 22 abierto (`ssh-keyscan`), para reconocer
   las varias interfaces de un mismo cortafuegos.

Nada se inventa: sin traceroute (Nmap sin privilegios) `saltos` es None; un salto que no responde queda
como None en su posición. Plan: documentacion/05-fase5-implementacion-del-prototipo/
plan-asistente-de-red.md (tarea 3).
"""
import base64
import hashlib
import ipaddress
import subprocess
import xml.etree.ElementTree as ET

from prototipo.accion import conector

MAX_RANGOS = 8
PREFIJO_MINIMO = 22
MAX_PUERTOS = 100
PLAZO_EQUIPO = "120s"
PLAZO_ORDEN_S = 1200
_RITMO = {"suave": ["-T3", "--max-rate", "100"], "normal": ["-T4"]}


def validar_peticion(cuerpo):
    """Normaliza {rangos, externo, ritmo, puertos}; ValueError con el motivo si algo no vale."""
    if not isinstance(cuerpo, dict):
        raise ValueError("petición no válida")
    rangos = cuerpo.get("rangos")
    if not isinstance(rangos, list) or not rangos:
        raise ValueError("rangos: hace falta una lista con al menos un rango")
    if len(rangos) > MAX_RANGOS:
        raise ValueError(f"rangos: como mucho {MAX_RANGOS}")
    normalizados = []
    for r in rangos:
        try:
            red = ipaddress.IPv4Network(str(r), strict=False)
        except ValueError:
            raise ValueError(f"rango no válido: {r}")
        if not red.is_private or red.prefixlen == 0:
            raise ValueError(f"rango {red}: solo redes privadas del cliente")
        if red.prefixlen < PREFIJO_MINIMO:
            raise ValueError(f"rango {red}: demasiado grande (como mucho /{PREFIJO_MINIMO})")
        normalizados.append(str(red))
    try:
        externo = str(ipaddress.IPv4Address(str(cuerpo.get("externo"))))
    except ValueError:
        raise ValueError("externo: una dirección IPv4")
    ritmo = cuerpo.get("ritmo", "suave")
    if ritmo not in _RITMO:
        raise ValueError("ritmo: suave o normal")
    puertos = cuerpo.get("puertos", "comunes")
    if puertos != "comunes":
        if (not isinstance(puertos, list) or not puertos or len(puertos) > MAX_PUERTOS
                or not all(isinstance(p, int) and not isinstance(p, bool) and 1 <= p <= 65535 for p in puertos)):
            raise ValueError(f"puertos: «comunes» o una lista de 1 a {MAX_PUERTOS} números entre 1 y 65535")
        puertos = sorted(set(puertos))
    return {"rangos": normalizados, "externo": externo, "ritmo": ritmo, "puertos": puertos}


def _alcance(peticion):
    if peticion["puertos"] == "comunes":
        return ["--top-ports", "1000"]
    return ["-p", ",".join(str(p) for p in peticion["puertos"])]


def argumentos_vivos(peticion):
    return ["nmap", "-sn", *_RITMO[peticion["ritmo"]], "-oX", "-", *peticion["rangos"]]


def argumentos_detalle(peticion, ips):
    return ["nmap", "--traceroute", "--host-timeout", PLAZO_EQUIPO, *_RITMO[peticion["ritmo"]], *_alcance(peticion),
            "-oX", "-", *ips]


def argumentos_salida(peticion):
    return ["nmap", "-sn", "--traceroute", *_RITMO[peticion["ritmo"]], "-oX", "-", peticion["externo"]]


def argumentos_huellas(ips):
    return ["ssh-keyscan", "-T", "5", "-t", "ed25519", *ips]


def _saltos(host, ip):
    traza = host.find("trace")
    if traza is None:
        return None
    por_ttl = {}
    for h in traza.findall("hop"):
        try:
            por_ttl[int(h.get("ttl"))] = h.get("ipaddr")
        except (TypeError, ValueError):
            continue
    if not por_ttl:
        return []
    ultimo = max(por_ttl)
    hasta = ultimo if por_ttl[ultimo] != ip else ultimo - 1
    return [por_ttl.get(t) for t in range(1, hasta + 1)]


def parsear_xml(texto):
    """Equipos «up» de una salida XML de Nmap (-oX -)."""
    raiz = ET.fromstring(texto)
    equipos = []
    for host in raiz.findall("host"):
        estado = host.find("status")
        if estado is None or estado.get("state") != "up":
            continue
        ip = mac = fabricante = None
        for a in host.findall("address"):
            if a.get("addrtype") == "ipv4":
                ip = a.get("addr")
            elif a.get("addrtype") == "mac":
                mac, fabricante = a.get("addr"), a.get("vendor")
        if not ip:
            continue
        dns = next((h.get("name") for h in host.findall("hostnames/hostname") if h.get("type") == "PTR"), None)
        puertos = []
        for p in host.findall("ports/port"):
            st = p.find("state")
            if st is None or st.get("state") != "open" or p.get("protocol") != "tcp":
                continue
            s = p.find("service")
            puertos.append({"puerto": int(p.get("portid")), "servicio": s.get("name") if s is not None else None,
                            "producto": s.get("product") if s is not None else None,
                            "version": s.get("version") if s is not None else None})
        equipos.append({"ip": ip, "dns": dns, "mac": mac, "fabricante": fabricante, "puertos": puertos,
                        "huella_ssh": None, "saltos": _saltos(host, ip)})
    return equipos


def parsear_huellas(texto):
    """{ip: "SHA256:…"} de la salida de ssh-keyscan (líneas «ip tipo clave»)."""
    huellas = {}
    for linea in (texto or "").splitlines():
        partes = linea.split()
        if len(partes) < 3 or linea.startswith("#"):
            continue
        try:
            crudo = base64.b64decode(partes[2], validate=True)
        except ValueError:
            continue
        huellas[partes[0]] = "SHA256:" + base64.b64encode(hashlib.sha256(crudo).digest()).decode().rstrip("=")
    return huellas


def ejecutor_nmap(entorno=None):
    """`correr(args) -> (rc, salida)`: en el nodo de gestión si TRIAJE_NODO_GESTION está fijado
    (laboratorio), si no en este equipo. Sin shell; plazo de PLAZO_ORDEN_S segundos."""
    import os
    entorno = os.environ if entorno is None else entorno
    nodo = entorno.get("TRIAJE_NODO_GESTION")

    def correr(args):
        argv = ["docker", "exec", nodo, *args] if nodo else list(args)
        try:
            cp = subprocess.run(argv, capture_output=True, text=True, timeout=PLAZO_ORDEN_S, env=conector._env_filtrado())
        except subprocess.TimeoutExpired:
            return 124, f"sin respuesta en {PLAZO_ORDEN_S} s"
        except OSError as e:
            return 127, str(e)
        return cp.returncode, cp.stdout if cp.returncode == 0 else (cp.stdout + cp.stderr)
    return correr


def _nmap(correr, args):
    rc, salida = correr(args)
    if rc != 0:
        raise RuntimeError(f"{args[0]} falló ({rc}): {salida.strip()[-300:]}")
    try:
        return parsear_xml(salida)
    except ET.ParseError as e:
        raise RuntimeError(f"{args[0]} devolvió una salida ilegible: {e}")


def descubrir(peticion, correr, gestion, operador, ahora):
    """Las cuatro pasadas, juntas. RuntimeError si Nmap falla (el llamador conserva lo anterior)."""
    vivos = [e for e in _nmap(correr, argumentos_vivos(peticion)) if e["ip"] != gestion]
    equipos = []
    if vivos:
        detalle = {e["ip"]: e for e in _nmap(correr, argumentos_detalle(peticion, [e["ip"] for e in vivos]))}
        for v in vivos:
            e = detalle.get(v["ip"]) or {**v, "puertos": []}
            e = {**e, "dns": e.get("dns") or v.get("dns"), "mac": e.get("mac") or v.get("mac"),
                 "fabricante": e.get("fabricante") or v.get("fabricante")}
            equipos.append(e)
        con_ssh = [e["ip"] for e in equipos if any(p["puerto"] == 22 for p in e["puertos"])]
        if con_ssh:
            _, salida = correr(argumentos_huellas(con_ssh))      # sin huella no se agrupa; no es un fallo
            huellas = parsear_huellas(salida)
            equipos = [{**e, "huella_ssh": huellas.get(e["ip"])} for e in equipos]
    fuera = _nmap(correr, argumentos_salida(peticion))
    salida = fuera[0]["saltos"] if fuera else None
    return {"version": 1, "fecha": ahora, "operador": operador, "gestion": gestion,
            "rangos": peticion["rangos"], "externo": peticion["externo"], "ritmo": peticion["ritmo"],
            "puertos": peticion["puertos"], "equipos": equipos, "salida": salida,
            "traceroute": any(e["saltos"] is not None for e in equipos) or salida is not None}
