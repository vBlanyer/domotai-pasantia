"""El pipeline de decisión: análisis -> política -> perfil -> registro. Puro: sin ficheros ni red
(el CLI por lotes que lo recorre vive en `servicio/triaje_lote`; el daemon, en `servicio/stream`)."""
from prototipo.motor import analisis, politica, perfil as perfilm, correspondencia
from prototipo.servicio import traza

def procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo, id_decision, timestamp,
             justificar_fn=analisis.justificar, registro_correspondencia=None):
    ctx = analisis.enriquecer(alerta, hallazgos, perfil_dict)
    clas = analisis.clasificar(alerta, ctx)
    # justificar_fn puede devolver str (plantilla, legado) o dict con metadata (LLM: version, pasajes).
    res = justificar_fn(alerta, ctx, clas["clase"])
    if isinstance(res, dict):
        just, version_just, pasajes = res.get("texto", ""), res.get("version_justificador", "desconocido"), res.get("pasajes_usados", [])
        consulta_rag, recuperacion_agentica = res.get("consulta_usada", ""), res.get("recuperacion_agentica", False)
        descartada = res.get("llm_descartada")
    else:
        just, version_just, pasajes = res, "plantilla-0", []
        consulta_rag, recuperacion_agentica = "", False
        descartada = None
    accion, params = politica.proponer(clas["clase"], alerta)
    impacto = catalogo[accion]["impacto"] if accion else "ninguno"
    filtro = perfilm.filtrar(perfil_dict, accion, params, catalogo, alerta.get("activo"),
                             alerta.get("servicio"), clas["confianza"], hallazgos=hallazgos)
    # Escalada de un no_soportada GRAVE (opt-in del perfil, RF-13): un desconocido de SEVERIDAD alta no
    # debe quedar solo en el log. Si el perfil fija `continuidad.revisar_no_soportada_nivel` y el nivel
    # Wazuh lo alcanza, se marca para REVISIÓN humana (resultado 'revisar'), SIN acción (no hay nada que
    # contener, no se adivina una). Ausente la clave -> apagado (comportamiento de siempre), así el
    # canónico —medido sin ella— no se mueve. El ruido de plataforma (nivel bajo) sigue sin molestar.
    if clas["clase"] == "no_soportada":
        umbral_rev = (perfil_dict.get("continuidad") or {}).get("revisar_no_soportada_nivel")
        nivel = alerta.get("nivel_wazuh")
        _es_entero = lambda x: isinstance(x, int) and not isinstance(x, bool)
        # Fail-safe: un umbral mal escrito en el YAML (texto/lista) NO debe reventar el triaje con un
        # TypeError en `nivel >= umbral`; se trata como apagado. `perfil.validar` además lo avisa al arrancar.
        if _es_entero(umbral_rev) and _es_entero(nivel) and nivel >= umbral_rev:
            filtro = {**filtro, "resultado": "revisar", "requiere_humano": True}
    ruta = perfilm.ruta_de(perfil_dict, clas.get("ruta"))
    # Recomendacion de respuesta dirigida (asesora, NO cambia accion/filtro): la calcula el registro
    # de correspondencia a partir de la familia y el servicio atacado. El default cachea (registro()).
    reg_corr = registro_correspondencia if registro_correspondencia is not None else correspondencia.registro()
    recomendacion = correspondencia.recomendar(alerta.get("familia"), alerta.get("servicio"),
                                               clas["clase"], reg_corr)
    analisis_out = {**clas, "justificacion": just, "version_justificador": version_just, "pasajes_usados": pasajes,
                    "consulta_rag": consulta_rag, "recuperacion_agentica": recuperacion_agentica, "ruta": ruta,
                    "justificacion_descartada": descartada, "recomendacion": recomendacion,
                    # Señal ASESORA del punto ciego 'low-and-slow' desde un origen de confianza (no
                    # cambia clase/accion/filtro): se calcula con el contexto ya enriquecido.
                    "aviso": analisis.aviso_vigilancia(ctx, clas["clase"])}
    version_perfil = perfil_dict.get("version", "v0")
    return traza.construir(id_decision, timestamp, alerta, analisis_out, accion, impacto, perfil_nombre, filtro,
                            version_perfil=version_perfil, contexto=ctx)

