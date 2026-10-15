"""Confirma el efecto de una acción ejecutando el comando de verificación del catálogo."""
from prototipo.conector import _params_seguros, ip_valida

def confirmar(orden, catalogo, ejecutor):
    if not ip_valida(orden.get("nodo_ip")):
        return {"verificado": False, "evidencia": "nodo_ip rechazado: no es una IP valida"}
    if not _params_seguros(orden.get("params", {})):
        return {"verificado": False, "evidencia": "params rechazados: caracteres no permitidos"}
    acc = catalogo[orden["accion_id"]]
    cmd = acc["verificacion"].format(**orden["params"])
    rc, salida = ejecutor(orden["nodo_ip"], cmd)
    # Transitoria (MATAR_CONEXION): la verificación busca la conexión VIVA; rc0 = sigue viva = NO
    # cortada. Se invierte (verificado cuando el grep NO la encuentra). Persistente: rc0 = aplicada.
    transitoria = acc.get("reversion") == "transitoria"
    verificado = (rc != 0) if transitoria else (rc == 0)
    return {"verificado": verificado, "evidencia": salida}
