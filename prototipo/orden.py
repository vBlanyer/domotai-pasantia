"""Construye la orden de acción (mensaje) que el conector consume. Frontera motor↔conector."""
from prototipo import perfil as perfilm

# Respaldo heredado: mapa activo->IP del plano de datos del laboratorio, para perfiles que no
# declaran la IP del activo. La IP se resuelve primero del perfil (`perfil.ip_de`: inventario y
# topología del cliente, V4).
IP_DE_NODO = {
    "objetivo-vuln": "192.168.1.30", "puesto": "192.168.1.10",
    "iot": "192.168.1.20", "borde": "192.168.1.1",
}
_ACCIONES_SOBRE_ORIGEN = {"BLOQUEAR_IP", "MATAR_CONEXION"}

def construir(decision, alerta, perfil=None):
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
        "nodo_ip": (perfilm.ip_de(perfil, activo) if perfil else None) or IP_DE_NODO.get(activo),
        "params": params,
        "impacto": decision.get("impacto"),
        "justificacion": decision.get("justificacion"),
    }
