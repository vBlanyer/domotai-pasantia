"""Impacto DETERMINADO de una acción (RF-17): qué servicios toca y a quién bloquea.

El catálogo declara un impacto fijo por tipo de acción (`BLOQUEAR_IP` siempre «localizado», bloquee
a quien bloquee). Aquí se determina a partir del inventario del perfil y de los hallazgos del
auditor: a quién afecta bloquear una IP (`actores.quien_es`), qué servicio detiene cerrar un puerto
y cuántos servicios caen al aislar un nodo (el radio de impacto: una cota superior, porque un
puerto abierto no implica que alguien lo use).

C2: el nivel determinado nunca queda por debajo del catálogo; solo lo mantiene o lo sube. Un
inventario incompleto no puede rebajar una protección.
"""
from prototipo import actores

NIVELES = ("ninguno", "localizado", "alcanza_servicio")
ACCIONES_SOBRE_IP = frozenset({"BLOQUEAR_IP", "BLOQUEAR_IP_FIREWALL", "MATAR_CONEXION"})
ACCIONES_SOBRE_PUERTO = frozenset({"BLOQUEAR_PUERTO", "CERRAR_SERVICIO"})
ACCIONES_SOBRE_NODO = frozenset({"AISLAR_NODO", "REINICIAR_NODO"})
_TOPE_LISTA = 4
_TIPO_LEGIBLE = {"gestion": "canal de gestión del MDR", "dispositivo_red": "dispositivo de red",
                 "activo_interno": "activo interno", "desconocido": "origen no inventariado"}
_POR_LEGIBLE = {"redes_internas": "IP de las redes internas del cliente",
                "origenes_legitimos": "origen legítimo declarado"}


def _max_nivel(a, b):
    return a if NIVELES.index(a) >= NIVELES.index(b) else b


def _activo(perfil, nombre):
    return ((perfil or {}).get("activos") or {}).get(nombre) or {}


def como_puerto(valor):
    """Normaliza un puerto a entero para poder cruzarlo (los hallazgos y servicios_prestados son
    enteros, pero un puerto puede declararse o llegar como texto, p. ej. "80"). Pública: también
    la usa `inventario.reconciliar` para que declarado y abierto se comparen igual en los dos
    sitios (F6)."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return valor


def puertos_abiertos(hallazgos, activo):
    """{puerto: servicio} abiertos del activo según el auditor, o None si el nodo no se escaneó:
    no escaneado no es «sin servicios» (RNF-07)."""
    nodos = (hallazgos or {}).get("nodos")
    if not isinstance(nodos, dict) or activo not in nodos:
        return None
    return {s["puerto"]: s.get("servicio") for s in nodos[activo] or []
            if s.get("estado") == "open" and s.get("puerto") is not None}


def afectados_en_cascada(activo, perfil):
    """Activos que dependen, directa o indirectamente, de `activo` según `depende_de` (cierre
    transitivo inverso), en orden alfabético. Guardia de ciclos: cada activo se visita una vez. Una
    dependencia no declarada da un falso «sin cascada»: es un límite del inventario (Nivel 2)."""
    dependientes = {}
    for nombre, info in ((perfil or {}).get("activos") or {}).items():
        deps = (info or {}).get("depende_de") or []
        if isinstance(deps, str):
            # YAML sin corchetes ("depende_de: a") llega como str, no como lista de un elemento:
            # sin normalizar, iterarla caracter a caracter produce falsos matches (M1).
            deps = [deps]
        for dep in deps:
            dependientes.setdefault(dep, set()).add(nombre)
    vistos, pendientes = set(), [activo]
    while pendientes:
        for d in dependientes.get(pendientes.pop(), ()):
            if d not in vistos and d != activo:
                vistos.add(d)
                pendientes.append(d)
    return sorted(vistos)


def _servicio(puerto, nombre, declarados, abiertos):
    return {"puerto": puerto,
            "servicio": nombre if nombre else (abiertos or {}).get(puerto),
            "declarado": puerto in declarados,
            "abierto": None if abiertos is None else puerto in abiertos}


def _declarados(perfil, activo):
    return {como_puerto(p) for p in _activo(perfil, activo).get("servicios_prestados") or []}


def _servicios_de_puerto(accion_id, params, activo, perfil, hallazgos):
    declarados, abiertos = _declarados(perfil, activo), puertos_abiertos(hallazgos, activo)
    if accion_id == "BLOQUEAR_PUERTO":
        return [_servicio(como_puerto(params.get("puerto")), None, declarados, abiertos)]
    # CERRAR_SERVICIO llega por nombre: el puerto sale de los hallazgos.
    nombre = params.get("servicio")
    puertos = sorted(p for p, s in (abiertos or {}).items() if s == nombre)
    return ([_servicio(p, nombre, declarados, abiertos) for p in puertos]
            or [_servicio(None, nombre, declarados, abiertos)])


def _servicios_del_nodo(activo, perfil, hallazgos):
    declarados, abiertos = _declarados(perfil, activo), puertos_abiertos(hallazgos, activo)
    return [_servicio(p, None, declarados, abiertos) for p in sorted(declarados | set(abiertos or {}))]


def _quien(actor):
    nombre = actor["nombre"] or actor["ip"]
    detalle = actor["funcion"] or _POR_LEGIBLE.get(actor["por"])
    tipo = _TIPO_LEGIBLE[actor["tipo"]]
    return f"{nombre} ({tipo}: {detalle})" if detalle else f"{nombre} ({tipo})"


def _etiqueta(s):
    if s["servicio"] and s["puerto"] is not None:
        return f"{s['servicio']}/{s['puerto']}"
    return str(s["servicio"] or s["puerto"])


def _estado(s):
    abierto = {True: "abierto según el auditor", False: "no abierto según el auditor",
               None: "sin datos del auditor"}[s["abierto"]]
    return f"{'declarado' if s['declarado'] else 'no declarado'} · {abierto}"


def _lista(servicios):
    etiquetas = [_etiqueta(s) for s in servicios]
    if len(etiquetas) <= _TOPE_LISTA:
        return ", ".join(etiquetas)
    return ", ".join(etiquetas[:_TOPE_LISTA]) + f" y {len(etiquetas) - _TOPE_LISTA} más"


def _motivo_base(det, perfil):
    """Una línea para el analista y el daemon: la consecuencia de ejecutar la acción."""
    accion, actor, servicios = det["accion_id"], det["actor"], det["servicios_afectados"]
    if accion in ACCIONES_SOBRE_IP:
        if actor is None:
            return "sin IP que bloquear"
        texto = f"bloquea a {_quien(actor)}"
        if actor["tipo"] != "dispositivo_red":
            # Un dispositivo de red no "detiene 0 servicios": puede cortar todo lo que enruta
            # (la frase que sigue cuando sube de nivel). Decir las dos cosas se contradice.
            texto += " · 0 servicios detenidos"
        if det["nivel"] != det["nivel_catalogo"]:
            texto += (f" · sube de {det['nivel_catalogo']} a {det['nivel']}: "
                      "un dispositivo de red puede cortar todo lo que enruta")
        return texto
    if accion in ACCIONES_SOBRE_PUERTO:
        return "; ".join(f"detendría {_etiqueta(s)} en {det['activo']} ({_estado(s)})" for s in servicios)
    if accion in ACCIONES_SOBRE_NODO:
        criticidad = _activo(perfil, det["activo"]).get("criticidad", "media")
        if not servicios:
            return f"detendría {det['activo']} (criticidad {criticidad}): sin servicios conocidos"
        return (f"detendría {len(servicios)} servicio(s) de {det['activo']} (criticidad {criticidad}): "
                f"{_lista(servicios)}")
    return f"impacto del catálogo: {det['nivel']}"


def _motivo(det, perfil):
    texto = _motivo_base(det, perfil)
    if det.get("activos_afectados_en_cascada"):
        texto += " · en cascada: " + ", ".join(det["activos_afectados_en_cascada"])
    return texto


def determinar(accion_id, params, activo, perfil, catalogo, hallazgos=None):
    """Impacto determinado de `accion_id` sobre `activo`: {nivel, nivel_catalogo,
    servicios_afectados, actor, activo, accion_id, activos_afectados_en_cascada, motivo}."""
    params = params or {}
    nivel_catalogo = (catalogo.get(accion_id) or {}).get("impacto", "ninguno")
    nivel, servicios, actor = nivel_catalogo, [], None
    if accion_id in ACCIONES_SOBRE_IP:
        actor = actores.quien_es(params.get("ip"), perfil)
        if actor and actor["tipo"] == "dispositivo_red":
            # Bloquear un gateway puede cortar todo lo que enruta (con NAT, todo).
            nivel = _max_nivel(nivel, "alcanza_servicio")
    elif accion_id in ACCIONES_SOBRE_PUERTO:
        servicios = _servicios_de_puerto(accion_id, params, activo, perfil, hallazgos)
    elif accion_id in ACCIONES_SOBRE_NODO:
        servicios = _servicios_del_nodo(activo, perfil, hallazgos)
    cascada = (afectados_en_cascada(activo, perfil)
               if accion_id in ACCIONES_SOBRE_PUERTO or accion_id in ACCIONES_SOBRE_NODO else [])
    det = {"nivel": nivel, "nivel_catalogo": nivel_catalogo, "servicios_afectados": servicios,
           "actor": actor, "activo": activo, "accion_id": accion_id, "activos_afectados_en_cascada": cascada}
    det["motivo"] = _motivo(det, perfil)
    return det
