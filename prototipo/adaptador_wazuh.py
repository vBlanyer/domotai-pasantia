"""Adaptador de fuente Wazuh: traduce una alerta cruda de Wazuh al esquema normalizado del motor.

Es la pieza específica de fabricante (RNF-06) del módulo de ingesta. El mapeo tolera campos ausentes
con `.get()` y nunca infiere lo que falta (RNF-07); el activo se deriva de los campos del evento, no
del id de agente (RF-16).
"""

FUENTE = "wazuh"

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
    if g & {"authentication_failed", "authentication_failures", "invalid_login"}:
        return "acceso_credenciales"
    if "recon" in g or rid == "5706":
        return "reconocimiento"
    if g & {"telnetd", "telnet"}:
        return "servicio_expuesto"
    if g & {"exploit", "attack"}:
        return "explotacion_conocida"
    if g & {"rootcheck", "cis", "ossec", "sca"}:
        return "plataforma"
    return "otra"

def normalizar_alerta(cruda, campaña):
    rule = cruda.get("rule", {})
    data = cruda.get("data", {})
    return {
        "id_alerta": cruda.get("id"),
        "timestamp": cruda.get("timestamp"),
        "campaña": campaña,
        "fuente": FUENTE,
        "activo": resolver_activo(cruda),
        "servicio": servicio_de(cruda),
        "familia": familia_de(rule),
        "origen_ip": data.get("srcip"),
        "mitre": rule.get("mitre", {}).get("id", []),
        "evento_crudo": cruda.get("full_log"),
        "nivel_wazuh": rule.get("level"),
        "regla_id": rule.get("id"),
    }

def adaptador(campaña=""):
    """Fábrica de adaptador para el núcleo de ingesta: devuelve un `cruda -> dict` con la campaña fijada."""
    return lambda cruda: normalizar_alerta(cruda, campaña)
