"""Construye la orden de acción (mensaje) que el conector consume. Frontera motor↔conector."""
from prototipo.motor import perfil as perfilm
from prototipo.motor import actores

# Respaldo heredado: mapa activo->IP del plano de datos del laboratorio, para perfiles que no
# declaran la IP del activo. La IP se resuelve primero del perfil (`perfil.ip_de`: inventario y
# topología del cliente, V4).
IP_DE_NODO = {
    "objetivo-vuln": "192.168.1.30", "puesto": "192.168.1.10",
    "iot": "192.168.1.20", "borde": "192.168.1.1",
}
_ACCIONES_SOBRE_ORIGEN = {"BLOQUEAR_IP", "MATAR_CONEXION"}
_ACCIONES_SOBRE_CUENTA = {"FORZAR_CAMBIO_PASS"}   # la acción recae sobre el usuario, no la IP ni el servicio
_ACCIONES_SOBRE_NODO = {"AISLAR_NODO"}            # cuarentena: se ejecuta en el cortafuegos de borde, no en el host

def construir(decision, alerta, perfil=None):
    accion = decision.get("accion_final")
    if accion is None:
        return None
    activo = decision.get("activo")
    if accion in _ACCIONES_SOBRE_NODO:
        # Cuarentena REAL en el borde (6ª familia, FIM): objetivo = IP del host (del INVENTARIO, no de
        # la alerta —agent.ip es poco fiable—); ejecutor = su cortafuegos de borde (como
        # BLOQUEAR_IP_FIREWALL). Sin IP del host o sin cortafuegos no hay cuarentena ejecutable -> sin
        # orden (el filtro del perfil ya lo veta; esto es el cinturón del constructor).
        objetivo = perfilm.ip_de(perfil, activo) if perfil else None
        _ejec, ejec_ip = perfilm.ejecutor_aislamiento(perfil, activo) if perfil else (None, None)
        if not objetivo or not ejec_ip:
            return None
        return {
            "decision_id": decision.get("id_decision"), "accion_id": accion,
            "nodo_objetivo": activo,          # el host en cuarentena (lo que lee el operador)
            "nodo_ip": ejec_ip,               # dónde se ejecuta: el cortafuegos de borde
            "params": {"ip_nodo": objetivo},  # a quién corta el reenvío: la IP del host
            "impacto": decision.get("impacto"), "justificacion": decision.get("justificacion"),
        }
    if accion == "LIMITAR_BANDA":
        # DoS (7ª familia): acotar la banda del enlace del host víctima (contención gradual con `tc`).
        # if = la interfaz declarada del nodo en el inventario; rate = política del perfil (defecto
        # sensato). Sin interfaz no hay throttle ejecutable -> sin orden (el filtro ya lo veta).
        interfaz = perfilm.interfaz_de(perfil, activo) if perfil else None
        if not interfaz:
            return None
        rate = ((perfil or {}).get("continuidad") or {}).get("limite_banda") or "1mbit"
        return {
            "decision_id": decision.get("id_decision"), "accion_id": accion,
            "nodo_objetivo": activo,          # el host cuyo enlace se acota (corre en él mismo)
            "nodo_ip": (perfilm.ip_de(perfil, activo) if perfil else None) or IP_DE_NODO.get(activo),
            "params": {"if": interfaz, "rate": rate},
            "impacto": decision.get("impacto"), "justificacion": decision.get("justificacion"),
        }
    if accion == "BLOQUEAR_DESTINO":
        # Exfiltracion/C2 (9ª familia): corta el EGRESO hacia el destino malicioso en el cortafuegos
        # de borde del host que baliza (como BLOQUEAR_IP_FIREWALL, pero por destino -d). El destino sale
        # de la ALERTA (dstip, fiable); el ejecutor del inventario (igual que AISLAR_NODO). Sin destino o
        # sin cortafuegos no hay egreso que cortar -> sin orden (el filtro ya lo veta; cinturon aqui).
        destino = alerta.get("destino_ip")
        _ejec, ejec_ip = perfilm.ejecutor_aislamiento(perfil, activo) if perfil else (None, None)
        # El filtro ya veta un destino no-IPv4; cinturon independiente: no construir `iptables -d`
        # con un destino vacio o no-IPv4 (p. ej. IPv6, que el catalogo no sabe bloquear).
        if not actores.es_ipv4(destino) or not ejec_ip:
            return None
        return {
            "decision_id": decision.get("id_decision"), "accion_id": accion,
            "nodo_objetivo": activo,       # el host interno que baliza (lo que lee el operador)
            "nodo_ip": ejec_ip,            # donde se ejecuta: el cortafuegos de borde
            "params": {"ip": destino},     # a quien se corta el egreso: el destino malicioso
            "impacto": decision.get("impacto"), "justificacion": decision.get("justificacion"),
        }
    if accion in _ACCIONES_SOBRE_ORIGEN:
        params = {"ip": alerta.get("origen_ip")}
    elif accion in _ACCIONES_SOBRE_CUENTA:
        params = {"usuario": alerta.get("usuario")}
    else:
        params = {"servicio": alerta.get("servicio")}
    return {
        "decision_id": decision.get("id_decision"),
        "accion_id": accion,
        "nodo_objetivo": activo,
        "nodo_ip": (perfilm.ip_de(perfil, activo) if perfil else None) or IP_DE_NODO.get(activo),
        "params": params,
        "impacto": decision.get("impacto"),
        "justificacion": decision.get("justificacion"),
    }
