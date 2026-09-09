"""Agente de mitigación (ReAct + Tool Calling acotado). El LLM decide la estrategia y escala de
dispositivo eligiendo acciones de un catálogo CERRADO; el código renderiza el comando, lo valida,
pide aprobación humana y lo ejecuta de forma reversible reutilizando conector.ejecutar_orden.
"""
import json, re
from prototipo import conector, politica, rag

def resolver_topologia(perfil):
    topo = dict(perfil.get("topologia", {}) or {})
    topo["ip_gestion"] = perfil.get("ip_gestion")
    return topo
