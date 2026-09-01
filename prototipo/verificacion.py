"""Confirma el efecto de una acción ejecutando el comando de verificación del catálogo."""

def confirmar(orden, catalogo, ejecutor):
    cmd = catalogo[orden["accion_id"]]["verificacion"].format(**orden["params"])
    rc, salida = ejecutor(orden["nodo_ip"], cmd)
    return {"verificado": rc == 0, "evidencia": salida}
