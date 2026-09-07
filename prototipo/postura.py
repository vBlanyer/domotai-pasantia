"""Postura del activo según el auditor: el contexto que enriquece la alerta antes de clasificar (RF-02).

Pieza de producto (usada por `analisis.enriquecer` y por el etiquetado del dataset). Nunca infiere lo
ausente: un servicio desconocido o un nodo no escaneado dan `None` (caso gris) — RNF-07.
"""

def postura_de(hallazgos, activo, servicio):
    # I1: la alerta no identifica el servicio atacado -> caso gris, no FP.
    # Adivinar aquí (asumir "no coincide con nada abierto" = no expuesto)
    # corrompería el ground truth en silencio.
    if not servicio or servicio == "desconocido":
        return None
    nodos = hallazgos.get("nodos", {})
    # I2: un nodo ausente de "nodos" es "no escaneado con éxito" (desconocido
    # → gris), NUNCA "sin servicios abiertos" (FP). auditar.sh omite la clave
    # del nodo cuando el escaneo falla, precisamente para caer en esta rama.
    if activo not in nodos:
        return None  # nodo desconocido → caso gris, decide un humano
    servicios = {s.get("servicio") for s in nodos[activo] if s.get("estado") == "open"}
    return {"expuesto": servicio in servicios, "servicios_abiertos": sorted(servicios)}

def otros_servicios_expuestos(postura, servicio):
    """Otros servicios abiertos del activo, distintos del atacado — contexto que enriquece la
    justificación (RF-02). Vacío si no hay postura, no está expuesto, o no se conocen otros."""
    if not postura or not postura.get("expuesto"):
        return []
    return [s for s in postura.get("servicios_abiertos", []) if s != servicio]

def resumen_otros_expuestos(postura, servicio, tope=4):
    """Los otros servicios expuestos, resumidos para una justificación legible: los primeros `tope`
    y «y N más» si hay más. Cadena vacía si no hay otros (para no meter ruido)."""
    otros = otros_servicios_expuestos(postura, servicio)
    if not otros:
        return ""
    if len(otros) <= tope:
        return ", ".join(otros)
    return ", ".join(otros[:tope]) + f" y {len(otros) - tope} más"
