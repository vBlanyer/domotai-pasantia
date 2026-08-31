"""Construye el registro de decisión auditable (RF-09)."""

VERSION_BASELINE = "baseline-0"

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
        "accion_propuesta": accion_prop,
        "impacto": impacto,
        "perfil_aplicado": perfil_nombre,
        "resultado_filtro": filtro_out.get("resultado"),
        "accion_final": filtro_out.get("accion_final"),
        "requiere_humano": filtro_out.get("requiere_humano"),
        "version_baseline": VERSION_BASELINE,
        "version_perfil": version_perfil,
    }
