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


_INVERSO = {v: k for k, v in VALORES.items()}
_EN_PALABRAS = {"automatica": "se ejecuta sola", "automatica_si_confianza": "se ejecuta sola si hay certeza",
                "humano_siempre": "espera siempre a un analista"}     # sujeto femenino: «la respuesta», «una contención»


def _num(x):
    return f"{x:.2f}".replace(".", ",") if isinstance(x, float) else str(x)


def explicar(perfil, catalogo):
    """La política EFECTIVA del perfil (con o sin politica.yml) contada en frases, en el orden en que
    decide: frenos del código, confianza, automatización por defecto y por capas, intocables."""
    perfil = perfil or {}
    cont = perfil.get("continuidad") or {}
    frases = []
    frenos = sorted(familias_freno_duro(catalogo))
    if frenos:
        frases.append(f"Estos tipos de ataque nunca se contienen solos, lo fija el código: {', '.join(frenos)}.")
    frases.append("El plano de gestión no se corta nunca y solo se ejecutan acciones que se pueden deshacer.")
    if perfil.get("origenes_legitimos"):
        r = perfil.get("rafaga") or {}
        tras = (f", salvo que formen una ráfaga de {r.get('umbral')} alertas en {r.get('ventana_s')} s"
                if r.get("umbral") and r.get("ventana_s") else "")
        frases.append(f"La actividad de {', '.join(map(str, perfil['origenes_legitimos']))} no es un ataque{tras}.")
    if perfil.get("terceros_confiables"):
        frases.append(f"Los socios críticos ({', '.join(map(str, perfil['terceros_confiables']))}) nunca se "
                      "bloquean sin un analista.")
    if "umbral_confianza" in cont:
        frases.append(f"Ninguna respuesta se ejecuta sola con una certeza menor de {_num(cont['umbral_confianza'])}.")
    for clave, que in (("impacto_localizado", "Una respuesta localizada (bloquear un origen)"),
                       ("impacto_alcanza_servicio", "Una respuesta que afecta a un servicio"),
                       ("impacto_ninguno", "Una respuesta que solo observa")):
        if clave in cont:
            frases.append(f"{que} {_EN_PALABRAS.get(cont[clave], cont[clave])}.")
    act = cont.get("actores") or {}
    if act:
        frases.append("Una contención sobre un equipo propio " + _EN_PALABRAS.get(act.get("activo_interno"), "sigue el caso general")
                      + "; sobre un dispositivo de red, " + _EN_PALABRAS.get(act.get("dispositivo_red"), "sigue el caso general") + ".")
    if cont.get("contener_externos_desconocidos"):
        frases.append("Una contención contra un origen externo desconocido "
                      + _EN_PALABRAS.get(cont["contener_externos_desconocidos"], "") + ".")
    for fam, pol in sorted((perfil.get("automatizacion_por_familia") or {}).items()):
        frases.append(f"La respuesta a un ataque de tipo {fam} {_EN_PALABRAS.get((pol or {}).get('automatizacion'), '')}.")
    zonas = (perfil.get("red") or {}).get("zonas") or {}
    for zona, pol in sorted((perfil.get("politicas_por_zona") or {}).items()):
        equipos = ", ".join(zonas.get(zona) or [])
        frases.append(f"En la zona {zona}" + (f" ({equipos})" if equipos else "") + ", una contención "
                      + _EN_PALABRAS.get((pol or {}).get("automatizacion"), "") + ".")
    for eq, pol in sorted((perfil.get("overrides_por_activo") or {}).items()):
        frases.append(f"Sobre {eq}, una contención {_EN_PALABRAS.get((pol or {}).get('automatizacion'), '')}.")
    for e in perfil.get("excepciones") or []:
        if e.get("regla") == "nunca_automatica":
            frases.append(f"El servicio {e.get('servicio')} de {e.get('activo')} no se toca nunca en automático.")
    if cont.get("revisar_no_soportada_nivel"):
        frases.append(f"Una alerta que el MDR no sabe tratar, con nivel {cont['revisar_no_soportada_nivel']} o más, "
                      "pasa a revisión de un analista, sin acción.")
    return frases


def extraer_politica(perfil):
    """Lo inverso de la traducción, para migrar un perfil antiguo: (politica, perfil_sin_politica).
    Lo que no tiene equivalente en el fichero (p. ej. actores distintos entre sí, umbral_largo) se
    queda en el perfil. fusionar_perfil_y_politica(resto, politica) devuelve el perfil de partida."""
    resto = copy.deepcopy(perfil or {})
    pol, conf, ra = {}, {}, {}
    if "origenes_legitimos" in resto:
        conf["administradores"] = resto.pop("origenes_legitimos")
    if "terceros_confiables" in resto:
        conf["socios_criticos"] = resto.pop("terceros_confiables")
    raf = resto.get("rafaga") or {}
    if "umbral" in raf and "ventana_s" in raf:
        conf["sospechar_si_rafaga"] = {"alertas": raf.pop("umbral"), "en_segundos": raf.pop("ventana_s")}
        if not raf:
            resto.pop("rafaga")
    cont = resto.get("continuidad") or {}
    if "umbral_confianza" in cont:
        ra["certeza_minima"] = cont.pop("umbral_confianza")
    for clave, origen in _NIVEL.items():
        if origen in cont and cont[origen] in _INVERSO:
            ra[clave] = _INVERSO[cont.pop(origen)]
    act = cont.get("actores") or {}
    if (set(act) == {"activo_interno", "dispositivo_red"} and act["activo_interno"] == act["dispositivo_red"]
            and act["activo_interno"] in _INVERSO):
        ra["equipos_propios"] = _INVERSO[act["activo_interno"]]
        cont.pop("actores")
    if cont.get("contener_externos_desconocidos") in _INVERSO:
        ra["externos_desconocidos"] = _INVERSO[cont.pop("contener_externos_desconocidos")]
    graves = {}
    if "revisar_no_soportada_nivel" in cont:
        graves["revisar_desde_nivel"] = cont.pop("revisar_no_soportada_nivel")
    for clave, destino in _DIMENSION.items():
        if destino in resto:
            ra[clave] = {k: _INVERSO.get((v or {}).get("automatizacion"), (v or {}).get("automatizacion"))
                         for k, v in resto.pop(destino).items()}
    exc = resto.get("excepciones") or []
    nunca = [e for e in exc if e.get("regla") == "nunca_automatica"]
    if nunca:
        pol["nunca_tocar_en_automatico"] = [{"equipo": e.get("activo"), "servicio": e.get("servicio")} for e in nunca]
        otras = [e for e in exc if e.get("regla") != "nunca_automatica"]
        if otras:
            resto["excepciones"] = otras
        else:
            resto.pop("excepciones")
    if conf:
        pol["confianza"] = conf
    if ra:
        pol["respuesta_automatica"] = ra
    if graves:
        pol["desconocidos_graves"] = graves
    return pol, resto


def propuesta(pol, overlay):
    """La versión siguiente de la política con los cambios de consola (overlay) aplicados, pendiente de
    aprobar. No escribe nada: la consola propone, Seguridad aprueba y el técnico la instala."""
    nueva = copy.deepcopy(pol or {})
    previa = (nueva.get("politica") or {}).get("version")
    ra = nueva.setdefault("respuesta_automatica", {})
    for clave, destino in _DIMENSION.items():
        for k, v in ((overlay or {}).get(destino) or {}).items():
            valor = (v or {}).get("automatizacion")
            if valor in _INVERSO:
                ra.setdefault(clave, {})[k] = _INVERSO[valor]
    if not ra:
        nueva.pop("respuesta_automatica")
    cab = {"version": (previa or 0) + 1, "aprobada_por": "[pendiente de aprobación]"}
    if previa is not None:
        cab["basada_en"] = previa
    return {"politica": cab, **{k: v for k, v in nueva.items() if k != "politica"}}
