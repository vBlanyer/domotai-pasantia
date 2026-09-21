"""El perfil de cliente (V3/V4) y el filtro permite/degrada/veta (RNF-14, RF-17/18/19)."""
import yaml
from prototipo import actores, impacto as impactom
from prototipo import catalogo as _cat

UMBRAL_CONFIANZA = 0.7   # default; configurable por perfil en continuidad.umbral_confianza (RF-07). Sin calibrar aún (barrido pendiente)
DEGRADACION = {"BLOQUEAR_PUERTO": "BLOQUEAR_IP"}   # alcanza_servicio -> localizado
_REVERSION_OK = {"definida", "auto", "transitoria"}

def cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def criticidad_de(perfil, activo):
    return perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")

def ruta_de(perfil, rol):
    """Rol logico de ruta (p. ej. 'appsec') -> destino real del cliente. Sin binding, el rol mismo.
    El registro de familias es agnostico; el binding a la cola/equipo del cliente vive en el perfil."""
    if not rol:
        return None
    return perfil.get("rutas", {}).get(rol, rol)

def _res(resultado, accion_final, requiere_humano):
    return {"resultado": resultado, "accion_final": accion_final, "requiere_humano": requiere_humano}

def _umbral(perfil):
    # RF-07: el umbral de escalado es configurable por perfil; 0.7 por defecto.
    return perfil.get("continuidad", {}).get("umbral_confianza", UMBRAL_CONFIANZA)

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
        return confianza >= _umbral(perfil)
    return False

def _filtrar_reglas(perfil, accion_id, params, catalogo, activo, servicio, confianza, nivel):
    """Las reglas de continuidad de siempre (RF-17 a RF-19), aplicadas con el nivel de impacto
    DETERMINADO (`nivel`, nunca por debajo del catálogo: C2)."""
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
    regla = cont.get(f"impacto_{nivel}", "humano_siempre")
    if regla == "automatica":
        return _res("permite", accion_id, False)
    if regla == "automatica_si_confianza":
        if confianza >= _umbral(perfil):
            return _res("permite", accion_id, False)
        return _res("veta", accion_id, True)
    # regla == "humano_siempre" (impacto alcanza_servicio): intentar degradar
    alt = DEGRADACION.get(accion_id)
    if alt is not None:
        if _permite_localizado(perfil, confianza):
            return _res("degrada", alt, False)
        return _res("degrada", alt, True)
    return _res("veta", accion_id, True)

def _aplicar_actor(res, perfil, det):
    """A quién bloquea la acción FINAL (C1, C4). El canal de gestión es veto duro (RF-19): cortarlo
    impide la siguiente respuesta y la verificación. Un activo interno o un dispositivo de red con
    política `humano_siempre` queda retenido para validación humana (el analista puede aprobarlo)."""
    actor = det.get("actor")
    if not res["accion_final"] or not actor:
        return res
    if actor["tipo"] == "gestion":
        return _res("veta", None, True)
    if (actor["tipo"] in actores.TIPOS_CON_POLITICA
            and actores.politica(perfil, actor["tipo"]) == "humano_siempre"):
        return _res("degrada" if res["resultado"] == "degrada" else "veta", res["accion_final"], True)
    return res

def filtrar(perfil, accion_id, params, catalogo, activo, servicio, confianza, hallazgos=None):
    """permite / degrada / veta. El resultado lleva `impacto`: el impacto DETERMINADO de la acción
    final (a quién bloquea y qué servicios detiene, `impacto.determinar`). Quien no lo use sigue
    funcionando igual. La conciencia de actores vive aquí (C5) para que ningún punto de decisión
    —tampoco un salto de la escalada— pueda saltársela."""
    if accion_id is None:
        return _res("sin_accion", None, False)
    if accion_id not in catalogo:
        return _res("veta", None, True)
    det = impactom.determinar(accion_id, params, activo, perfil, catalogo, hallazgos)
    res = _filtrar_reglas(perfil, accion_id, params, catalogo, activo, servicio, confianza, det["nivel"])
    if res["accion_final"] and res["accion_final"] != accion_id:   # degradada: se ejecuta otra acción
        det = impactom.determinar(res["accion_final"], params, activo, perfil, catalogo, hallazgos)
    return {**_aplicar_actor(res, perfil, det), "impacto": det}
