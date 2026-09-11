"""Interfaz de análisis (clasificar/justificar) con implementación baseline determinista."""
from prototipo.postura import postura_de, resumen_otros_expuestos

# Clases en las que la decision del motor es "esto no es una amenaza". La consumen el
# justificador (para preguntar por que NO lo es) y el RAG (para recuperar el motivo del
# descarte en vez de fichas sobre tecnicas de ataque).
CLASES_SIN_AMENAZA = ("fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada")

FAMILIAS_ATAQUE = {"acceso_credenciales", "reconocimiento", "servicio_expuesto", "explotacion_conocida"}

_PRIORIDAD_BASE = {
    "vp_acceso_consumado": 4, "vp_intento_acceso": 3, "vp_exposicion_gestion": 2,
    "fp_actividad_legitima": 1, "fp_exposicion_inexistente": 1, "no_soportada": 1,
}

def enriquecer(alerta, hallazgos, perfil):
    activo = alerta.get("activo")
    postura = postura_de(hallazgos, activo, alerta.get("servicio"))
    criticidad = perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")
    # Orígenes de administración declarados por el cliente (RNF-14): un ataque aparente
    # desde uno de ellos es el FP dominante (RF-03, clase fp_actividad_legitima).
    origen_legitimo = alerta.get("origen_ip") in set(perfil.get("origenes_legitimos") or [])
    return {"postura": postura, "criticidad": criticidad, "origen_legitimo": origen_legitimo}

def _priorizar(clase, criticidad):
    base = _PRIORIDAD_BASE.get(clase, 1)
    if criticidad in ("alta", "critica"):
        base = min(4, base + 1)
    return base

def clasificar(alerta, contexto):
    postura = contexto.get("postura")
    if alerta.get("familia") not in FAMILIAS_ATAQUE:
        clase, confianza = "no_soportada", 1.0
    elif contexto.get("origen_legitimo"):       # admin declarado -> FP dominante (RF-03)
        clase, confianza = "fp_actividad_legitima", 1.0
    elif postura is None:                       # gris: el baseline sabe que no sabe
        clase, confianza = "vp_intento_acceso", 0.5
    elif postura.get("expuesto"):
        clase, confianza = "vp_intento_acceso", 1.0
    else:
        clase, confianza = "fp_exposicion_inexistente", 1.0
    return {"clase": clase, "prioridad": _priorizar(clase, contexto.get("criticidad")), "confianza": confianza}

def justificar(alerta, contexto, clase):
    postura = contexto.get("postura")
    if postura is None:
        veredicto = "el auditor no tiene postura del activo (contexto incompleto)"
    elif postura.get("expuesto"):
        veredicto = f"el auditor confirma que {alerta.get('servicio')} está expuesto en {alerta.get('activo')}"
        otros = resumen_otros_expuestos(postura, alerta.get("servicio"))
        if otros:
            veredicto += f" (el activo también expone: {otros})"
    else:
        veredicto = f"el auditor no confirma exposición de {alerta.get('servicio')} en {alerta.get('activo')}"
    mitre = ", ".join(alerta.get("mitre", []) or ["s/téc."])
    return (f"Alerta {alerta.get('regla_id')} (técnica {mitre}) desde {alerta.get('origen_ip')} "
            f"contra {alerta.get('activo')} ({alerta.get('servicio')}). {veredicto}. "
            f"Clasificada como {clase}. [justificación de plantilla — baseline, no modelo]")
