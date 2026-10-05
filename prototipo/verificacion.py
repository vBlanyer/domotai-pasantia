"""Confirma el efecto de una acción ejecutando el comando de verificación del catálogo."""
from prototipo.conector import _params_seguros
from prototipo import catalogo as catm

def confirmar(orden, catalogo, ejecutor):
    if not _params_seguros(orden.get("params", {})):
        return {"verificado": False, "evidencia": "params rechazados: caracteres no permitidos"}
    cmd = catm.campo(catalogo[orden["accion_id"]], "verificacion", orden.get("plataforma")).format(**orden["params"])
    rc, salida = ejecutor(orden["nodo_ip"], cmd)
    return {"verificado": rc == 0, "evidencia": salida}
