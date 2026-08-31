"""Interfaz de análisis (clasificar/justificar) con implementación baseline determinista."""
from lab.dataset.etiquetar import postura_de

FAMILIAS_ATAQUE = {"acceso_credenciales", "reconocimiento", "servicio_expuesto", "explotacion_conocida"}

_PRIORIDAD_BASE = {
    "vp_acceso_consumado": 4, "vp_intento_acceso": 3, "vp_exposicion_gestion": 2,
    "fp_actividad_legitima": 1, "fp_exposicion_inexistente": 1, "no_soportada": 1,
}

def enriquecer(alerta, hallazgos, perfil):
    activo = alerta.get("activo")
    postura = postura_de(hallazgos, activo, alerta.get("servicio"))
    criticidad = perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")
    return {"postura": postura, "criticidad": criticidad}

def _priorizar(clase, criticidad):
    base = _PRIORIDAD_BASE.get(clase, 1)
    if criticidad in ("alta", "critica"):
        base = min(4, base + 1)
    return base

def clasificar(alerta, contexto):
    postura = contexto.get("postura")
    if alerta.get("familia") not in FAMILIAS_ATAQUE:
        clase, confianza = "no_soportada", 1.0
    elif postura is None:                       # gris: el baseline sabe que no sabe
        clase, confianza = "vp_intento_acceso", 0.5
    elif postura.get("expuesto"):
        clase, confianza = "vp_intento_acceso", 1.0
    else:
        clase, confianza = "fp_exposicion_inexistente", 1.0
    return {"clase": clase, "prioridad": _priorizar(clase, contexto.get("criticidad")), "confianza": confianza}
