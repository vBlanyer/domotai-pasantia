"""Confirma el efecto de una acción ejecutando el comando de verificación del catálogo."""
from prototipo.accion.conector import _params_seguros, ip_valida, objetivo_presente

def confirmar(orden, catalogo, ejecutor):
    if not ip_valida(orden.get("nodo_ip")):
        return {"verificado": False, "evidencia": "nodo_ip rechazado: no es una IP valida"}
    if not _params_seguros(orden.get("params", {})):
        return {"verificado": False, "evidencia": "params rechazados: caracteres no permitidos"}
    acc = catalogo[orden["accion_id"]]
    cmd = acc["verificacion"].format(**orden["params"])
    rc, salida = ejecutor(orden["nodo_ip"], cmd)
    # Transitoria (MATAR_CONEXION): el listado de verificación (`ss -tunap`) debe CORRER (rc0) y la
    # conexión objetivo NO debe aparecer en la salida. Se mira la SALIDA, no el rc de un pipe a grep:
    # un FALLO del chequeo (ss ausente rc127, SSH caído rc255, timeout rc124) da rc!=0 y falla CERRADO
    # —no se da por cortada una conexión que ni se pudo verificar (FAIL-OPEN de seguridad)—.
    # Persistente: rc0 = el estado deseado está presente = aplicada (un fallo del chequeo ya falla cerrado).
    transitoria = acc.get("reversion") == "transitoria"
    verificado = (rc == 0 and not objetivo_presente(salida, orden["params"])) if transitoria else (rc == 0)
    return {"verificado": verificado, "evidencia": salida}
