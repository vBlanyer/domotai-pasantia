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


def _canon(ip):
    """Forma canónica de `ip` (str), o None si no es una IP parseable — se compara entonces como
    texto plano (fallback), que es lo que hacía siempre antes de este módulo. Recorta espacios y
    desenvuelve una IPv4 mapeada en IPv6 (`::ffff:a.b.c.d`), para que declarar o recibir la misma
    dirección en distinta notación no la vuelva "otra" IP."""
    if not isinstance(ip, str):
        return None
    try:
        direccion = ipaddress.ip_address(ip.strip())
    except ValueError:
        return None
    mapeada = getattr(direccion, "ipv4_mapped", None)
    return str(mapeada) if mapeada is not None else str(direccion)


def _coincide(entrada, declarado):
    """¿`entrada` y `declarado` son la misma IP? Si ambas son IPs parseables, compara su forma
    canónica; si alguna no lo es (p. ej. un nombre en el perfil, o una entrada mal formada), cae a
    la comparación de texto de siempre — así un perfil con valores que no son IPs sigue
    funcionando igual (RNF-07: no se adivina)."""
    if declarado is None:
        return False
    ca, cd = _canon(entrada), _canon(declarado)
    if ca is not None and cd is not None:
        return ca == cd
    return entrada == declarado


def _en_redes(ip, redes):
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False                 # no es una IP (p. ej. un nombre): no está en ninguna red
    # Un CIDR mal escrito lanza ValueError: es un error de configuración y debe verse; tratarlo
    # como «fuera de las redes internas» desprotegería esas IPs.
    return any(direccion in ipaddress.ip_network(red, strict=False) for red in redes or [])


def ip_de(perfil, nodo):
    """IP de `nodo` declarada en el perfil: la del inventario (`activos`) o, si no la tiene, la de la
    `topologia`. None si el perfil no la declara. Vive aquí (y `perfil.ip_de` la reexporta) porque
    `impacto` la necesita para saber a quién afecta una acción sobre un nodo."""
    activo = ((perfil or {}).get("activos") or {}).get(nodo) or {}
    nodo_top = ((perfil or {}).get("topologia") or {}).get(nodo)
    return activo.get("ip") or (nodo_top.get("ip") if isinstance(nodo_top, dict) else None)


def quien_es(ip, perfil):
    """Actor al que afecta bloquear `ip`: {tipo, nombre, funcion, ip, por}, o None si no hay IP.

    Precedencia (la primera que encaja): gestion > dispositivo_red (nodo de `topologia` con rol
    firewall_perimetral) > activo_interno (activo del inventario, otro nodo de `topologia`, IP de
    `redes_internas` u origen legítimo) > desconocido. `por` dice de qué declaración sale."""
    if not ip:
        return None
    perfil = perfil or {}
    if _coincide(ip, perfil.get("ip_gestion")):
        return _actor("gestion", ip, "ip_gestion")
    activos = perfil.get("activos") or {}
    topologia = perfil.get("topologia") or {}

    def _funcion(nombre):
        return (activos.get(nombre) or {}).get("funcion")

    for nombre, nodo in topologia.items():
        if isinstance(nodo, dict) and _coincide(ip, nodo.get("ip")) and nodo.get("rol") == _ROL_RED:
            return _actor("dispositivo_red", ip, "topologia", nombre, _funcion(nombre))
    for nombre, activo in activos.items():
        if isinstance(activo, dict) and _coincide(ip, activo.get("ip")):
            return _actor("activo_interno", ip, "inventario", nombre, activo.get("funcion"))
    for nombre, nodo in topologia.items():
        if isinstance(nodo, dict) and _coincide(ip, nodo.get("ip")):
            return _actor("activo_interno", ip, "topologia", nombre, _funcion(nombre))
    if _en_redes(ip, perfil.get("redes_internas")):
        return _actor("activo_interno", ip, "redes_internas")
    if any(_coincide(ip, o) for o in perfil.get("origenes_legitimos") or []):
        return _actor("activo_interno", ip, "origenes_legitimos")
    return _actor("desconocido", ip, None)


def politica(perfil, tipo):
    """Política del perfil para bloquear un actor de `tipo` (`continuidad.actores`). Por defecto
    `humano_siempre` (C1). Un valor que no es una política conocida también cae a
    `humano_siempre`: una errata no puede volver automático el bloqueo de lo propio."""
    valor = (((perfil or {}).get("continuidad") or {}).get("actores") or {}).get(tipo)
    return valor if valor in POLITICAS else POLITICA_POR_DEFECTO
