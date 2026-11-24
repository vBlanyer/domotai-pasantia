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
# El nombre es el que trae el SIEM (`resolver_activo`): mayúsculas, puntos (FQDN) y guiones bajos incluidos.
_NOMBRE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}\Z")
_RESERVADOS = {"mdr", "internet"}           # el equipo del MDR y el nodo externo del mapa
_ZONA_GESTION = "Gestión"
_FRAGILES = {9100, 515, 631, 554}
_CAMPOS = {"incluido", "nombre", "zona", "papel", "criticidad", "no_tocar", "depende_de", "funcion", "gateway"}


def _en_rangos(ip, rangos):
    try:
        a = ipaddress.ip_address(ip)
        return any(a in ipaddress.ip_network(r, strict=False) for r in rangos)
    except ValueError:
        return False


def _privada(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_private and not (a.is_loopback or a.is_link_local or a.is_unspecified or a.is_multicast)


def _es_ip(x):
    try:
        ipaddress.IPv4Address(x)
        return True
    except ValueError:
        return False


def _nombre_dep(b, dep):
    """Una dependencia se guarda por IP (la que se eligió en la consola) y sale con el nombre de ese equipo;
    las antiguas, escritas por nombre, valen tal cual."""
    return ((b["equipos"].get(dep) or {}).get("nombre") or None) if dep in b["equipos"] else dep


def _subred(ip):
    return str(ipaddress.ip_network(f"{ip}/24", strict=False))


def borrador_inicial(desc):
    """El borrador que propone el asistente a partir del descubrimiento."""
    rangos = desc.get("rangos") or []
    equipos = {e["ip"]: e for e in desc.get("equipos") or []}
    salida = [s for s in (desc.get("salida") or []) if s]
    saltos_vistos = {s for e in equipos.values() for s in (e.get("saltos") or []) if s}
    # Un salto intermedio privado es un cortafuegos de la red del cliente aunque su segmento no se escaneara
    # (tránsito o gestión): sin él no habría cadena. Su segmento se propone en redes_internas, con aviso.
    gestion = desc.get("gestion")
    fws = sorted({ip for ip in saltos_vistos | set(salida) if ip != gestion and (_en_rangos(ip, rangos) or _privada(ip))})
    fuera = sorted(f for f in fws if not _en_rangos(f, rangos))
    # Interfaces de cada cortafuegos: las IPs con su misma huella SSH. No lo es una IP a la que se llega A TRAVÉS
    # de él, ni una con otros puertos (equipos clonados de una plantilla comparten huella): esas se avisan.
    interfaces, absorbidas, compartida = {}, set(), {}
    huellas_saltos = desc.get("huellas_saltos") or {}
    for f in fws:
        # Un cortafuegos fuera de los rangos no se escaneó: su huella viene aparte y sus puertos no se conocen
        # (entonces basta la huella para reconocer sus otras patas).
        huella = (equipos.get(f) or {}).get("huella_ssh") or huellas_saltos.get(f)
        puertos_f = {p["puerto"] for p in equipos[f].get("puertos") or []} if f in equipos else None
        otras = []
        for ip, e in sorted(equipos.items()):
            if not huella or ip == f or ip in fws or ip in absorbidas or e.get("huella_ssh") != huella:
                continue                  # (una IP ya asignada a otro cortafuegos no es de dos a la vez)
            if f in (e.get("saltos") or []) or (puertos_f is not None
                                                and {p["puerto"] for p in e.get("puertos") or []} != puertos_f):
                compartida[ip] = f
            else:
                otras.append(ip)
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
        ptr = (e.get("dns") or "").split(".")[0]
        base = {"incluido": True, "nombre": ptr if _NOMBRE.match(ptr or "") else "",
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
        if ip in compartida:
            salida_b[ip]["huella_compartida_con"] = compartida[ip]
    for f in fws:                     # un salto que no está en los rangos escaneados no se conoce más allá
        if f not in salida_b:
            salida_b[f] = {"incluido": True, "nombre": "", "criticidad": "media", "no_tocar": False, "depende_de": [],
                           "funcion": "", "servicios": [], "interfaces": interfaces[f], "papel": "cortafuegos", "zona": None,
                           "gateway": gw_fw[f], "deducido": deducido[f], "sin_camino": False,
                           "huella": bool(huellas_saltos.get(f))}
    b = {"version": 1, "basado_en": desc.get("fecha"), "gestion": gestion, "rangos": list(rangos),
         "salida": salida, "traceroute": bool(desc.get("traceroute")), "equipos": salida_b, "fuera_de_rangos": fuera}
    b["redes_internas"] = _redes_internas(b)
    return b


def _redes_internas(b):
    """Los rangos escaneados más el segmento de cada cortafuegos de fuera de ellos que siga INCLUIDO: descartar
    un router del proveedor saca también su red (antes se quedaba en el perfil exportado)."""
    if "rangos" not in b:                       # borrador anterior al 23/11
        return list(b.get("redes_internas") or [])
    eq = b.get("equipos") or {}
    fuera = {_subred(f) for f in b.get("fuera_de_rangos") or []
             if (eq.get(f) or {}).get("incluido") and (eq.get(f) or {}).get("papel") == "cortafuegos"}
    return list(b["rangos"]) + sorted(fuera - set(b["rangos"]))


def _cierra_ciclo(eq, ip, gw):
    """¿Poner `gw` como salida del cortafuegos `ip` cierra un ciclo? (siguiendo la cadena desde `gw`)"""
    visto, actual = set(), gw
    while actual and actual not in visto:
        if actual == ip:
            return True
        visto.add(actual)
        actual = (eq.get(actual) or {}).get("gateway")
    return False


def _normalizar(ip, k, v):
    if k in ("incluido", "no_tocar") and not isinstance(v, bool):
        raise ValueError(f"{ip}.{k}: verdadero o falso")
    if k == "nombre" and not (v == "" or (isinstance(v, str) and _NOMBRE.match(v))):
        raise ValueError(f"{ip}.nombre: letras, números, puntos, guiones y guiones bajos (hasta 63)")
    if k == "zona":
        if v == "":
            return None                                  # vaciar el campo en la consola: sin zona
        if not (v is None or (isinstance(v, str) and 0 < len(v.strip()) <= 40)):
            raise ValueError(f"{ip}.zona: un nombre de hasta 40 caracteres")
        return v.strip() if v is not None else None
    if k == "papel" and v not in PAPELES:
        raise ValueError(f"{ip}.papel: {', '.join(PAPELES)}")
    if k == "criticidad" and v not in CRITICIDADES:
        raise ValueError(f"{ip}.criticidad: {', '.join(CRITICIDADES)}")
    if k == "depende_de" and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
        raise ValueError(f"{ip}.depende_de: una lista de nombres")
    if k == "funcion":
        if not isinstance(v, str):
            raise ValueError(f"{ip}.funcion: texto")
        return re.sub(r"[\x00-\x1f\x7f]", "", v).strip()[:80]
    return v


def _aplicar_uno(eq, ip, k, v):
    """Aplica UN campo sobre `eq` (in situ). ValueError si no vale; entonces no toca nada."""
    v = _normalizar(ip, k, v)
    e = eq[ip]
    if k == "depende_de":
        for x in v:
            if _es_ip(x) and x == ip:
                raise ValueError(f"{ip}.depende_de: un equipo no depende de sí mismo")
            if _es_ip(x) and x not in eq:
                raise ValueError(f"{ip}.depende_de: {x} no es un equipo del borrador")
        v = list(dict.fromkeys(v))                       # sin repetidos, en el orden elegido
    if k == "gateway" and v is not None:
        fws = {x for x, o in eq.items() if o["papel"] == "cortafuegos"}
        if v == ip:
            raise ValueError(f"{ip}.gateway: un equipo no puede salir por sí mismo")
        if v not in fws:
            raise ValueError(f"{ip}.gateway: debe ser un cortafuegos del borrador")
        if e["papel"] == "cortafuegos" and _cierra_ciclo(eq, ip, v):
            raise ValueError(f"{ip}.gateway: {v} ya sale por {ip}; cerraría un ciclo")
    era_fw = e["papel"] == "cortafuegos" and e["incluido"]
    e[k] = v
    if k == "gateway":                       # lo ha indicado el técnico: ni «sin camino» ni «deducido»
        e["sin_camino"] = e["deducido"] = False
    if k == "papel" and v == "cortafuegos":
        e["depende_de"] = []                 # la consola no los enseña para un cortafuegos
    if era_fw and not (e["papel"] == "cortafuegos" and e["incluido"]):
        # Sale de la cadena (descartado o ya no es cortafuegos): lo que salía por él sale por su siguiente salto.
        for otro, o in eq.items():
            if otro != ip and o.get("gateway") == ip:
                o["gateway"] = e.get("gateway") if e.get("gateway") != otro else None


def aplicar_cambios(borrador, cambios):
    """Borrador NUEVO con los cambios del técnico ({ip: {campo: valor}}). ValueError si algo no vale."""
    if not isinstance(cambios, dict):
        raise ValueError("cambios: se esperaba {ip: {campo: valor}}")
    nuevo, rechazados = aplicar_cambios_parcial(borrador, cambios)
    if rechazados:
        raise ValueError(rechazados[0]["error"])
    return nuevo


def aplicar_cambios_parcial(borrador, cambios):
    """(borrador NUEVO, rechazados): aplica cada campo que vale y devuelve los que no, como
    [{ip, campo, error}]. Así un nombre mal escrito no se lleva por delante los cambios buenos que viajaban
    con él (antes el lote entero se rechazaba y la consola seguía enseñándolos como guardados)."""
    if not isinstance(cambios, dict):
        raise ValueError("cambios: se esperaba {ip: {campo: valor}}")
    nuevo = copy.deepcopy(borrador)
    eq, rechazados = nuevo["equipos"], []
    for ip, campos in cambios.items():
        if ip not in eq:
            rechazados.append({"ip": ip, "campo": None, "error": f"{ip}: no es un equipo del borrador"})
            continue
        if not isinstance(campos, dict):
            rechazados.append({"ip": ip, "campo": None, "error": f"{ip}: se esperaba {{campo: valor}}"})
            continue
        for k, v in campos.items():
            if k not in _CAMPOS:
                rechazados.append({"ip": ip, "campo": k, "error": f"{ip}: campos admitidos: {', '.join(sorted(_CAMPOS))}"})
                continue
            try:
                _aplicar_uno(eq, ip, k, v)
            except ValueError as e:
                rechazados.append({"ip": ip, "campo": k, "error": str(e)})
    nuevo["redes_internas"] = _redes_internas(nuevo)
    return nuevo, rechazados


_CONSERVABLES = ("nombre", "zona", "criticidad", "no_tocar", "depende_de", "funcion", "incluido")


def conservar_trabajo(viejo, nuevo):
    """El borrador de un escaneo NUEVO con lo que el técnico ya había escrito para las mismas IPs (nombre, zona,
    criticidad, dependencias…), y el cortafuegos que indicó si el nuevo no lo ve y sigue siendo cortafuegos.
    Antes reescanear borraba todo el trabajo sin avisar."""
    if not viejo or not isinstance(viejo.get("equipos"), dict):
        return nuevo
    b = copy.deepcopy(nuevo)
    eq = b["equipos"]
    fws = {ip for ip, e in eq.items() if e["papel"] == "cortafuegos"}
    for ip, v in viejo["equipos"].items():
        if ip not in eq or not isinstance(v, dict):
            continue
        e = eq[ip]
        for k in _CONSERVABLES:
            if k in v and not (k == "zona" and (v[k] is None or e["papel"] == "cortafuegos")):
                e[k] = copy.deepcopy(v[k])
        if e["papel"] == "cortafuegos":
            e["depende_de"] = []
        e["depende_de"] = [x for x in e["depende_de"] if not _es_ip(x) or (x in eq and x != ip)]   # IPs que siguen
        gw = v.get("gateway")
        if gw in fws and gw != ip and e.get("gateway") is None and not (e["papel"] == "cortafuegos" and _cierra_ciclo(eq, ip, gw)):
            e.update({"gateway": gw, "sin_camino": False, "deducido": False})
    b["redes_internas"] = _redes_internas(b)
    return b


def _ciclos(inc, fws):
    """Ciclos en la cadena de cortafuegos incluidos (cada uno una vez)."""
    vistos, ciclos = set(), []
    for f in sorted(fws):
        camino, actual = [], f
        while actual in fws and actual not in camino and actual not in vistos:
            camino.append(actual)
            actual = inc[actual].get("gateway")
        if actual in camino:
            ciclos.append(camino[camino.index(actual):] + [actual])
        vistos.update(camino)
    return ciclos


def _incluidos(b):
    return {ip: e for ip, e in b["equipos"].items() if e["incluido"]}


def _nombre_de(b, ip):
    return ((b["equipos"].get(ip) or {}).get("nombre")) or None


def perfil_desde_borrador(b):
    """El perfil.yml propuesto: la red, sin reglas de política (van en politica.yml)."""
    inc = _incluidos(b)
    fws = {ip for ip, e in inc.items() if e["papel"] == "cortafuegos"}
    p = perfilm.perfil_minimo(b["gestion"], _redes_internas(b))
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
        deps = [n for n in (_nombre_dep(b, d) for d in e["depende_de"]) if n]
        if deps:
            activo["depende_de"] = deps
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


def nombres_vistos(registros):
    """Los nombres de equipo que han llegado en alertas (decisiones, actividad propia, repeticiones)."""
    vistos = set()
    for r in registros or []:
        if r.get("tipo") not in (None, "decision", "pendiente", "actividad_propia", "actividad_suprimida"):
            continue
        a = r.get("activo") or (r.get("clave") or {}).get("activo")
        if isinstance(a, str) and a and a != "desconocido":
            vistos.add(a)
    return vistos


def validar(b, catalogo, vistos=None):
    """{"errores", "avisos"}: con errores no se exporta. `vistos`: los nombres que ya han llegado en alertas del
    SIEM; con alguno, se avisa de cada equipo cuyo nombre aún no ha llegado (con el parecido, si lo hay)."""
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
    errores += [f"{', '.join(ips)}: «{n}» está reservado (el MDR o el nodo externo del mapa)"
                for n, ips in nombres.items() if n.lower() in _RESERVADOS]
    errores += [f"{e['nombre'] or ip}: la zona «{_ZONA_GESTION}» es la del MDR; usa otro nombre"
                for ip, e in sorted(inc.items()) if e["papel"] != "cortafuegos" and e.get("zona") == _ZONA_GESTION]
    for ip, e in inc.items():
        for dep in e["depende_de"]:
            otro = b["equipos"].get(dep)
            if otro is not None:                          # elegida en la consola: por IP
                if not otro["incluido"]:
                    errores.append(f"{e['nombre'] or ip}: depende de {dep}, que está descartado")
                elif not otro["nombre"]:
                    errores.append(f"{e['nombre'] or ip}: depende de {dep}, que aún no tiene nombre en el SIEM")
            elif dep not in nombres:
                errores.append(f"{e['nombre'] or ip}: depende de {dep}, que no está entre los equipos incluidos")
    for ciclo in _ciclos(inc, fws):
        errores.append(f"ciclo de cortafuegos: {' → '.join(_nombre_de(b, f) or f for f in ciclo)}: "
                       "cambia el de alguno en «Llega por»")
    if fws and not any(not inc[f].get("gateway") for f in fws):
        errores.append("ningún cortafuegos es el de borde (sin gateway): la cadena no llega a internet")
    if not errores:
        from prototipo.servicio import tablero       # lo mismo que mira «mdr validar-perfil»
        perfil = perfil_desde_borrador(b)
        errores += [f"perfil: {x}" for x in perfilm.validar(perfil)]
        errores += [f"perfil: mapa de la red: {x}" for x in tablero.estado_red(perfil, [])["avisos"]]
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
        if e["sin_camino"] and not e.get("gateway"):
            avisos.append(f"{n}: sin camino (el traceroute no lo vio): indica su cortafuegos")
        if e["deducido"]:
            avisos.append(f"{n}: su salida hacia el borde está deducida del traceroute: confírmala")
        if e["papel"] == "cortafuegos" and not e.get("huella"):
            avisos.append(f"{n}: sin huella SSH; sus otras interfaces pueden aparecer como equipos sueltos")
    if vistos:
        import difflib
        libres = sorted(set(vistos) - set(nombres))            # un nombre que ya lleva otro equipo no se sugiere
        for ip, e in sorted(inc.items()):
            n = e["nombre"]
            if n and n not in vistos:
                parecido = difflib.get_close_matches(n, libres, n=1, cutoff=0.75)
                avisos.append(f"«{n}» ({ip}) aún no ha llegado en ninguna alerta del SIEM: comprueba que es el nombre "
                              "con que lo envía" + (f" (¿quizá «{parecido[0]}»?)" if parecido else ""))
    for f in b.get("fuera_de_rangos") or []:
        if f in inc:
            avisos.append(f"{inc[f]['nombre'] or f}: cortafuegos fuera de los rangos escaneados; se propone su red "
                          f"{_subred(f)} en redes_internas. Si es un router del proveedor, descártalo")
    for ip, e in sorted(inc.items()):
        if e.get("huella_compartida_con"):
            avisos.append(f"{e['nombre'] or ip} comparte huella SSH con el cortafuegos {e['huella_compartida_con']} "
                          "(¿equipo clonado?): se deja como equipo aparte; compruébalo")
    for ip, e in sorted(inc.items()):
        if e["papel"] != "cortafuegos" and e["servicios"] == [22]:
            avisos.append(f"{e['nombre'] or ip}: solo se ve el SSH (22). Si presta un servicio en un puerto poco común, "
                          "vuelve a escanear con «Lista propia» incluyéndolo junto a los demás: su postura quedaría incompleta")
    for ip, e in sorted(b["equipos"].items()):
        if not e["incluido"] and e["servicios"]:
            avisos.append(f"{ip} descartado con puertos abiertos ({', '.join(map(str, e['servicios']))})")
    if b.get("traceroute") and not b.get("salida"):
        avisos.append("la salida a internet no se trazó (la dirección de fuera no respondió): el cortafuegos de "
                      "borde está deducido; confírmalo")
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
