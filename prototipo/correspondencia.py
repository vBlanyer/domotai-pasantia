"""Registro de correspondencia amenaza -> respuesta recomendada (dato, RNF-03).

Asesor, NO ejecutor: no cambia la accion automatica (`politica.proponer`) ni el filtro del perfil.
Produce la `recomendacion` que ve el analista/agente: una respuesta de un conjunto cerrado
{contener_origen, endurecer_servicio, enrutar, observar} y la accion de catalogo sugerida. Se indexa
por familia y, opcionalmente, por nombre de servicio (que prevalece sobre la familia).
"""
import os, yaml
from prototipo.analisis import CLASES_SIN_AMENAZA

RUTA = os.path.join(os.path.dirname(__file__), "correspondencia.yml")
_REGISTRO = None
# La respuesta mapea a una accion del catalogo por defecto (override con `accion_sugerida` en el dato).
_ACCION_POR_RESPUESTA = {"contener_origen": "BLOQUEAR_IP", "endurecer_servicio": "CERRAR_SERVICIO",
                         "enrutar": None, "observar": None}


def cargar(ruta=RUTA):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def registro():
    global _REGISTRO
    if _REGISTRO is None:
        _REGISTRO = cargar()
    return _REGISTRO


def recomendar(familia, servicio, clase, registro):
    """La recomendacion de respuesta, o None si no hay amenaza (FP/no_soportada) o la familia no tiene
    entrada. `por_servicio` afina y prevalece sobre `por_familia`."""
    if clase in CLASES_SIN_AMENAZA:
        return None
    base = dict((registro.get("por_familia") or {}).get(familia) or {})
    refin = (registro.get("por_servicio") or {}).get(servicio) if servicio else None
    if refin:
        base.update(refin)
    respuesta = base.get("respuesta")
    if not respuesta:
        return None
    return {"respuesta": respuesta,
            "accion_sugerida": base.get("accion_sugerida", _ACCION_POR_RESPUESTA.get(respuesta)),
            "ruta": base.get("ruta"), "servicio": servicio, "nota": base.get("nota", "")}
