"""Interfaz de análisis (clasificar/justificar) con implementación baseline determinista."""
from lab.dataset.etiquetar import postura_de

def enriquecer(alerta, hallazgos, perfil):
    activo = alerta.get("activo")
    postura = postura_de(hallazgos, activo, alerta.get("servicio"))
    criticidad = perfil.get("activos", {}).get(activo, {}).get("criticidad", "media")
    return {"postura": postura, "criticidad": criticidad}
