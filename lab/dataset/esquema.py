"""Traducción de una alerta cruda de Wazuh al esquema normalizado del proyecto."""

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
    if g & {"rootcheck", "cis", "ossec"}:
        return "plataforma"
    return "otra"
