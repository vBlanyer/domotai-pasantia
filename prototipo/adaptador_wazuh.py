"""Adaptador de fuente Wazuh: traduce una alerta cruda de Wazuh al esquema normalizado del motor.

Es la pieza específica de fabricante (RNF-06) del módulo de ingesta. El mapeo tolera campos ausentes
con `.get()` y nunca infiere lo que falta (RNF-07); el activo se deriva de los campos del evento, no
del id de agente (RF-16).
"""
import ipaddress

FUENTE = "wazuh"

def _texto(v):
    """str o None. Campos que aguas abajo se usan como clave (origen_ip/activo) o se recortan
    (`timestamp[:19]`) deben ser str o None: un tipo hostil (número, objeto, lista) de una alerta
    controlada por el atacante reventaría el motor FUERA de la barrera de excepciones (DoS). Las
    malformaciones de contenedor (rule/data/predecoder no-dict) siguen reventando AQUÍ, dentro de la
    barrera de `_parsear`, que las descarta: solo coaccionamos los campos escalar que pasan el
    adaptador y explotan después."""
    return v if isinstance(v, str) else None


def _entero(v):
    """int o None (nunca bool). `nivel_wazuh` se compara numéricamente (max/sorted en agrupacion y
    en el orden por severidad): un tipo hostil —o incluso un string— rompería esa comparación fuera
    de la barrera de excepciones."""
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def resolver_activo(cruda):
    # En Containerlab todo entra como agent.id 000: el activo se deduce del
    # hostname que decodifica Wazuh, no del id de agente (RF-16).
    pre = cruda.get("predecoder", {})
    if pre.get("hostname"):
        return pre["hostname"]
    return cruda.get("location", "desconocido")

def servicio_de(cruda):
    grupos = cruda.get("rule", {}).get("groups", [])
    prog = cruda.get("predecoder", {}).get("program_name", "")
    if "sshd" in grupos or prog == "sshd":
        return "ssh"
    if "telnetd" in grupos or "telnet" in grupos or prog == "telnetd":
        return "telnet"
    return prog or "desconocido"

def familia_de(rule):
    g = set(rule.get("groups", []))
    rid = rule.get("id")
    # Escalada de privilegios / manipulacion de cuentas (sudo, alta de cuenta, cambios de cuenta):
    # mas especifico que un fallo de autenticacion, asi que se comprueba primero.
    if g & {"sudo", "adduser", "account_changed"}:
        return "abuso_de_cuenta"
    # Acceso CONSUMADO: login exitoso desde una IP que venia haciendo fuerza bruta (regla compuesta
    # local, grupo 'intrusion'). Se comprueba ANTES del fallo de autenticacion: ya no es un intento,
    # el atacante entro -> cortar su conexion viva. Un login exitoso LEGITIMO no trae 'intrusion'.
    if "intrusion" in g:
        return "acceso_consumado"
    if g & {"authentication_failed", "authentication_failures", "invalid_login"}:
        return "acceso_credenciales"
    if "recon" in g or rid == "5706":
        return "reconocimiento"
    if g & {"telnetd", "telnet"}:
        return "servicio_expuesto"
    # Denegacion de servicio (flood volumetrico / reglas de frecuencia). Se comprueba ANTES de
    # exploit/attack porque un flood suele traer tambien el grupo 'attack'.
    if g & {"dos", "flood"}:
        return "denegacion_servicio"
    if g & {"exploit", "attack"}:
        return "explotacion_conocida"
    # Integridad de ficheros (FIM): un fichero critico cambio. Se comprueba ANTES del cajon 'plataforma'
    # porque las alertas de syscheck suelen traer tambien el grupo 'ossec'.
    if "syscheck" in g:
        return "integridad_fichero"
    if g & {"rootcheck", "cis", "ossec", "sca"}:
        return "plataforma"
    return "otra"

# Grupos de reglas que son telemetria del PROPIO triaje y no alertas del cliente: hoy, las anclas
# de la traza (regla local 100100, grupo 'triaje'). Si entraran como alertas, cada ancla generaria
# una decision, la decision un ancla, y asi sin fin: se midio (14 registros por un solo ataque).
GRUPOS_PROPIOS = {"triaje"}

def es_propia(cruda):
    return bool(set(cruda.get("rule", {}).get("groups", [])) & GRUPOS_PROPIOS)

def _usuario_de(rule, data):
    """Cuenta sobre la que actuaría FORZAR_CAMBIO_PASS, según la técnica. En una ESCALADA (sudo) la
    cuenta que abusa es QUIEN invoca (srcuser), no el objetivo de la escalada (dstuser suele ser root):
    bloquear root dejaría fuera al admin. En un ALTA/CAMBIO de cuenta, la cuenta afectada es la
    creada/modificada (dstuser). `_texto` coacciona tipos hostiles."""
    if "sudo" in set(rule.get("groups", [])):
        return _texto(data.get("srcuser") or data.get("dstuser") or data.get("user"))
    return _texto(data.get("dstuser") or data.get("srcuser") or data.get("user"))

def normalizar_alerta(cruda, campaña):
    if es_propia(cruda):
        return None
    rule = cruda.get("rule", {})
    data = cruda.get("data", {})
    return {
        "id_alerta": cruda.get("id"),
        "timestamp": _texto(cruda.get("timestamp")),
        "campaña": campaña,
        "fuente": FUENTE,
        "activo": _texto(resolver_activo(cruda)),
        "servicio": _texto(servicio_de(cruda)) or "desconocido",
        "familia": familia_de(rule),
        "origen_ip": _ip_origen(data.get("srcip")),
        # La IP del HOST a aislar (familia integridad_fichero, AISLAR_NODO) NO se toma de la alerta:
        # agent.ip es poco fiable (en Containerlab todo entra como agent 000 -> seria la del manager,
        # no la del host vigilado; incoherente con `activo`, que sale de predecoder.hostname, RF-16).
        # Se resuelve del inventario del perfil aguas abajo (orden.construir / perfil.ejecutor_aislamiento),
        # igual que el nodo ejecutor de cualquier otra accion.
        # Cuenta objeto del evento (familia abuso_de_cuenta): la que se bloquearia (FORZAR_CAMBIO_PASS).
        # Consciente de la tecnica (ver _usuario_de); ausente en el resto de familias.
        "usuario": _usuario_de(rule, data),
        "mitre": rule.get("mitre", {}).get("id", []),
        "evento_crudo": cruda.get("full_log"),
        "nivel_wazuh": _entero(rule.get("level")),   # se compara numéricamente (agrupación/severidad)
        "regla_id": _texto(rule.get("id")),           # clave de Counter en la agrupación -> hashable
    }

def _ip_origen(srcip):
    """srcip tal cual (str), salvo una IPv4 mapeada en IPv6 (`::ffff:a.b.c.d`), que se deja en IPv4: es
    la forma que entiende el catalogo (iptables) y la que se compara con el perfil. Un srcip no-str
    (objeto/lista de una alerta hostil) -> None: no es una IP y aguas abajo se usa como clave."""
    if not isinstance(srcip, str):
        return None
    if srcip.lower().startswith("::ffff:"):
        try:
            return str(ipaddress.ip_address(srcip).ipv4_mapped or srcip)
        except ValueError:
            return srcip
    return srcip

def adaptador(campaña=""):
    """Fábrica de adaptador para el núcleo de ingesta: devuelve un `cruda -> dict` con la campaña fijada."""
    return lambda cruda: normalizar_alerta(cruda, campaña)
