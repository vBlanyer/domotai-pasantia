"""Árbol de decisión del etiquetado: asigna el ground truth a cada alerta."""

def postura_de(hallazgos, activo, servicio):
    nodos = hallazgos.get("nodos", {})
    if activo not in nodos:
        return None  # nodo desconocido → caso gris, decide un humano
    servicios = {s.get("servicio") for s in nodos[activo] if s.get("estado") == "open"}
    return {"expuesto": servicio in servicios, "servicios_abiertos": sorted(servicios)}
