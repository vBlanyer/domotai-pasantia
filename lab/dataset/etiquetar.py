"""Árbol de decisión del etiquetado: asigna el ground truth a cada alerta."""
from prototipo.postura import postura_de  # noqa: F401  (re-exportación: la lógica vive en el producto)

# Familias dentro del caso de uso. El ground truth aquí es la pregunta amenaza/no-amenaza (VP/FP),
# ORTOGONAL a cómo el producto responde: `explotacion_conocida` es una familia soportada (su VP/FP
# por postura sigue siendo el ground truth correcto), aunque el motor la trate en el nivel
# `triar_y_enrutar` (la encamina en vez de contenerla; ver prototipo/familias.yml). El mapeo de esa
# respuesta a la métrica de detección vive en evaluacion/prediccion.es_amenaza, no aquí.
FAMILIAS_SOPORTADAS = {
    "acceso_credenciales", "reconocimiento", "servicio_expuesto", "explotacion_conocida",
}

def _ips_auditor(ficha):
    return set((ficha.get("auditor") or {}).get("ips", []))

def _ips_legitimas(ficha):
    return set((ficha.get("legitimos") or {}).get("ips", []))

def _con(registro, etiqueta, por, postura):
    r = dict(registro)
    r["etiqueta"] = etiqueta
    r["etiqueta_por"] = por
    r["postura_activo"] = postura
    r["particion"] = None  # la puebla Task 7 desde particion.yml
    return r

def _verdad_declarada(registro, ficha):
    """Etiqueta que la campana declara para un origen en una ventana temporal, o None.

    Es la verdad del EXPERIMENTO ('esto lo lance yo como ataque desde la IP del admin'), no la de
    la heuristica. Sin ella, las etiquetas las generan las mismas senales que usa el clasificador
    determinista (origen declarado, postura), y un modelo entrenado solo podria copiarlas."""
    for v in ficha.get("verdad") or []:
        if (registro.get("origen_ip") == v.get("origen")
                and v.get("desde", "") <= (registro.get("timestamp") or "") <= v.get("hasta", "~")):
            return v.get("etiqueta")
    return None

def etiquetar(registro, hallazgos, ficha, resoluciones):
    # 1. ¿Actividad de nuestro propio auditor?
    if registro.get("origen_ip") in _ips_auditor(ficha):
        return _con(registro, "PROPIA", "regla", None)
    # 1b. ¿La campana declara la verdad de este escenario? Manda sobre las reglas de abajo, y solo
    #     dentro del caso de uso: fuera de el, 'no_soportada' sigue siendo la etiqueta correcta.
    declarada = _verdad_declarada(registro, ficha)
    if declarada and registro.get("familia") in FAMILIAS_SOPORTADAS:
        return _con(registro, declarada, "campaña", postura_de(hallazgos, registro.get("activo"), registro.get("servicio")))
    # 2. ¿Dentro del caso de uso acotado?
    if registro.get("familia") not in FAMILIAS_SOPORTADAS:
        return _con(registro, "no_soportada", "regla", None)
    # 2b. ¿Origen administrativo legítimo declarado? -> falso positivo.
    # Es la misma señal que un ataque sobre un servicio expuesto; lo que la
    # separa es que el origen es administración normal (FP dominante del dominio).
    if registro.get("origen_ip") in _ips_legitimas(ficha):
        return _con(registro, "FP", "regla", None)
    # 3. ¿El servicio atacado existe en el nodo?
    postura = postura_de(hallazgos, registro.get("activo"), registro.get("servicio"))
    if postura is None:  # caso gris
        r = resoluciones.get(registro.get("id_alerta"))
        if r:
            return _con(registro, r, "humano", None)
        return _con(registro, "PENDIENTE", "regla", None)
    etq = "VP" if postura["expuesto"] else "FP"
    return _con(registro, etq, "regla", postura)
