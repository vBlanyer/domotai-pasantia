"""Ground truth de priorizacion: prioridad esperada por (activo, etiqueta)."""
import yaml

def cargar_esperada(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def esperada(activo, etiqueta, tabla):
    return tabla.get(activo, {}).get(etiqueta)
