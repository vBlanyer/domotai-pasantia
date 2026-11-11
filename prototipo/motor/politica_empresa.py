"""La política de respuesta de la empresa (`politica.yml`), en términos de negocio, traducida a las claves
del perfil que lee el motor. El motor no cambia: esto es una capa de traducción y validación, sin E/S.

Plan: documentacion/05-fase5-implementacion-del-prototipo/plan-politica-empresa.md. Precedencia: código
(frenos duros) > politica.yml > consola (solo endurece). Una regla en el perfil y en la política a la vez
es un error, no «gana uno».
"""
import copy

from prototipo.motor import analisis, familias, politica
from prototipo.motor import perfil as perfilm

VALORES = {"sola": "automatica", "si_hay_certeza": "automatica_si_confianza", "con_analista": "humano_siempre"}
_SOLO_DOS = ("si_hay_certeza", "con_analista")          # en familia, zona y equipo (como hoy)
_CLAVES = {
    "politica": None,                                    # cabecera: version, aprobada_por, fecha
    "confianza": {"administradores", "socios_criticos", "sospechar_si_rafaga"},
    "respuesta_automatica": {"certeza_minima", "por_defecto", "si_afecta_a_un_servicio", "solo_observar",
                             "equipos_propios", "externos_desconocidos", "por_tipo_de_ataque", "por_zona",
                             "por_equipo"},
    "nunca_tocar_en_automatico": None,
    "desconocidos_graves": {"revisar_desde_nivel"},
}
_NIVEL = {"por_defecto": "impacto_localizado", "si_afecta_a_un_servicio": "impacto_alcanza_servicio",
          "solo_observar": "impacto_ninguno"}
_DIMENSION = {"por_tipo_de_ataque": "automatizacion_por_familia", "por_zona": "politicas_por_zona",
              "por_equipo": "overrides_por_activo"}


def cabecera(pol):
    """Versión, quién la aprobó y cuándo (`politica:` del fichero), o {}."""
    return dict((pol or {}).get("politica") or {})


def traducir_politica(pol):
    """Las claves del perfil que genera la política; solo las que declara."""
    pol = pol or {}
    out, cont = {}, {}
    conf = pol.get("confianza") or {}
    if "administradores" in conf:
        out["origenes_legitimos"] = list(conf["administradores"] or [])
    if "socios_criticos" in conf:
        out["terceros_confiables"] = list(conf["socios_criticos"] or [])
    if "sospechar_si_rafaga" in conf:
        r = conf["sospechar_si_rafaga"] or {}
        out["rafaga"] = {"umbral": r.get("alertas"), "ventana_s": r.get("en_segundos")}
    ra = pol.get("respuesta_automatica") or {}
    if "certeza_minima" in ra:
        cont["umbral_confianza"] = ra["certeza_minima"]
    for clave, destino in _NIVEL.items():
        if clave in ra:
            cont[destino] = VALORES.get(ra[clave], ra[clave])
    if "equipos_propios" in ra:
        v = VALORES.get(ra["equipos_propios"], ra["equipos_propios"])
        cont["actores"] = {"activo_interno": v, "dispositivo_red": v}
    if "externos_desconocidos" in ra:
        cont["contener_externos_desconocidos"] = VALORES.get(ra["externos_desconocidos"], ra["externos_desconocidos"])
    graves = pol.get("desconocidos_graves") or {}
    if "revisar_desde_nivel" in graves:
        cont["revisar_no_soportada_nivel"] = graves["revisar_desde_nivel"]
    if cont:
        out["continuidad"] = cont
    for clave, destino in _DIMENSION.items():
        if clave in ra:
            out[destino] = {k: {"automatizacion": VALORES.get(v, v)} for k, v in (ra[clave] or {}).items()}
    if "nunca_tocar_en_automatico" in pol:
        out["excepciones"] = [{"activo": e.get("equipo"), "servicio": e.get("servicio"), "regla": "nunca_automatica"}
                              for e in pol["nunca_tocar_en_automatico"] or []]
    return out


def familias_freno_duro(catalogo):
    """Familias cuya acción es `nunca_automatica` en el catálogo: ningún fichero puede automatizarlas."""
    reg = familias.registro()
    frenos = set()
    for fam in reg:
        clase = analisis.clasificar({"familia": fam}, {"postura": {"expuesto": True}}, reg)["clase"]
        accion = politica.ACCION_POR_CLASE.get(clase)
        if accion and (catalogo.get(accion) or {}).get("nunca_automatica"):
            frenos.add(fam)
    return frenos


def _choques(perfil, traducida):
    """Reglas que estarían a la vez en el perfil y en la política."""
    perfil = perfil or {}
    out = []
    for clave, valor in traducida.items():
        if clave in ("continuidad", "rafaga"):
            previo = perfil.get(clave) or {}
            for sub in valor:
                if sub == "actores":
                    out += [f"continuidad.actores.{a}" for a in valor[sub] if a in (previo.get("actores") or {})]
                elif sub in previo:
                    out.append(f"{clave}.{sub}")
        elif clave in perfil:
            out.append(clave)
    return out


def fusionar_perfil_y_politica(perfil, pol):
    """Perfil NUEVO con la política traducida. Sin política, el mismo perfil. ValueError si una regla
    está en los dos ficheros. Los frenos que no se exponen (reversibilidad, plano de gestión) quedan a True."""
    if not pol:
        return perfil
    traducida = traducir_politica(pol)
    choques = _choques(perfil, traducida)
    if choques:
        raise ValueError("reglas en el perfil y en la política a la vez: " + ", ".join(choques))
    out = copy.deepcopy(perfil or {})
    for clave, valor in traducida.items():
        if clave in ("continuidad", "rafaga"):
            out.setdefault(clave, {})
            for sub, v in valor.items():
                if sub == "actores":
                    out[clave].setdefault("actores", {}).update(v)
                else:
                    out[clave][sub] = v
        else:
            out[clave] = valor
    cont = out.setdefault("continuidad", {})
    cont.setdefault("reversibilidad_obligatoria", True)
    cont.setdefault("no_cortar_gestion", True)
    return out


def _entero_positivo(v):
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def validar_politica(pol, perfil, catalogo):
    """Avisos en castellano (vacío = válida). Mira claves, valores, equipos, zonas y familias conocidas,
    direcciones, números, reglas repetidas en el perfil y frenos duros que el fichero intente abrir."""
    if pol is None:
        return []
    if not isinstance(pol, dict):
        return ["la política debe ser un mapa"]
    perfil = perfil or {}
    avisos = []
    for clave, val in pol.items():
        if clave not in _CLAVES:
            avisos.append(f"clave desconocida: {clave}")
            continue
        permitidas = _CLAVES[clave]
        if permitidas and isinstance(val, dict):
            avisos += [f"clave desconocida: {clave}.{k}" for k in val if k not in permitidas]
    conf = pol.get("confianza") or {}
    for ip in conf.get("administradores") or []:
        if not perfilm._ip_ok(str(ip)):
            avisos.append(f"confianza.administradores: no es una IP: {ip}")
    for ip in conf.get("socios_criticos") or []:
        if not (perfilm._ip_ok(str(ip)) or perfilm._cidr_ok(str(ip))):
            avisos.append(f"confianza.socios_criticos: no es una IP ni una red: {ip}")
    if "sospechar_si_rafaga" in conf:
        r = conf["sospechar_si_rafaga"] or {}
        for k in ("alertas", "en_segundos"):
            if not _entero_positivo(r.get(k)):
                avisos.append(f"confianza.sospechar_si_rafaga.{k} debe ser un entero positivo: {r.get(k)!r}")
    ra = pol.get("respuesta_automatica") or {}
    if "certeza_minima" in ra:
        c = ra["certeza_minima"]
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
            avisos.append(f"respuesta_automatica.certeza_minima debe estar entre 0 y 1: {c!r}")
    for clave in list(_NIVEL) + ["equipos_propios", "externos_desconocidos"]:
        if clave in ra and ra[clave] not in VALORES:
            avisos.append(f"respuesta_automatica.{clave}: valor no reconocido ({ra[clave]!r}); "
                          f"usa {', '.join(VALORES)}")
    conocidos = {"por_tipo_de_ataque": set(familias.registro()),
                 "por_zona": set(((perfil.get("red") or {}).get("zonas") or {})),
                 "por_equipo": set(perfil.get("activos") or {})}
    nombre = {"por_tipo_de_ataque": "tipo de ataque", "por_zona": "zona", "por_equipo": "equipo"}
    frenos = familias_freno_duro(catalogo)
    for clave in _DIMENSION:
        for k, v in (ra.get(clave) or {}).items():
            if k not in conocidos[clave]:
                avisos.append(f"respuesta_automatica.{clave}: {nombre[clave]} desconocido: {k}")
            if v not in _SOLO_DOS:
                avisos.append(f"respuesta_automatica.{clave}.{k}: valor no admitido ({v!r}); usa si_hay_certeza o con_analista")
            elif clave == "por_tipo_de_ataque" and k in frenos and v != "con_analista":
                avisos.append(f"respuesta_automatica.por_tipo_de_ataque.{k}: es un freno duro del código; "
                              "solo admite con_analista")
    activos = set(perfil.get("activos") or {})
    for e in pol.get("nunca_tocar_en_automatico") or []:
        if not isinstance(e, dict) or e.get("equipo") not in activos:
            avisos.append(f"nunca_tocar_en_automatico: equipo desconocido: {(e or {}).get('equipo') if isinstance(e, dict) else e}")
        elif not _entero_positivo(e.get("servicio")):
            avisos.append(f"nunca_tocar_en_automatico.{e['equipo']}: el servicio debe ser un puerto: {e.get('servicio')!r}")
    graves = pol.get("desconocidos_graves") or {}
    if "revisar_desde_nivel" in graves and not _entero_positivo(graves["revisar_desde_nivel"]):
        avisos.append(f"desconocidos_graves.revisar_desde_nivel debe ser un entero positivo: {graves['revisar_desde_nivel']!r}")
    avisos += [f"{c}: está en el perfil y en la política; déjala solo en la política"
               for c in _choques(perfil, traducir_politica(pol))]
    return avisos
