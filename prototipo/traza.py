"""Construye el registro de decisión auditable (RF-09)."""

VERSION_BASELINE = "baseline-0"

def justificacion_estructurada(alerta, analisis_out, accion_prop):
    """Justificación estructurada (RF-05): los 4 componentes de la decisión como objeto.
    Puro y tolerante — usa `.get()`, no infiere lo ausente (RNF-07)."""
    return {
        "evidencia": {
            "regla": alerta.get("regla_id"),
            "origen_ip": alerta.get("origen_ip"),
            "activo": alerta.get("activo"),
            "servicio": alerta.get("servicio"),
        },
        "hipotesis": {
            "clase": analisis_out.get("clase"),
            "confianza": analisis_out.get("confianza"),
        },
        "tecnica_mitre": alerta.get("mitre", []) or [],
        "accion_sugerida": accion_prop,
    }

def construir(id_decision, timestamp, alerta, analisis_out, accion_prop, impacto, perfil_nombre, filtro_out, version_perfil):
    return {
        "id_decision": id_decision,
        "timestamp": timestamp,
        "id_alerta": alerta.get("id_alerta"),
        "activo": alerta.get("activo"),
        "clase": analisis_out.get("clase"),
        "prioridad": analisis_out.get("prioridad"),
        "confianza": analisis_out.get("confianza"),
        "justificacion": analisis_out.get("justificacion"),
        "justificacion_estructurada": justificacion_estructurada(alerta, analisis_out, accion_prop),
        "version_justificador": analisis_out.get("version_justificador", "plantilla-0"),  # RF-09/RNF-03
        "pasajes_usados": analisis_out.get("pasajes_usados", []),
        "consulta_rag": analisis_out.get("consulta_rag", ""),                    # Opcion C (RNF-03)
        "recuperacion_agentica": analisis_out.get("recuperacion_agentica", False),
        "accion_propuesta": accion_prop,
        "impacto": impacto,
        "perfil_aplicado": perfil_nombre,
        "resultado_filtro": filtro_out.get("resultado"),
        "accion_final": filtro_out.get("accion_final"),
        "requiere_humano": filtro_out.get("requiere_humano"),
        "version_baseline": VERSION_BASELINE,
        "version_perfil": version_perfil,
    }
