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
    return [v] if isinstance(v, str) else list(v)


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
    activos = perfil.get("activos") or {}
    topologia = {k: v for k, v in (perfil.get("topologia") or {}).items() if isinstance(v, dict)}
    seccion = perfil.get("red") or {}
    extra = seccion.get("nodos") or {}
    avisos = []

    nodos = {}
    for nombre in list(activos) + [n for n in topologia if n not in activos] + [n for n in extra if n not in activos and n not in topologia]:
        info = {**(activos.get(nombre) or {}), **(extra.get(nombre) or {})}
        rol = (topologia.get(nombre) or {}).get("rol")
        funcion = info.get("funcion") or ("cortafuegos perimetral" if rol == "firewall_perimetral" else None)
        servicios = info.get("servicios_prestados") or []
        nodos[nombre] = {"nombre": nombre, "ip": info.get("ip") or (topologia.get(nombre) or {}).get("ip"),
                         "funcion": funcion, "criticidad": info.get("criticidad"),
                         "servicios_prestados": servicios, "depende_de": _lista(info.get("depende_de")),
                         "tipo": _tipo(info.get("tipo"), rol, funcion, servicios), "zona": None}

    crudos = (dict(seccion.get("enlaces") or {}) if "enlaces" in seccion
              else {n: t["gateway"] for n, t in topologia.items() if t.get("gateway")})
    enlaces = {}
    for hijo, padre in crudos.items():
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
    if "zonas" in seccion:
        for zona, miembros in (seccion.get("zonas") or {}).items():
            validos = []
            for m in _lista(miembros):
                if m in nodos:
                    validos.append(m)
                else:
                    avisos.append(f"zona {zona}: nodo desconocido {m}, se ignora")
            zonas.append([zona, validos])
    else:
        zonas.append(["Red", sorted(n for n, v in nodos.items() if v["tipo"] not in ("cortafuegos", "externo"))])
    en_zona = {m for _, ms in zonas for m in ms}
    conectados = set(enlaces) | set(enlaces.values())
    sueltos = sorted(n for n in nodos if n not in en_zona and n not in conectados)
    if sueltos and "zonas" in seccion:
        zonas.append([SIN_UBICAR, sueltos])
    for zona, miembros in zonas:
        for m in miembros:
            nodos[m]["zona"] = zona
    return {"nodos": nodos, "enlaces": enlaces, "zonas": zonas, "avisos": avisos}
