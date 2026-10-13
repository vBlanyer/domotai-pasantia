"""La regla clasificación -> acción candidata. Determinista; principio de mínimo impacto."""

ACCION_POR_CLASE = {
    "vp_acceso_consumado": "MATAR_CONEXION",
    "vp_intento_acceso": "BLOQUEAR_IP",
    "vp_reconocimiento": "BLOQUEAR_IP",   # mismo desenlace que un intento: se bloquea la IP que sondea
    "vp_abuso_cuenta": "FORZAR_CAMBIO_PASS",
    "vp_exposicion_gestion": "CERRAR_SERVICIO",
    "fp_actividad_legitima": None,
    "fp_exposicion_inexistente": None,
    "no_soportada": None,
    "amenaza_enrutada": None,   # se tria y encamina; sin contencion automatica
}

def proponer(clase, alerta):
    accion = ACCION_POR_CLASE.get(clase)
    if accion is None:
        return (None, {})
    if accion in ("BLOQUEAR_IP", "MATAR_CONEXION"):
        params = {"ip": alerta.get("origen_ip")}
    elif accion == "FORZAR_CAMBIO_PASS":
        params = {"usuario": alerta.get("usuario")}     # se bloquea la CUENTA, no la IP
    else:
        params = {"servicio": alerta.get("servicio")}
    return (accion, params)
