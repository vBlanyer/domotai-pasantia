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
