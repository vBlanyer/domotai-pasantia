"""Interfaz de análisis (clasificar/justificar) con implementación baseline determinista."""
import re
from prototipo.postura import postura_de, resumen_otros_expuestos
from prototipo import actores, familias, servicios


def _sanear(v, tope=64):
    """Neutraliza un campo de la alerta controlable por el atacante antes de meterlo en texto
    (justificación/prompt del LLM): colapsa espacios y saltos de línea —para que no rompa la
    estructura del prompt ni inyecte una línea falsa— y acota la longitud. NO se usa en la lógica."""
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()[:tope]

# Clases en las que la decision del motor es "esto no es una amenaza". La consumen el
# justificador (para preguntar por que NO lo es) y el RAG (para recuperar el motivo del
# descarte en vez de fichas sobre tecnicas de ataque).
# Las clases que el motor produce hoy (fuente de verdad, p. ej. para el menú de reclasificación).
# Las 2 clases finas del caso de uso (vp_acceso_consumado, vp_exposicion_gestion) no entran: el
# baseline no las emite por falta de etiquetas finas (límite de datos, ver README).
CLASES = ("vp_intento_acceso", "fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada")

CLASES_SIN_AMENAZA = ("fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada")

_PRIORIDAD_BASE = {
    "vp_acceso_consumado": 4, "vp_intento_acceso": 3, "vp_exposicion_gestion": 2,
    "fp_actividad_legitima": 1, "fp_exposicion_inexistente": 1, "no_soportada": 1,
    "amenaza_enrutada": 3,
}

def enriquecer(alerta, hallazgos, perfil):
    activo = alerta.get("activo")
    postura = postura_de(hallazgos, activo, alerta.get("servicio"))
    # Criticidad del SERVICIO atacado (no solo la del equipo): un golpe a un servicio crítico pesa
    # más. Fallback a la del activo cuando el servicio no declara criticidad propia (RF-17).
    criticidad = servicios.criticidad_servicio(perfil, activo, alerta.get("servicio"), hallazgos)
    # Orígenes de administración declarados por el cliente (RNF-14): un ataque aparente
    # desde uno de ellos es el FP dominante (RF-03, clase fp_actividad_legitima).
    origen_legitimo = any(actores._coincide(alerta.get("origen_ip"), o)
                          for o in perfil.get("origenes_legitimos") or [])
    # Rafaga: cuantas alertas del mismo origen en la ventana (la calcula quien alimenta al motor:
    # prototipo/rafaga.py). El umbral es del perfil (RNF-14); sin umbral, la regla no actua.
    return {"postura": postura, "criticidad": criticidad, "origen_legitimo": origen_legitimo,
            "rafaga": alerta.get("rafaga_60s"),
            "umbral_rafaga": (perfil.get("rafaga") or {}).get("umbral")}

def _priorizar(clase, criticidad):
    base = _PRIORIDAD_BASE.get(clase, 1)
    if criticidad in ("alta", "critica"):
        base = min(4, base + 1)
    return base

def clasificar(alerta, contexto, registro=None):
    reg = registro if registro is not None else familias.registro()
    entrada = reg.get(alerta.get("familia"))
    postura = contexto.get("postura")
    umbral = contexto.get("umbral_rafaga")
    en_rafaga = bool(umbral) and (contexto.get("rafaga") or 0) >= umbral
    ruta = None
    if entrada is None:                                 # fuera del registro -> honesto
        clase, confianza = "no_soportada", 1.0
    elif entrada.get("nivel") == "triar_y_enrutar":     # se tria y encamina, no se contiene
        clase, confianza, ruta = "amenaza_enrutada", 1.0, entrada.get("ruta")
    elif contexto.get("origen_legitimo") and en_rafaga:
        clase, confianza = "vp_intento_acceso", 0.6
    elif contexto.get("origen_legitimo"):
        clase, confianza = "fp_actividad_legitima", 1.0
    elif postura is None:
        clase, confianza = "vp_intento_acceso", 0.5
    elif postura.get("expuesto"):
        clase, confianza = "vp_intento_acceso", 1.0
    else:
        clase, confianza = "fp_exposicion_inexistente", 1.0
    salida = {"clase": clase, "prioridad": _priorizar(clase, contexto.get("criticidad")),
              "confianza": confianza}
    if ruta is not None:
        salida["ruta"] = ruta
    return salida

def justificar(alerta, contexto, clase):
    postura = contexto.get("postura")
    # activo/servicio derivan de campos controlables por el atacante (hostname/program_name): se
    # sanean antes de meterlos en texto (saltos de línea y longitud) para que no rompan la estructura
    # del prompt del LLM ni inyecten instrucciones. La decisión NO depende de este texto (RF-05).
    act, svc = _sanear(alerta.get("activo")), _sanear(alerta.get("servicio"))
    if postura is None:
        veredicto = "el auditor no tiene postura del activo (contexto incompleto)"
    elif postura.get("expuesto"):
        veredicto = f"el auditor confirma que {svc} está expuesto en {act}"
        otros = resumen_otros_expuestos(postura, alerta.get("servicio"))
        if otros:
            veredicto += f" (el activo también expone: {otros})"
    else:
        veredicto = f"el auditor no confirma exposición de {svc} en {act}"
    mitre = ", ".join(alerta.get("mitre", []) or ["s/téc."])
    umbral = contexto.get("umbral_rafaga")
    if umbral and (contexto.get("rafaga") or 0) >= umbral:
        veredicto += f"; ráfaga de {contexto['rafaga']} alertas del mismo origen en un minuto"
    return (f"Alerta {alerta.get('regla_id')} (técnica {mitre}) desde {alerta.get('origen_ip')} "
            f"contra {act} ({svc}). {veredicto}. "
            f"Clasificada como {clase}. [justificación de plantilla — baseline, no modelo]")
