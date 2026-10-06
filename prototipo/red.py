"""Mapa de la red del cliente para la vista «Red» del visor. Es solo presentación: la contención y
la escalada leen `topologia`, nunca esto.

Sale del perfil: la sección opcional `red` (nodos que no están en el inventario, enlaces de cada
equipo hacia internet y zonas en el orden en que se dibujan). Sin esa sección, la red se
reconstruye con lo que haya: enlaces = los `gateway` de `topologia` y una única zona «Red». Un
perfil incompleto nunca rompe el mapa: lo que no encaja se avisa y se ignora."""

TIPOS = ("externo", "cortafuegos", "switch", "servidor", "puesto", "gestion")
SIN_UBICAR = "Sin ubicar"


def _lista(v):
    if not v:
        return []
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


def _puerto_declarado(x):
    """Puerto de una entrada de `servicios_prestados` del esquema enriquecido: un dict aporta su
    `puerto`; un entero/cadena se conserva tal cual. Así la vista Red no pierde los servicios en
    forma de dict (misma fuente que servicios.puertos_declarados)."""
    if isinstance(x, dict):
        return x.get("puerto")
    return x if isinstance(x, (int, str)) else None


def _tipo(declarado, rol, funcion, servicios):
    if declarado in TIPOS:
        return declarado
    if rol == "firewall_perimetral":
        return "cortafuegos"
    f = (funcion or "").lower()
    if any(p in f for p in ("soc", "siem", "mdr", "gestion", "auditor")):
        return "gestion"
    return "servidor" if servicios else "puesto"


def red_de(perfil):
    perfil = perfil or {}
    avisos = []
    activos = perfil.get("activos") if isinstance(perfil.get("activos"), dict) else {}
    topologia = {k: v for k, v in (perfil.get("topologia") or {}).items() if isinstance(v, dict)}
    bruta = perfil.get("red")
    if bruta is not None and not isinstance(bruta, dict):
        avisos.append("sección red mal formada (se esperaba un mapa), se ignora")
        bruta = None
    seccion = {}
    for clave, v in (bruta or {}).items():
        if clave in ("nodos", "enlaces", "zonas") and v is not None and not isinstance(v, dict):
            avisos.append(f"red.{clave} mal formada (se esperaba un mapa), se ignora")
        elif clave in ("nodos", "enlaces", "zonas"):
            seccion[clave] = v or {}
    extra = {}
    for nombre, v in (seccion.get("nodos") or {}).items():
        if isinstance(nombre, str):
            extra[nombre] = v
        else:
            avisos.append(f"red.nodos.{nombre}: el nombre de un equipo debe ser texto, se ignora")

    nodos = {}
    for nombre in list(activos) + [n for n in topologia if n not in activos] + [n for n in extra if n not in activos and n not in topologia]:
        a, e = activos.get(nombre) or {}, extra.get(nombre) or {}
        if not isinstance(e, dict):
            avisos.append(f"red.nodos.{nombre}: se esperaba un mapa, se ignora")
            e = {}
        info = {**(a if isinstance(a, dict) else {}), **e}
        rol = (topologia.get(nombre) or {}).get("rol")
        funcion = info.get("funcion") or ("cortafuegos perimetral" if rol == "firewall_perimetral" else None)
        servicios = [p for p in map(_puerto_declarado, _lista(info.get("servicios_prestados"))) if p is not None]
        depende = _lista(info.get("depende_de"))
        if not all(isinstance(d, str) for d in depende):
            avisos.append(f"{nombre}: depende_de solo admite nombres de equipo, se ignora el resto")
            depende = [d for d in depende if isinstance(d, str)]
        nodos[nombre] = {"nombre": nombre, "ip": info.get("ip") or (topologia.get(nombre) or {}).get("ip"),
                         "funcion": funcion, "criticidad": info.get("criticidad"),
                         "servicios_prestados": servicios, "depende_de": depende,
                         "tipo": _tipo(info.get("tipo"), rol, funcion, servicios), "zona": None}

    crudos = (dict(seccion.get("enlaces") or {}) if "enlaces" in seccion
              else {n: t["gateway"] for n, t in topologia.items() if t.get("gateway")})
    enlaces = {}
    for hijo, padre in crudos.items():
        if not isinstance(hijo, str) or not isinstance(padre, str):
            avisos.append(f"enlace {hijo} -> {padre}: se esperaban nombres de equipo, se ignora")
            continue
        if hijo not in nodos or padre not in nodos:
            avisos.append(f"enlace {hijo} -> {padre}: nodo desconocido, se ignora")
            continue
        enlaces[hijo] = padre
    for inicio in list(enlaces):                       # un ciclo haría infinita la disposición
        visto, n = set(), inicio
        while n in enlaces:
            if n in visto:
                avisos.append(f"ciclo en los enlaces en {n}: se corta")
                del enlaces[n]
                break
            visto.add(n)
            n = enlaces[n]

    zonas = []
    nodos_en_zona = {}  # Tracks which zone each node was placed in (first placement wins)
    if "zonas" in seccion:
        for zona, miembros in (seccion.get("zonas") or {}).items():
            zona, validos = str(zona), []
            if not isinstance(miembros, (list, str)) and miembros is not None:
                avisos.append(f"zona {zona}: se esperaba una lista de equipos, se ignoran sus miembros")
                miembros = []
            for m in _lista(miembros):
                if not isinstance(m, str):
                    avisos.append(f"zona {zona}: miembro {m!r} no es un nombre de equipo, se ignora")
                elif m not in nodos:
                    avisos.append(f"zona {zona}: nodo desconocido {m}, se ignora")
                elif m in nodos_en_zona:
                    avisos.append(f"zona {zona}: {m} ya está en la zona {nodos_en_zona[m]}, se ignora")
                else:
                    validos.append(m)
                    nodos_en_zona[m] = zona
            zonas.append([zona, validos])
    else:
        zonas.append(["Red", sorted(n for n, v in nodos.items() if v["tipo"] not in ("cortafuegos", "externo"))])
        for n in zonas[0][1]:
            nodos_en_zona[n] = "Red"
    en_zona = {m for _, ms in zonas for m in ms}
    conectados = set(enlaces) | set(enlaces.values())
    sueltos = sorted(n for n in nodos if n not in en_zona and n not in conectados)
    if sueltos and "zonas" in seccion:
        zonas.append([SIN_UBICAR, sueltos])
        for n in sueltos:
            nodos_en_zona[n] = SIN_UBICAR
    for zona, miembros in zonas:
        for m in miembros:
            nodos[m]["zona"] = zona
    return {"nodos": nodos, "enlaces": enlaces, "zonas": zonas, "avisos": avisos}
