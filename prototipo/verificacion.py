"""Confirma el efecto de una acción ejecutando el comando de verificación del catálogo."""
from prototipo.conector import _params_seguros, ip_valida

def confirmar(orden, catalogo, ejecutor):
    if not ip_valida(orden.get("nodo_ip")):
        return {"verificado": False, "evidencia": "nodo_ip rechazado: no es una IP valida"}
    if not _params_seguros(orden.get("params", {})):
        return {"verificado": False, "evidencia": "params rechazados: caracteres no permitidos"}
    cmd = catalogo[orden["accion_id"]]["verificacion"].format(**orden["params"])
    rc, salida = ejecutor(orden["nodo_ip"], cmd)
    return {"verificado": rc == 0, "evidencia": salida}
