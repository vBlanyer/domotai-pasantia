"""Inventario operativo: equipos dados de alta desde la consola y el PAPEL de cada equipo (qué acciones
del catálogo admite y sobre qué servicios y cuentas), en una capa encima del perfil del cliente. Mismo
patrón que el overlay de Políticas: el perfil canónico no se toca, la capa se fusiona al cargar y cada
cambio va al registro de auditoría.

Un equipo nuevo nace «pendiente»: aún no tiene usuario ni sudoers en el equipo, así que el motor no lo
ve. Pasa a «activo» cuando el analista fija su clave del host y la prueba de conexión pasa; solo
entonces entra en el perfil vivo (inventario, zona, enlace) y el motor puede contener en él.
"""
import copy
import ipaddress
import os
import re
import tempfile

import yaml

from prototipo.accion import catalogo as catalogom

_NOMBRE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}\Z")
_INTERFAZ = re.compile(r"^[a-z][a-z0-9._-]{0,14}\Z")
CRITICIDADES = ("baja", "media", "alta")
from prototipo.motor.perfil import CUENTAS_DEL_SISTEMA as _CUENTAS_PROHIBIDAS   # nunca en una lista de cuentas
_VACIO = {"equipos": {}}


def cargar(ruta):
    """Inventario saneado ({"equipos": {nombre: {...}}}); un fichero roto o ausente es inventario vacío."""
    try:
        with open(ruta, encoding="utf-8") as f:
            bruto = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError, TypeError):
        return copy.deepcopy(_VACIO)
    equipos = bruto.get("equipos") if isinstance(bruto, dict) else None
    if not isinstance(equipos, dict):
        return copy.deepcopy(_VACIO)
    return {"equipos": {n: e for n, e in equipos.items() if isinstance(n, str) and _NOMBRE.match(n) and isinstance(e, dict)}}


def guardar(ruta, inventario):
    """Escritura atómica (temporal + os.replace), permisos 0600."""
    directorio = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=directorio, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(inventario, f, allow_unicode=True, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _lista(v, que):
    if v is None:
        return []
    if not isinstance(v, list) or len(v) > 20:
        raise ValueError(f"{que}: se esperaba una lista corta")
    out = []
    for x in v:
        x = str(x).strip()
        if not catalogom._VALOR_SEGURO.match(x):
            raise ValueError(f"{que}: valor no válido ({x!r})")
        if x not in out:
            out.append(x)
    return out


def validar_reglas(catalogo, datos):
    """Papel, acciones y listas de un equipo, validados contra el catálogo cerrado."""
    papel = datos.get("papel")
    if papel not in catalogom.PAPELES:
        raise ValueError("papel desconocido")
    acciones = datos.get("acciones")
    acciones = list(catalogom.PAPELES[papel]["acciones"]) if acciones is None else acciones
    if not isinstance(acciones, list) or any(a not in catalogo for a in acciones):
        raise ValueError("acciones: solo acciones del catálogo")
    servicios = _lista(datos.get("servicios"), "servicios")
    cuentas = _lista(datos.get("cuentas"), "cuentas")
    if set(cuentas) & _CUENTAS_PROHIBIDAS:
        raise ValueError("cuentas: no se admiten cuentas del sistema ni la del conector")
    cualquiera = datos.get("cuentas_cualquiera") is True
    return {"papel": papel, "acciones": [a for a in catalogo if a in set(acciones)], "servicios": servicios,
            "cuentas": [] if cualquiera else cuentas, "cuentas_cualquiera": cualquiera}


def _nombres_e_ips(perfil, inventario):
    nombres, ips = set(), set()
    red = (perfil or {}).get("red") or {}
    for fuente in ((perfil or {}).get("activos") or {}, (perfil or {}).get("topologia") or {}, red.get("nodos") or {}):
        for n, v in fuente.items():
            nombres.add(n)
            if isinstance(v, dict) and v.get("ip"):
                ips.add(str(v["ip"]))
    if (perfil or {}).get("ip_gestion"):
        ips.add(str(perfil["ip_gestion"]))
    for n, e in (inventario or {}).get("equipos", {}).items():
        nombres.add(n)
        if e.get("ip"):
            ips.add(str(e["ip"]))
    return nombres, ips


def zonas(perfil):
    return list(((perfil or {}).get("red") or {}).get("zonas") or {})


def validar_alta(perfil, inventario, datos):
    """Datos de inventario de un equipo NUEVO. ValueError con el motivo si algo no vale."""
    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not _NOMBRE.match(nombre):
        raise ValueError("nombre: minúsculas, números y guiones (2 a 31)")
    nombres, ips = _nombres_e_ips(perfil, inventario)
    if nombre in nombres:
        raise ValueError("ya hay un equipo con ese nombre")
    try:
        ip = ipaddress.IPv4Address(str(datos.get("ip") or ""))
    except ValueError:
        raise ValueError("ip: IPv4 no válida")
    if str(ip) in ips:
        raise ValueError("esa IP ya es de otro equipo")
    internas = (perfil or {}).get("redes_internas") or []
    try:
        if internas and not any(ip in ipaddress.ip_network(str(r), strict=False) for r in internas):
            raise ValueError("ip: fuera de las redes internas del perfil")
    except (TypeError, ValueError) as ex:
        if "fuera" in str(ex):
            raise
    zona = datos.get("zona")
    if zona not in zonas(perfil):
        raise ValueError("zona desconocida")
    criticidad = datos.get("criticidad") or "media"
    if criticidad not in CRITICIDADES:
        raise ValueError("criticidad: baja, media o alta")
    activos = set(((perfil or {}).get("activos") or {}))
    depende = datos.get("depende_de") or []
    if not isinstance(depende, list) or any(d not in activos for d in depende):
        raise ValueError("depende_de: solo equipos del inventario")
    funcion = re.sub(r"[\x00-\x1f\x7f]", "", str(datos.get("funcion") or "")).strip()[:80]
    interfaz = datos.get("interfaz") or None
    if interfaz is not None and not _INTERFAZ.match(str(interfaz)):
        raise ValueError("interfaz no válida")
    return {"ip": str(ip), "zona": zona, "funcion": funcion, "criticidad": criticidad,
            "depende_de": list(depende), **({"interfaz": interfaz} if interfaz else {})}


def fusionar(perfil, inventario):
    """Perfil NUEVO con el inventario operativo aplicado (no muta `perfil`):
    - cada equipo nuevo ACTIVO entra en `activos`, en su zona, con el enlace y el cortafuegos de sus
      vecinos de zona (así el mapa y el aislamiento en el borde funcionan igual que para los demás);
    - el papel de cada equipo va a `papeles_equipo` (lo lee el filtro del motor). Un pendiente no entra."""
    out = copy.deepcopy(perfil or {})
    papeles = dict(out.get("papeles_equipo") or {})
    for n, e in sorted((inventario or {}).get("equipos", {}).items()):
        if e.get("nuevo"):
            if e.get("estado") != "activo":
                continue
            out.setdefault("activos", {})[n] = {"ip": e["ip"], "funcion": e.get("funcion") or "",
                                                 "criticidad": e.get("criticidad") or "media",
                                                 "depende_de": list(e.get("depende_de") or []),
                                                 **({"interfaz": e["interfaz"]} if e.get("interfaz") else {})}
            red = out.setdefault("red", {})
            miembros = red.setdefault("zonas", {}).setdefault(e["zona"], [])
            if n not in miembros:
                miembros.append(n)
            enlaces = red.setdefault("enlaces", {})
            vecino = next((m for m in miembros if m != n and m in enlaces), None)
            if vecino:
                enlaces[n] = enlaces[vecino]
            topo = out.get("topologia") or {}
            vt = next((topo[m] for m in miembros if m != n and isinstance(topo.get(m), dict) and topo[m].get("gateway")), None)
            if vt:
                out.setdefault("topologia", {})[n] = {"rol": "host_victima", "ip": e["ip"], "gateway": vt["gateway"]}
        if e.get("papel") in catalogom.PAPELES:
            cualquiera = e.get("cuentas_cualquiera") is True
            papeles[n] = {"papel": e["papel"],
                          "acciones": catalogom.acciones_efectivas(e.get("acciones") or [], e.get("servicios"), e.get("cuentas"), cualquiera),
                          "servicios": list(e.get("servicios") or []), "cuentas": list(e.get("cuentas") or []),
                          "cuentas_cualquiera": cualquiera}
    if papeles:
        out["papeles_equipo"] = papeles
    return out
