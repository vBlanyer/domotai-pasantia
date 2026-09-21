"""¿Quién es esta IP para el cliente? Resolución de actores desde el perfil (RF-17, RF-19).

Lo que el MDR sabe de una IP lo declara el cliente en su perfil (C3): el canal de gestión
(`ip_gestion`), la topología de contención, el inventario (`activos`), sus redes internas y sus
orígenes legítimos. Nada se adivina: una IP que no aparece en ninguna de esas fuentes es
`desconocido`, y un perfil sin IPs en el inventario resuelve todo a `desconocido` (comportamiento
idéntico al de antes de existir este módulo).
"""
import ipaddress

POLITICA_POR_DEFECTO = "humano_siempre"          # C1: bloquear lo propio exige humano
POLITICAS = ("humano_siempre", "automatica_si_confianza")
TIPOS_CON_POLITICA = ("activo_interno", "dispositivo_red")
_ROL_RED = "firewall_perimetral"


def _actor(tipo, ip, por, nombre=None, funcion=None):
    return {"tipo": tipo, "nombre": nombre, "funcion": funcion, "ip": ip, "por": por}


def _en_redes(ip, redes):
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False                 # no es una IP (p. ej. un nombre): no está en ninguna red
    # Un CIDR mal escrito lanza ValueError: es un error de configuración y debe verse; tratarlo
    # como «fuera de las redes internas» desprotegería esas IPs.
    return any(direccion in ipaddress.ip_network(red, strict=False) for red in redes or [])


def quien_es(ip, perfil):
    """Actor al que afecta bloquear `ip`: {tipo, nombre, funcion, ip, por}, o None si no hay IP.

    Precedencia (la primera que encaja): gestion > dispositivo_red (nodo de `topologia` con rol
    firewall_perimetral) > activo_interno (activo del inventario, otro nodo de `topologia`, IP de
    `redes_internas` u origen legítimo) > desconocido. `por` dice de qué declaración sale."""
    if not ip:
        return None
    perfil = perfil or {}
    if ip == perfil.get("ip_gestion"):
        return _actor("gestion", ip, "ip_gestion")
    activos = perfil.get("activos") or {}
    topologia = perfil.get("topologia") or {}

    def _funcion(nombre):
        return (activos.get(nombre) or {}).get("funcion")

    for nombre, nodo in topologia.items():
        if isinstance(nodo, dict) and nodo.get("ip") == ip and nodo.get("rol") == _ROL_RED:
            return _actor("dispositivo_red", ip, "topologia", nombre, _funcion(nombre))
    for nombre, activo in activos.items():
        if isinstance(activo, dict) and activo.get("ip") == ip:
            return _actor("activo_interno", ip, "inventario", nombre, activo.get("funcion"))
    for nombre, nodo in topologia.items():
        if isinstance(nodo, dict) and nodo.get("ip") == ip:
            return _actor("activo_interno", ip, "topologia", nombre, _funcion(nombre))
    if _en_redes(ip, perfil.get("redes_internas")):
        return _actor("activo_interno", ip, "redes_internas")
    if ip in (perfil.get("origenes_legitimos") or []):
        return _actor("activo_interno", ip, "origenes_legitimos")
    return _actor("desconocido", ip, None)


def politica(perfil, tipo):
    """Política del perfil para bloquear un actor de `tipo` (`continuidad.actores`). Por defecto
    `humano_siempre` (C1). Un valor que no es una política conocida también cae a
    `humano_siempre`: una errata no puede volver automático el bloqueo de lo propio."""
    valor = (((perfil or {}).get("continuidad") or {}).get("actores") or {}).get(tipo)
    return valor if valor in POLITICAS else POLITICA_POR_DEFECTO
