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

# ---------------------------------------------------------------- salvaguarda --

_DESTRUCTIVO = re.compile(r'(-F|--flush|-X|-Z|\brm\b|\breboot\b|\bshutdown\b|;|\||&&|`|\$\()')

def validar_comando(comando, ip_gestion):
    """Última línea de defensa (RF-19): veta gestión y patrones destructivos/encadenados."""
    if ip_gestion and ip_gestion in comando:
        return (False, "el comando afecta al plano de gestion (RF-19)")
    if _DESTRUCTIVO.search(comando):
        return (False, "patron destructivo o encadenamiento no permitido")
    return (True, "")

# -------------------------------------------------------------------- parser --

_ACCION_RE = re.compile(r'(Action|Final)\s*:\s*(\{.*)', re.DOTALL)

def _primer_json(s):
    inicio = s.find("{")
    if inicio < 0:
        return None
    prof = 0
    for i in range(inicio, len(s)):
        if s[i] == "{":
            prof += 1
        elif s[i] == "}":
            prof -= 1
            if prof == 0:
                try:
                    return json.loads(s[inicio:i + 1])
                except json.JSONDecodeError:
                    return None
    return None

def parsear_accion(texto):
    m = _ACCION_RE.search(texto or "")
    if not m:
        return None
    obj = _primer_json(m.group(2))
    if obj is None:
        return None
    return {"kind": "final" if m.group(1).lower() == "final" else "action", **obj}

def _extraer_thought(texto):
    m = re.search(r'Thought\s*:\s*(.+)', texto or "")
    return m.group(1).strip() if m else ""

# ------------------------------------------------------- herramientas read-only --

_ACCION_POR_ROL = {
    ("bloquear_ip", "host_victima"): "BLOQUEAR_IP",
    ("bloquear_ip", "firewall_perimetral"): "BLOQUEAR_IP_FIREWALL",
}

def herramienta_consultar_topologia(topo):
    dev = {k: v.get("rol") for k, v in topo.items() if isinstance(v, dict) and v.get("rol")}
    return "nodos: " + ", ".join(f"{k}={r}" for k, r in dev.items())

def herramienta_verificar_mitigacion(topo, catalogo, ejecutor, dispositivo, ip):
    nodo = topo.get(dispositivo)
    if not isinstance(nodo, dict):
        return f"Error: dispositivo desconocido '{dispositivo}'"
    accion_id = _ACCION_POR_ROL.get(("bloquear_ip", nodo.get("rol")))
    if accion_id is None:
        return f"Error: sin verificacion para '{dispositivo}'"
    cmd = catalogo[accion_id]["verificacion"].format(ip=ip)
    rc, _ = ejecutor(nodo.get("ip"), cmd)
    return "bloqueado" if rc == 0 else "activo"

def herramienta_consultar_conocimiento(alerta, indice=None, embedder=None, generador=None, k=3):
    """Read-only: consulta el RAG (ATT&CK+D3FEND) para fundamentar la contramedida. Reutiliza
    rag.consultar_conocimiento (Opcion C). Tolerante: sin indice devuelve un aviso, no rompe."""
    if indice is None:
        return "sin indice de conocimiento"
    r = rag.consultar_conocimiento(alerta, indice, embedder, generador=generador, k=k)
    if not r.get("pasajes"):
        return "sin conocimiento recuperado"
    return "conocimiento: " + "; ".join(p.get("titulo", "") for p in r["pasajes"])
