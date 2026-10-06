"""Esquema de `servicios_prestados` enriquecido y retrocompatible, y criticidad por servicio.

Un activo declara servicios como enteros (puerto) o dicts {puerto, servicio?, criticidad?, rol?},
mezclables. Fuente única: `impacto`/`inventario` toman aquí el conjunto de puertos declarados, y
`analisis` la criticidad del servicio atacado. Importa solo `postura` (traducción nombre↔protocolo);
nunca `perfil` ni `impacto`, para no crear ciclos (perfil ya importa impacto).
"""
from prototipo import postura


def _a_entero(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def normalizar(entradas, criticidad_activo):
    """Lista de servicios normalizada a dicts {puerto:int|None, servicio:str|None, criticidad, rol}.
    Un entero hereda la criticidad del activo; un dict sin `criticidad` también."""
    salida = []
    for e in entradas or []:
        if isinstance(e, dict):
            salida.append({"puerto": _a_entero(e.get("puerto")), "servicio": e.get("servicio"),
                           "criticidad": e.get("criticidad") or criticidad_activo, "rol": e.get("rol")})
        else:
            salida.append({"puerto": _a_entero(e), "servicio": None,
                           "criticidad": criticidad_activo, "rol": None})
    return salida


def _activo(perfil, activo):
    return ((perfil or {}).get("activos") or {}).get(activo) or {}


def de_activo(perfil, activo):
    a = _activo(perfil, activo)
    return normalizar(a.get("servicios_prestados"), a.get("criticidad", "media"))


def puertos_declarados(perfil, activo):
    """Conjunto de puertos declarados del activo (enteros), tratando igual enteros y dicts. Sustituye
    los cálculos locales de `impacto` e `inventario` para que declarado se cruce igual en los dos."""
    return {e["puerto"] for e in de_activo(perfil, activo) if e["puerto"] is not None}


def criticidad_servicio(perfil, activo, servicio, hallazgos=None):
    """Criticidad del servicio atacado: por nombre exacto, luego por alias web (http/https/apache…),
    luego por puerto vía los hallazgos del auditor, y si nada empareja, la del activo (fallback).
    Nunca infiere; nunca lanza (RNF-07)."""
    criticidad_base = _activo(perfil, activo).get("criticidad", "media")
    if not servicio or servicio == "desconocido":
        return criticidad_base
    entradas = de_activo(perfil, activo)
    abiertos = [s for s in (((hallazgos or {}).get("nodos") or {}).get(activo) or [])
                if s.get("estado") == "open"]
    # 1) nombre exacto declarado
    for e in entradas:
        if e["servicio"] == servicio:
            return e["criticidad"]
    # 2) por puerto con el nombre EXACTO del auditor: no confunde http(80) con https(443) aunque el
    #    alias web los meta en el mismo bucket (el fallo que corregimos: coger la criticidad del otro).
    puertos_exactos = {s.get("puerto") for s in abiertos if s.get("servicio") == servicio}
    for e in entradas:
        if e["puerto"] is not None and e["puerto"] in puertos_exactos:
            return e["criticidad"]
    # 3) alias de protocolo por nombre declarado (apache/nginx <-> http/https): ultimo recurso.
    prot = postura._protocolos(servicio)
    for e in entradas:
        if e["servicio"] and (postura._protocolos(e["servicio"]) & prot):
            return e["criticidad"]
    # 4) alias por puerto (bucket web): solo cuando no hubo coincidencia exacta de nombre ni puerto.
    puertos_alias = {s.get("puerto") for s in abiertos if postura._protocolos(s.get("servicio")) & prot}
    for e in entradas:
        if e["puerto"] is not None and e["puerto"] in puertos_alias:
            return e["criticidad"]
    return criticidad_base
