"""Postura del activo según el auditor: el contexto que enriquece la alerta antes de clasificar (RF-02).

Pieza de producto (usada por `analisis.enriquecer` y por el etiquetado del dataset). Nunca infiere lo
ausente: un servicio desconocido o un nodo no escaneado dan `None` (caso gris) — RNF-07.
"""

# El SIEM nombra el servicio por el programa que escribió el log (apache, nginx…) y el auditor (nmap)
# por el protocolo del puerto (http, https). Sin esta traducción, un ataque web real contra un activo
# con 80/443 abiertos salía «no expuesto» (caso EXPLOIT del banco). Solo se usa para comparar con el
# auditor: el nombre de la alerta no cambia, porque las órdenes (`service {servicio} stop`) lo usan.
_WEB = frozenset({"http", "https"})
_PROTOCOLOS = {"apache": _WEB, "apache2": _WEB, "httpd": _WEB, "nginx": _WEB, "http": _WEB, "https": _WEB}


def _protocolos(servicio):
    """Los nombres con que el auditor puede listar el servicio de la alerta."""
    return _PROTOCOLOS.get(servicio, frozenset({servicio}))


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
    return {"expuesto": bool(_protocolos(servicio) & servicios), "servicios_abiertos": sorted(servicios)}

def otros_servicios_expuestos(postura, servicio):
    """Otros servicios abiertos del activo, distintos del atacado — contexto que enriquece la
    justificación (RF-02). Vacío si no hay postura, no está expuesto, o no se conocen otros."""
    if not postura or not postura.get("expuesto"):
        return []
    propios = _protocolos(servicio)
    return [s for s in postura.get("servicios_abiertos", []) if s not in propios]

def resumen_otros_expuestos(postura, servicio, tope=4):
    """Los otros servicios expuestos, resumidos para una justificación legible: los primeros `tope`
    y «y N más» si hay más. Cadena vacía si no hay otros (para no meter ruido)."""
    otros = otros_servicios_expuestos(postura, servicio)
    if not otros:
        return ""
    if len(otros) <= tope:
        return ", ".join(otros)
    return ", ".join(otros[:tope]) + f" y {len(otros) - tope} más"
