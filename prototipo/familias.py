"""Registro de familias de ataque: familia -> {mitre, nivel, ruta}. Extensible, alineado a MITRE.

nivel de respuesta: 'actuar' (contener con el catalogo cerrado) | 'triar_y_enrutar' (clasificar,
priorizar, enriquecer y encaminar, SIN contener). Una familia ausente del registro -> no_soportada.
El registro es dato (RNF-03): mismo fichero, mismo comportamiento."""
import os, yaml

RUTA = os.path.join(os.path.dirname(__file__), "familias.yml")
_REGISTRO = None

def cargar_registro(ruta=RUTA):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def registro():
    global _REGISTRO
    if _REGISTRO is None:
        _REGISTRO = cargar_registro()
    return _REGISTRO
