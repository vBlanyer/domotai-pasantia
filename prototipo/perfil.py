"""El perfil de cliente (V3/V4) y el filtro permite/degrada/veta (RNF-14, RF-17/18/19)."""
import ipaddress
import yaml
from prototipo import actores, impacto as impactom
from prototipo import catalogo as _cat

UMBRAL_CONFIANZA = 0.7   # default; configurable por perfil en continuidad.umbral_confianza (RF-07). Sin calibrar aún (barrido pendiente)
DEGRADACION = {"BLOQUEAR_PUERTO": "BLOQUEAR_IP"}   # alcanza_servicio -> localizado
_REVERSION_OK = {"definida", "auto", "transitoria"}
_CRITICIDADES = ("baja", "media", "alta", "critica")

def cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def _ip_ok(s):
    return actores._canon(s) is not None

def _cidr_ok(s):
    try:
        ipaddress.ip_network(str(s), strict=False)
        return True
    except ValueError:
        return False

def validar(perfil):
    """Revisa el perfil al cargarlo y devuelve una lista de avisos (vacía = coherente), SIN romper:
    un perfil mal escrito debe verse al arrancar, no fallar en silencio en la primera alerta. No
    cambia ninguna decisión; es un chequeo de cordura (B11)."""
    perfil = perfil or {}
    avisos = []
    activos = perfil.get("activos")
    if activos is not None and not isinstance(activos, dict):
        avisos.append("activos: se esperaba un mapa de equipos")
        activos = {}
    activos = activos or {}
    topologia = perfil.get("topologia")
    if topologia is not None and not isinstance(topologia, dict):
        avisos.append("topologia: se esperaba un mapa")
    if not perfil.get("ip_gestion"):
        avisos.append("no hay ip_gestion declarada: RF-19 no puede proteger el plano de gestión")
    elif not _ip_ok(perfil.get("ip_gestion")):
        avisos.append(f"ip_gestion no es una IP válida: {perfil.get('ip_gestion')!r}")
    for nombre, a in activos.items():
        if not isinstance(a, dict):
            avisos.append(f"activo {nombre}: se esperaba un mapa")
            continue
        if a.get("ip") is not None and not _ip_ok(a.get("ip")):
            avisos.append(f"activo {nombre}: IP no parseable {a.get('ip')!r}")
        dep_de = a.get("depende_de")
        if dep_de is not None and not isinstance(dep_de, (list, tuple)):
            avisos.append(f"activo {nombre}: depende_de debe ser una lista, no {dep_de!r}")
        else:
            for dep in dep_de or []:
                if dep not in activos:
                    avisos.append(f"activo {nombre}: depende_de un activo inexistente ({dep})")
        for sp in a.get("servicios_prestados") or []:
            if isinstance(sp, dict):
                if sp.get("puerto") is None:
                    avisos.append(f"activo {nombre}: servicio sin puerto ({sp!r})")
                c = sp.get("criticidad")
                if c is not None and c not in _CRITICIDADES:
                    avisos.append(f"activo {nombre}: criticidad de servicio no reconocida ({c!r})")
    for clave in ("origenes_legitimos", "terceros_confiables", "redes_internas"):
        v = perfil.get(clave)
        if v is None:
            continue
        if not isinstance(v, (list, tuple)):
            avisos.append(f"{clave}: se esperaba una lista, no {v!r}")
            continue
        for item in v:
            if not (_ip_ok(item) or _cidr_ok(item)):
                avisos.append(f"{clave}: entrada no es IP ni CIDR válido ({item!r})")
    rutas = perfil.get("rutas")
    if rutas is not None and not isinstance(rutas, dict):
        avisos.append("rutas: se esperaba un mapa rol->destino")
    u = (perfil.get("continuidad") or {}).get("umbral_confianza")
    if u is not None and not (isinstance(u, (int, float)) and 0 <= u <= 1):
        avisos.append(f"continuidad.umbral_confianza fuera de [0,1]: {u!r}")
    r = (perfil.get("rafaga") or {}).get("umbral")
    if r is not None and not (isinstance(r, int) and r > 0):
        avisos.append(f"rafaga.umbral debe ser un entero positivo: {r!r}")
    return avisos

def criticidad_de(perfil, activo):
    return perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")

def ip_de(perfil, nodo):
    """IP de ejecución de `nodo` declarada en el perfil (ver `actores.ip_de`). None si el perfil no
    la declara (orden.construir cae entonces al mapa heredado del laboratorio)."""
    return actores.ip_de(perfil, nodo)

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
    # Sin `corta_gestion_si` la acción no corta la gestión: una alerta sin servicio (None) no puede
    # casar con la clave ausente (None), o cualquier acción suya quedaría vetada en duro.
    corta = catalogo.get(accion_id, {}).get("corta_gestion_si")
    return corta is not None and corta == servicio

def _excepcion_nunca_automatica(perfil, activo, params):
    # La excepción del perfil marca un puerto/servicio de un activo como no-automatico.
    puerto = params.get("puerto")
    for ex in perfil.get("excepciones", []) or []:
        if (ex.get("activo") == activo and ex.get("regla") == "nunca_automatica"
                and ex.get("servicio") == puerto):
            return True
    return False

def _permite_nivel(perfil, nivel, confianza):
    # regla impacto_<nivel> del perfil: ¿la deja en automático con esta confianza?
    regla = perfil.get("continuidad", {}).get(f"impacto_{nivel}", "humano_siempre")
    if regla == "automatica":
        return True
    if regla == "automatica_si_confianza":
        return confianza >= _umbral(perfil)
    return False

def _permite_localizado(perfil, confianza):
    # regla impacto_localizado del perfil aplicada a una acción ya localizada
    return _permite_nivel(perfil, "localizado", confianza)

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
    if accion_id in impactom.ACCIONES_SOBRE_IP and not actores.es_ipv4((params or {}).get("ip")):
        # Sin IP de origen (p. ej. una alerta sin srcip) o con una IPv6 no hay a quien bloquear con
        # el catalogo: sin este veto se ejecutaba 'iptables -A INPUT -s None -j DROP' en automatico.
        return {**_res("veta", None, True),
                "impacto": {**det, "motivo": "sin IP de origen IPv4 válida: no hay a quién bloquear"}}
    res = _filtrar_reglas(perfil, accion_id, params, catalogo, activo, servicio, confianza, det["nivel"])
    if res["accion_final"] and res["accion_final"] != accion_id:   # degradada: se ejecuta otra acción
        det = impactom.determinar(res["accion_final"], params, activo, perfil, catalogo, hallazgos)
        # C2: `_filtrar_reglas` decidió con el nivel de la acción PROPUESTA; la acción degradada
        # puede resultar en un nivel MAYOR (p. ej. bloquear IP de un dispositivo de red sube a
        # alcanza_servicio). Si la regla de continuidad para ese nivel final no lo autoriza en
        # automático, la acción sigue ejecutándose (sigue "degrada"), pero retenida para el humano.
        if not _permite_nivel(perfil, det["nivel"], confianza):
            res = {**res, "requiere_humano": True}
    final = _aplicar_actor(res, perfil, det)
    # Tercero externo de confianza (socio crítico): un ataque aparente desde él no se auto-bloquea
    # —cortarlo tiraría un servicio de negocio—, se retiene para un humano (la acción se conserva).
    if (accion_id in impactom.ACCIONES_SOBRE_IP and final.get("accion_final")
            and not final.get("requiere_humano")
            and actores.es_tercero_confiable((params or {}).get("ip"), perfil)):
        final = {**final, "requiere_humano": True}
        det = {**det, "motivo": f"{det.get('motivo') or ''} · origen en terceros_confiables: "
                                "no se bloquea en automático, requiere aprobación".strip()}
    # Postura conservadora OPCIONAL (continuidad.contener_externos_desconocidos: humano_siempre): un
    # externo no inventariado puede ser una IP legítima SUPLANTADA (srcip/XFF forjado) para provocar un
    # auto-bloqueo dañino. Si el perfil lo activa, se retiene para humano. Apagado por defecto -> el
    # comportamiento (y las métricas canónicas) no cambian.
    if (accion_id in impactom.ACCIONES_SOBRE_IP and final.get("accion_final")
            and not final.get("requiere_humano")
            and (det.get("actor") or {}).get("tipo") == "desconocido"
            and perfil.get("continuidad", {}).get("contener_externos_desconocidos") == "humano_siempre"):
        final = {**final, "requiere_humano": True}
        det = {**det, "motivo": f"{det.get('motivo') or ''} · externo desconocido: "
                                "no se bloquea en automático (política del perfil)".strip()}
    return {**final, "impacto": det}
