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
# vp_abuso_cuenta y vp_reconocimiento van al final: el submenú de reclasificación numera por este
# orden, y añadirlas al final no desplaza la numeración de las clases previas (menos fricción para el
# analista). vp_reconocimiento es el MISMO desenlace que vp_intento_acceso para la familia
# 'reconocimiento' (misma amenaza, prioridad y acción): se separa solo para que el justificador lo
# narre como precursor y no como explotación (recomendación #2 del informe), sin mover las cifras.
CLASES = ("vp_intento_acceso", "fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada",
          "vp_abuso_cuenta", "vp_reconocimiento")

CLASES_SIN_AMENAZA = ("fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada")

_PRIORIDAD_BASE = {
    "vp_acceso_consumado": 4, "vp_abuso_cuenta": 4, "vp_intento_acceso": 3, "vp_reconocimiento": 3,
    "vp_exposicion_gestion": 2,
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
    # Ventana LARGA (p. ej. 10 min): la puebla el daemon en vivo (rafaga.Ventana(600)); la evaluación
    # no la calcula, así que allí queda None y la señal de vigilancia no actúa (cifras intactas).
    rc = perfil.get("rafaga") or {}
    return {"postura": postura, "criticidad": criticidad, "origen_legitimo": origen_legitimo,
            "rafaga": alerta.get("rafaga_60s"),
            "umbral_rafaga": rc.get("umbral"),
            "rafaga_larga": alerta.get("rafaga_600s"),
            "umbral_largo": rc.get("umbral_largo")}


def aviso_vigilancia(contexto, clase):
    """Señal ASESORA (no cambia el veredicto): marca para revisión humana el punto ciego del
    'low-and-slow' — una acumulación de alertas desde un origen DE CONFIANZA en una ventana larga
    que la ráfaga de 60 s no llega a ver. No se puede clasificar con fiabilidad (un admin ocupado da
    los mismos recuentos, medido), así que en vez de decidir mal se muestra al analista. Devuelve el
    texto del aviso o None. NO toca clase/prioridad/acción, así que no afecta a las métricas."""
    if clase != "fp_actividad_legitima":            # el desenlace 'origen de confianza, sin acción'
        return None
    umbral_largo = contexto.get("umbral_largo")
    larga = contexto.get("rafaga_larga") or 0
    if not umbral_largo or larga < umbral_largo:     # fail-safe: sin umbral o sin volumen, no actúa
        return None
    umbral, rafaga = contexto.get("umbral_rafaga"), contexto.get("rafaga") or 0
    if umbral and rafaga >= umbral:                  # la ráfaga de 60 s ya disparó -> no hay punto ciego
        return None
    return (f"vigilar: {larga} alertas del mismo origen de confianza en la ventana larga; "
            "volumen inusual que la ráfaga de 60 s no detecta (posible acceso lento, revisar)")

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
    elif entrada.get("clase"):
        # La familia declara su propia clase de respuesta (registro extensible): el evento mismo es la
        # amenaza (sudo, cuenta nueva), no depende de que haya un 'servicio expuesto'. Las 4 familias
        # históricas no declaran 'clase', así que esta rama no las toca (métricas canónicas intactas).
        clase, confianza = entrada["clase"], 1.0
    elif postura is None:
        clase, confianza = "vp_intento_acceso", 0.5
    elif postura.get("expuesto"):
        clase, confianza = "vp_intento_acceso", 1.0
    else:
        clase, confianza = "fp_exposicion_inexistente", 1.0
    # El reconocimiento VP comparte desenlace con vp_intento_acceso, pero se le da clase propia para
    # que el justificador lo explique como precursor (sondeo/mapeo) y no como una explotación en curso
    # (recomendación #2). Se renombra SOLO el desenlace VP: los FP del recon no se tocan, y como
    # vp_reconocimiento sigue siendo vp_ con la misma prioridad base, las cifras canónicas no cambian.
    if clase == "vp_intento_acceso" and alerta.get("familia") == "reconocimiento":
        clase = "vp_reconocimiento"
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
