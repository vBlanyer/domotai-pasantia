"""Asistente de red: de lo que descubrió Nmap a una PROPUESTA de perfil, postura y política.

Funciones puras, sin E/S: el borrador es lo que el técnico acepta, corrige o descarta; de él salen los
tres ficheros que la consola ofrece para descargar. La consola NUNCA escribe el perfil vivo.

Reglas de deducción (plan-asistente-de-red.md, tarea 4; las fijan sus pruebas):
- Cortafuegos: una IP de los rangos que aparece como salto intermedio. Las IPs con su misma huella SSH son
  sus otras interfaces; su clave es la IP vista como salto desde el MDR (la que usará el conector).
- Cadena hacia fuera: los cortafuegos del traceroute a la dirección externa, en orden; el último es el
  borde. Uno que no esté ahí toma de gateway el salto anterior en el camino donde aparece (deducido).
- Equipo: su gateway es su último salto; sin traceroute, o con ese salto mudo, queda «sin camino».
- Papel: cortafuegos; frágil (sin SSH y con 9100, 515, 631 o 554); servidor (con SSH); si no, desconocido.
"""
import copy
import ipaddress
import re

from prototipo.motor import perfil as perfilm
from prototipo.motor import politica_empresa as pe

PAPELES = ("servidor", "cortafuegos", "fragil", "desconocido")
CRITICIDADES = ("baja", "media", "alta", "critica")
_NOMBRE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}\Z")
_FRAGILES = {9100, 515, 631, 554}
_CAMPOS = {"incluido", "nombre", "zona", "papel", "criticidad", "no_tocar", "depende_de", "funcion", "gateway"}


def _en_rangos(ip, rangos):
    try:
        a = ipaddress.ip_address(ip)
        return any(a in ipaddress.ip_network(r, strict=False) for r in rangos)
    except ValueError:
        return False


def _subred(ip):
    return str(ipaddress.ip_network(f"{ip}/24", strict=False))


def borrador_inicial(desc):
    """El borrador que propone el asistente a partir del descubrimiento."""
    rangos = desc.get("rangos") or []
    equipos = {e["ip"]: e for e in desc.get("equipos") or []}
    salida = [s for s in (desc.get("salida") or []) if s]
    saltos_vistos = {s for e in equipos.values() for s in (e.get("saltos") or []) if s}
    fws = sorted({ip for ip in saltos_vistos | set(salida) if _en_rangos(ip, rangos)})
    # Interfaces de cada cortafuegos: las IPs con su misma huella SSH.
    interfaces, absorbidas = {}, set()
    for f in fws:
        huella = (equipos.get(f) or {}).get("huella_ssh")
        otras = sorted(ip for ip, e in equipos.items() if huella and ip != f and e.get("huella_ssh") == huella and ip not in fws)
        interfaces[f] = otras
        absorbidas.update(otras)
    cadena = [s for s in salida if s in fws]
    gw_fw, deducido = {}, {}
    for i, f in enumerate(cadena):
        gw_fw[f], deducido[f] = (cadena[i + 1] if i + 1 < len(cadena) else None), False
    for f in fws:
        if f in gw_fw:
            continue
        previo = None
        for e in equipos.values():
            s = e.get("saltos") or []
            if f in s and s.index(f) > 0:
                previo = s[s.index(f) - 1]
                break
        if previo is None and f in equipos and (equipos[f].get("saltos") or []):
            previo = equipos[f]["saltos"][-1]
        gw_fw[f], deducido[f] = (previo if previo in fws else None), True

    salida_b = {}
    for ip, e in equipos.items():
        if ip in absorbidas:
            continue
        puertos = sorted(p["puerto"] for p in e.get("puertos") or [])
        base = {"incluido": True, "nombre": (e.get("dns") or "").split(".")[0].lower() if e.get("dns") else "",
                "criticidad": "media", "no_tocar": False, "depende_de": [], "funcion": "", "servicios": puertos,
                "interfaces": [], "deducido": False, "sin_camino": False, "huella": bool(e.get("huella_ssh"))}
        if ip in fws:
            salida_b[ip] = {**base, "papel": "cortafuegos", "zona": None, "gateway": gw_fw[ip],
                            "interfaces": interfaces[ip], "deducido": deducido[ip]}
            continue
        saltos = e.get("saltos")
        ultimo = saltos[-1] if saltos else None
        gateway = ultimo if ultimo in fws else None
        sin_camino = saltos is None or (bool(saltos) and ultimo is None)
        if 22 in puertos:
            papel = "servidor"
        elif _FRAGILES & set(puertos):
            papel = "fragil"
        else:
            papel = "desconocido"
        salida_b[ip] = {**base, "papel": papel, "zona": f"Zona {_subred(ip)}", "gateway": gateway,
                        "sin_camino": sin_camino, "incluido": not (papel == "desconocido" and not puertos)}
    for f in fws:                     # un salto que no está en los rangos escaneados no se conoce más allá
        if f not in salida_b:
            salida_b[f] = {"incluido": True, "nombre": "", "criticidad": "media", "no_tocar": False, "depende_de": [],
                           "funcion": "", "servicios": [], "interfaces": [], "papel": "cortafuegos", "zona": None,
                           "gateway": gw_fw[f], "deducido": deducido[f], "sin_camino": False, "huella": False}
    return {"version": 1, "basado_en": desc.get("fecha"), "gestion": desc.get("gestion"), "redes_internas": list(rangos),
            "salida": salida, "traceroute": bool(desc.get("traceroute")), "equipos": salida_b}


def aplicar_cambios(borrador, cambios):
    """Borrador NUEVO con los cambios del técnico ({ip: {campo: valor}}). ValueError si algo no vale."""
    if not isinstance(cambios, dict):
        raise ValueError("cambios: se esperaba {ip: {campo: valor}}")
    nuevo = copy.deepcopy(borrador)
    eq = nuevo["equipos"]
    fws = {ip for ip, e in eq.items() if e["papel"] == "cortafuegos"}
    for ip, campos in cambios.items():
        if ip not in eq:
            raise ValueError(f"{ip}: no es un equipo del borrador")
        if not isinstance(campos, dict) or set(campos) - _CAMPOS:
            raise ValueError(f"{ip}: campos admitidos: {', '.join(sorted(_CAMPOS))}")
        for k, v in campos.items():
            if k in ("incluido", "no_tocar") and not isinstance(v, bool):
                raise ValueError(f"{ip}.{k}: verdadero o falso")
            if k == "nombre" and not (v == "" or (isinstance(v, str) and _NOMBRE.match(v))):
                raise ValueError(f"{ip}.nombre: minúsculas, números y guiones (2 a 31)")
            if k == "zona" and not (v is None or (isinstance(v, str) and 0 < len(v.strip()) <= 40)):
                raise ValueError(f"{ip}.zona: un nombre de hasta 40 caracteres")
            if k == "papel" and v not in PAPELES:
                raise ValueError(f"{ip}.papel: {', '.join(PAPELES)}")
            if k == "criticidad" and v not in CRITICIDADES:
                raise ValueError(f"{ip}.criticidad: {', '.join(CRITICIDADES)}")
            if k == "depende_de" and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                raise ValueError(f"{ip}.depende_de: una lista de nombres")
            if k == "gateway" and v is not None and v not in fws:
                raise ValueError(f"{ip}.gateway: debe ser un cortafuegos del borrador")
            if k == "funcion":
                if not isinstance(v, str):
                    raise ValueError(f"{ip}.funcion: texto")
                v = re.sub(r"[\x00-\x1f\x7f]", "", v).strip()[:80]
            if k == "zona" and v is not None:
                v = v.strip()
            eq[ip][k] = v
    return nuevo


def _incluidos(b):
    return {ip: e for ip, e in b["equipos"].items() if e["incluido"]}


def _nombre_de(b, ip):
    return ((b["equipos"].get(ip) or {}).get("nombre")) or None


def perfil_desde_borrador(b):
    """El perfil.yml propuesto: la red, sin reglas de política (van en politica.yml)."""
    inc = _incluidos(b)
    fws = {ip for ip, e in inc.items() if e["papel"] == "cortafuegos"}
    p = perfilm.perfil_minimo(b["gestion"], b["redes_internas"])
    activos, topologia, enlaces, zonas = p["activos"], {}, {}, {}
    for ip, e in sorted(inc.items()):
        nombre = e["nombre"]
        if not nombre:
            continue
        gw = _nombre_de(b, e["gateway"]) if e.get("gateway") in fws else None
        if e["papel"] == "cortafuegos":
            topologia[nombre] = {"rol": "firewall_perimetral", "ip": ip, **({"gateway": gw} if gw else {})}
            enlaces[nombre] = gw or "internet"
            continue
        activo = {"ip": ip, "criticidad": e["criticidad"], "servicios_prestados": list(e["servicios"])}
        if e["funcion"]:
            activo["funcion"] = e["funcion"]
        if e["depende_de"]:
            activo["depende_de"] = list(e["depende_de"])
        activos[nombre] = activo
        if e["papel"] == "servidor" and gw and not e["no_tocar"]:
            topologia[nombre] = {"rol": "host_victima", "ip": ip, "gateway": gw}
        if gw:
            enlaces[nombre] = gw
        if e.get("zona"):
            zonas.setdefault(e["zona"], []).append(nombre)
    salida_fw = next((s for s in b.get("salida") or [] if s in fws and _nombre_de(b, s)), None)
    if salida_fw:
        enlaces["mdr"] = _nombre_de(b, salida_fw)
    p["topologia"] = topologia
    p["red"] = {"nodos": {"internet": {"tipo": "externo"}}, "enlaces": enlaces, "zonas": {**zonas, "Gestión": ["mdr"]}}
    return p


def postura_desde(desc, b):
    """postura.json en el formato de escanear_postura: los puertos abiertos de cada equipo incluido."""
    por_ip = {e["ip"]: e for e in desc.get("equipos") or []}
    nodos = {}
    for ip, e in sorted(_incluidos(b).items()):
        if not e["nombre"] or ip not in por_ip:
            continue
        nodos[e["nombre"]] = [{"puerto": p["puerto"], "servicio": p.get("servicio") or "desconocido", "estado": "open"}
                              for p in sorted(por_ip[ip]["puertos"], key=lambda x: x["puerto"])]
    return {"version_herramienta": "nmap (asistente de red)", "timestamp": desc.get("fecha"), "nodos": nodos}


def politica_desde(b, fecha):
    """Propuesta de politica.yml: el MDR como administrador y todo esperando a un analista."""
    return {"politica": {"version": 1, "aprobada_por": "[pendiente de aprobación]", "fecha": fecha},
            "confianza": {"administradores": [b["gestion"]], "socios_criticos": []},
            "respuesta_automatica": {"certeza_minima": 0.9, "por_defecto": "con_analista",
                                     "si_afecta_a_un_servicio": "con_analista", "solo_observar": "con_analista",
                                     "equipos_propios": "con_analista"}}


def validar(b, catalogo):
    """{"errores", "avisos"}: con errores no se exporta."""
    errores, avisos = [], []
    inc = _incluidos(b)
    fws = {ip for ip, e in inc.items() if e["papel"] == "cortafuegos"}
    nombres = {}
    for ip, e in sorted(inc.items()):
        if not e["nombre"]:
            errores.append(f"{ip}: falta su nombre en el SIEM")
        else:
            nombres.setdefault(e["nombre"], []).append(ip)
        if e.get("gateway") and e["gateway"] not in fws:
            errores.append(f"{e['nombre'] or ip}: su cortafuegos ({e['gateway']}) está descartado")
    errores += [f"nombre repetido: {n} ({', '.join(ips)})" for n, ips in nombres.items() if len(ips) > 1]
    for ip, e in inc.items():
        for dep in e["depende_de"]:
            if dep not in nombres:
                errores.append(f"{e['nombre'] or ip}: depende de {dep}, que no está entre los equipos incluidos")
    if fws and not any(not inc[f].get("gateway") for f in fws):
        errores.append("ningún cortafuegos es el de borde (sin gateway): la cadena no llega a internet")
    if not errores:
        perfil = perfil_desde_borrador(b)
        errores += [f"perfil: {x}" for x in perfilm.validar(perfil)]
        errores += [f"política: {x}" for x in pe.validar_politica(politica_desde(b, "2026-01-01"), perfil, catalogo)]
        en_cadena = set((perfil.get("topologia") or {}))
        perimetrales = ", ".join(sorted(n for n, t in perfil["topologia"].items()
                                        if t["rol"] == "firewall_perimetral" and "gateway" not in t)) or "ninguno"
        for ip, e in sorted(inc.items()):
            if e["papel"] != "cortafuegos" and e["nombre"] not in en_cadena:
                avisos.append(f"{e['nombre']} está fuera de la cadena de contención: su contención va a los "
                              f"cortafuegos perimetrales ({perimetrales}), sin tocar el equipo")
    for ip, e in sorted(inc.items()):
        n = e["nombre"] or ip
        if e["sin_camino"]:
            avisos.append(f"{n}: sin camino (el traceroute no lo vio): indica su cortafuegos")
        if e["deducido"]:
            avisos.append(f"{n}: su salida hacia el borde está deducida del traceroute: confírmala")
        if e["papel"] == "cortafuegos" and not e.get("huella"):
            avisos.append(f"{n}: sin huella SSH; sus otras interfaces pueden aparecer como equipos sueltos")
    for ip, e in sorted(b["equipos"].items()):
        if not e["incluido"] and e["servicios"]:
            avisos.append(f"{ip} descartado con puertos abiertos ({', '.join(map(str, e['servicios']))})")
    if not b.get("traceroute"):
        avisos.append("el escaneo no trazó caminos (traceroute sin privilegios): los cortafuegos no se deducen; "
                      "repítelo con «sudo mdr descubrir»")
    return {"errores": errores, "avisos": avisos}


def nombres_del_siem(registros, perfil):
    """Nombres de equipo que traen las alertas y que el perfil aún no conoce, por frecuencia."""
    conocidos = set((perfil or {}).get("activos") or {})
    cuenta = {}
    for r in registros or []:
        if r.get("tipo") not in (None, "decision"):
            continue
        a = r.get("activo")
        if isinstance(a, str) and a and a != "desconocido" and a not in conocidos:
            cuenta[a] = cuenta.get(a, 0) + 1
    return [n for n, _ in sorted(cuenta.items(), key=lambda x: (-x[1], x[0]))]
