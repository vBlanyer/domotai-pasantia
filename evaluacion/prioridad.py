"""Ground truth de priorizacion: prioridad esperada por (activo, etiqueta), con excepciones por familia.

La tabla da una prioridad por equipo y etiqueta; un equipo puede declarar excepciones para una familia
(`familias: {reconocimiento: {VP: 2}}`). Fijada antes de medir (R2, 11/11/2026)."""
import yaml

def cargar_esperada(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def esperada(activo, etiqueta, tabla, familia=None):
    fila = tabla.get(activo) or {}
    excepcion = ((fila.get("familias") or {}).get(familia) or {}).get(etiqueta) if familia else None
    return excepcion if excepcion is not None else fila.get(etiqueta)
