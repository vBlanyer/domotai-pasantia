"""Almacén de la copia operativa de políticas de respuesta y su auditoría.

El overlay tiene hasta tres claves (automatizacion_por_familia,
politicas_por_zona, overrides_por_activo), cada una {clave: {"automatizacion": v}}.
"""
import copy
import json
import os
import tempfile
from datetime import datetime, timezone

import yaml

DIMENSIONES = {
    "familia": "automatizacion_por_familia",
    "zona": "politicas_por_zona",
    "activo": "overrides_por_activo",
}


def cargar_overlay(ruta):
    """Devuelve el overlay parseado, o {} si el fichero no existe."""
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def aplicar_cambio(overlay, dimension, clave, valor):
    """Devuelve un overlay nuevo con el cambio; valor=None borra la clave."""
    seccion = DIMENSIONES[dimension]
    nuevo = copy.deepcopy(overlay or {})
    sec = nuevo.setdefault(seccion, {})
    if valor is None:
        sec.pop(clave, None)
        if not sec:
            nuevo.pop(seccion)
    else:
        sec[clave] = {"automatizacion": valor}
    return nuevo


def guardar_overlay(ruta, overlay):
    """Escritura atómica: temporal en el mismo directorio + os.replace."""
    directorio = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=directorio, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(overlay, f, allow_unicode=True, sort_keys=True)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def registrar_auditoria(ruta_log, operador, dimension, clave, antes, despues):
    """Añade una línea JSONL con el cambio y un timestamp UTC ISO-8601."""
    registro = {
        "operador": operador,
        "dimension": dimension,
        "clave": clave,
        "antes": antes,
        "despues": despues,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(ruta_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
