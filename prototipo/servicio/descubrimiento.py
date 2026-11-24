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
# Las redes de un cliente: privadas (RFC 1918) y el espacio compartido de los operadores (RFC 6598). Un /22 de
# loopback, 0/8, 240/4 o enlace local NO es la red del cliente aunque `is_private` lo diga.
_REDES_CLIENTE = tuple(ipaddress.IPv4Network(r) for r in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10"))


def _de_cliente(red):
    return any(red.subnet_of(c) for c in _REDES_CLIENTE)


def _de_cliente_ip(ip):
    try:
        a = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return any(a in c for c in _REDES_CLIENTE)


def _externo_valido(a):
    """Una dirección DE FUERA: ni de las redes del cliente ni especial (loopback, multicast, reservada…). Las de
    documentación (198.51.100.0/24…) valen: son las del laboratorio."""
    return not (any(a in c for c in _REDES_CLIENTE) or a.is_loopback or a.is_link_local or a.is_multicast
                or a.is_unspecified or a.is_reserved or a == ipaddress.IPv4Address("255.255.255.255"))


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
        if not _de_cliente(red):
            raise ValueError(f"rango {red}: solo redes privadas del cliente")
        if red.prefixlen < PREFIJO_MINIMO:
            raise ValueError(f"rango {red}: demasiado grande (como mucho /{PREFIJO_MINIMO})")
        normalizados.append(str(red))
    try:
        ext = ipaddress.IPv4Address(str(cuerpo.get("externo")))
    except ValueError:
        raise ValueError("externo: una dirección IPv4")
    # Una dirección interna invertiría la cadena de cortafuegos (el borde saldría dentro), sin aviso.
    if not _externo_valido(ext) or any(ext in ipaddress.IPv4Network(r) for r in normalizados):
        raise ValueError(f"externo {ext}: tiene que ser una dirección de internet, fuera de la red del cliente")
    externo = str(ext)
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


def _traza(host):
    """{ttl: ip} de la traza del equipo; None si Nmap no trazó."""
    traza = host.find("trace")
    if traza is None:
        return None
    por_ttl = {}
    for h in traza.findall("hop"):
        try:
            por_ttl[int(h.get("ttl"))] = h.get("ipaddr")
        except (TypeError, ValueError):
            continue
    return por_ttl


def _completar_omitidos(trazas):
    """Nmap no repite en el XML los saltos que ya trazó para otro equipo («hop sharing»): con muchos equipos
    detrás del mismo cortafuegos, la mayoría llegan sin sus primeros saltos (escaneo del banco, 23/11: 121 de
    185). Esos saltos son los de OTRO equipo trazado entero; se toman de los de su subred si los hay y, por
    TTL, solo si todos los candidatos coinciden. Si no, el hueco se queda: no se inventa un camino."""
    completas = {ip: t for ip, t in trazas.items() if t and min(t) == 1}

    def sirve(o, c, k):
        # Sus saltos 1..k-1 son intermedios: ni huecos ni el propio equipo (la puerta de enlace de una subred se
        # alcanza en el TTL 1 y su «salto» es ella misma).
        return all(c.get(n) and c.get(n) != o for n in range(1, k))
    for ip, t in trazas.items():
        if not t or min(t) == 1:
            continue
        k = min(t)
        cand = [c for o, c in completas.items() if o != ip and sirve(o, c, k)]
        misma = [c for o, c in completas.items() if o != ip and _misma_24(o, ip) and sirve(o, c, k)]
        for n in range(1, k):
            vistos = {c[n] for c in (misma or cand)}
            if len(vistos) == 1:
                t[n] = vistos.pop()


def _misma_24(a, b):
    return a.rsplit(".", 1)[0] == b.rsplit(".", 1)[0]


def _saltos(por_ttl, ip):
    if por_ttl is None:
        return None
    if not por_ttl:
        return []
    ultimo = max(por_ttl)
    if por_ttl[ultimo] == ip:
        return [por_ttl.get(t) for t in range(1, ultimo)]
    # La traza no llegó al equipo: lo que hay después del último salto visible no se sabe (hueco final).
    return [por_ttl.get(t) for t in range(1, ultimo + 1)] + [None]


def parsear_xml(texto):
    """Equipos «up» de una salida XML de Nmap (-oX -)."""
    raiz = ET.fromstring(texto)
    equipos, trazas = [], {}
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
        trazas[ip] = _traza(host)
        equipos.append({"ip": ip, "dns": dns, "mac": mac, "fabricante": fabricante, "puertos": puertos,
                        "huella_ssh": None, "saltos": None})
    _completar_omitidos(trazas)
    for e in equipos:
        e["saltos"] = _saltos(trazas[e["ip"]], e["ip"])
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


def descubrir(peticion, correr, gestion, operador, ahora, origen="consola"):
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
    fuera = _nmap(correr, argumentos_salida(peticion))
    salida = fuera[0]["saltos"] if fuera else None
    # La huella SSH de cada equipo con el 22 abierto Y la de los saltos privados del camino que quedan fuera de
    # los rangos (el cortafuegos que el MDR ve por su red de gestión): con ella se reconocen como suyas las IPs
    # de sus otras patas, que sí están en los rangos (banco, 24/11: 18 filas para 10 equipos).
    ips = {e["ip"] for e in equipos}
    pasos = [s for e in equipos for s in (e.get("saltos") or []) if s] + [s for s in (salida or []) if s]
    saltos_fuera = sorted({s for s in pasos if s not in ips and s != gestion and _de_cliente_ip(s)})
    con_ssh = [e["ip"] for e in equipos if any(p["puerto"] == 22 for p in e["puertos"])]
    huellas = {}
    if con_ssh or saltos_fuera:
        _, texto = correr(argumentos_huellas(con_ssh + saltos_fuera))   # sin huella no se agrupa; no es un fallo
        huellas = parsear_huellas(texto)
        equipos = [{**e, "huella_ssh": huellas.get(e["ip"])} for e in equipos]
    return {"version": 1, "fecha": ahora, "operador": operador, "gestion": gestion, "origen": origen, "autorizado": True,
            "rangos": peticion["rangos"], "externo": peticion["externo"], "ritmo": peticion["ritmo"],
            "puertos": peticion["puertos"], "equipos": equipos, "salida": salida,
            "huellas_saltos": {s: huellas[s] for s in saltos_fuera if s in huellas},
            "traceroute": any(e["saltos"] is not None for e in equipos) or salida is not None}
