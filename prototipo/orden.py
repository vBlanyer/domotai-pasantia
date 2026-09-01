"""Construye la orden de acción (mensaje) que el conector consume. Frontera motor↔conector."""

# Mapa activo->IP del plano de datos (lab). Un despliegue real lo resolvería del inventario (V4).
IP_DE_NODO = {
    "objetivo-vuln": "192.168.1.30", "puesto": "192.168.1.10",
    "iot": "192.168.1.20", "borde": "192.168.1.1",
}
_ACCIONES_SOBRE_ORIGEN = {"BLOQUEAR_IP", "MATAR_CONEXION"}

def construir(decision, alerta):
    accion = decision.get("accion_final")
    if accion is None:
        return None
    activo = decision.get("activo")
    if accion in _ACCIONES_SOBRE_ORIGEN:
        params = {"ip": alerta.get("origen_ip")}
    else:
        params = {"servicio": alerta.get("servicio")}
    return {
        "decision_id": decision.get("id_decision"),
        "accion_id": accion,
        "nodo_objetivo": activo,
        "nodo_ip": IP_DE_NODO.get(activo),
        "params": params,
        "impacto": decision.get("impacto"),
        "justificacion": decision.get("justificacion"),
    }
