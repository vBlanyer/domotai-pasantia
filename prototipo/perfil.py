"""El perfil de cliente (V3/V4) y el filtro permite/degrada/veta (RNF-14, RF-17/18/19)."""
import yaml
from prototipo import catalogo as _cat

UMBRAL_CONFIANZA = 0.7                       # recalibrable en la Fase 6
DEGRADACION = {"BLOQUEAR_PUERTO": "BLOQUEAR_IP"}   # alcanza_servicio -> localizado
_REVERSION_OK = {"definida", "auto", "transitoria"}

def cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def criticidad_de(perfil, activo):
    return perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")

def _res(resultado, accion_final, requiere_humano):
    return {"resultado": resultado, "accion_final": accion_final, "requiere_humano": requiere_humano}

def _corta_gestion(catalogo, accion_id, servicio):
    return catalogo.get(accion_id, {}).get("corta_gestion_si") == servicio

def _excepcion_nunca_automatica(perfil, activo, params):
    # La excepción del perfil marca un puerto/servicio de un activo como no-automatico.
    puerto = params.get("puerto")
    for ex in perfil.get("excepciones", []) or []:
        if (ex.get("activo") == activo and ex.get("regla") == "nunca_automatica"
                and ex.get("servicio") == puerto):
            return True
    return False

def _permite_localizado(perfil, confianza):
    # regla impacto_localizado del perfil aplicada a una acción ya localizada
    regla = perfil.get("continuidad", {}).get("impacto_localizado", "humano_siempre")
    if regla == "automatica":
        return True
    if regla == "automatica_si_confianza":
        return confianza >= UMBRAL_CONFIANZA
    return False

def filtrar(perfil, accion_id, params, catalogo, activo, servicio, confianza):
    if accion_id is None:
        return _res("sin_accion", None, False)
    acc = catalogo[accion_id]
    cont = perfil.get("continuidad", {})
    # Precondición dura RF-19: no cortar el plano de gestión.
    if cont.get("no_cortar_gestion") and _corta_gestion(catalogo, accion_id, servicio):
        return _res("veta", None, True)
    # Precondición dura RF-18: reversión definida y verificable.
    if cont.get("reversibilidad_obligatoria") and acc.get("reversion") not in _REVERSION_OK:
        return _res("veta", None, True)
    # Excepción por servicio/activo (más específica que la regla por impacto).
    if _excepcion_nunca_automatica(perfil, activo, params):
        alt = DEGRADACION.get(accion_id)
        if alt is not None:
            return _res("degrada", alt, not _permite_localizado(perfil, confianza))
        return _res("veta", accion_id, True)
    impacto = acc["impacto"]
    regla = cont.get(f"impacto_{impacto}", "humano_siempre")
    if regla == "automatica":
        return _res("permite", accion_id, False)
    if regla == "automatica_si_confianza":
        if confianza >= UMBRAL_CONFIANZA:
            return _res("permite", accion_id, False)
        return _res("veta", accion_id, True)
    # regla == "humano_siempre" (impacto alcanza_servicio): intentar degradar
    alt = DEGRADACION.get(accion_id)
    if alt is not None:
        if _permite_localizado(perfil, confianza):
            return _res("degrada", alt, False)
        return _res("degrada", alt, True)
    return _res("veta", accion_id, True)
