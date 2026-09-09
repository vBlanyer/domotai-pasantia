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

# ------------------------------------------------------ herramienta mutante --

def _aprobar(dispositivo, nodo_ip, accion_id, ip, leer, escribir):
    escribir(f"── Validación humana ── {accion_id} en {dispositivo} ({nodo_ip}) contra {ip}")
    return leer("¿aprobar la ejecución? [s/N] ").strip().lower().startswith("s")

def herramienta_ejecutar_comando(topo, catalogo, ejecutor, dispositivo, accion, ip, ip_gestion,
                                 decision_id, timestamp, autonomo, leer, escribir):
    """Única herramienta que muta: renderiza del catálogo (RF-15) -> valida (RF-19) -> aprobación
    humana (RF-08, salvo autonomo) -> conector.ejecutar_orden -> registra reversión (RF-18)."""
    nodo = topo.get(dispositivo)
    if not isinstance(nodo, dict):
        return (f"Error: dispositivo desconocido '{dispositivo}'", None)
    accion_id = _ACCION_POR_ROL.get((accion, nodo.get("rol")))
    if accion_id is None or accion_id not in catalogo:
        return (f"Error: accion '{accion}' no valida para el rol '{nodo.get('rol')}'", None)
    comando = catalogo[accion_id]["comando"].format(ip=ip)
    ok, motivo = validar_comando(comando, ip_gestion)
    reversion_cmd = catalogo[accion_id].get("reversion_cmd", "").format(ip=ip)
    if not ok:
        return (f"Error: {motivo}", {"accion_id": accion_id, "vetado": True, "reversion_cmd": reversion_cmd})
    if not autonomo and not _aprobar(dispositivo, nodo.get("ip"), accion_id, ip, leer, escribir):
        return (f"Cancelado por el humano: {accion_id} en {dispositivo}",
                {"accion_id": accion_id, "cancelado": True, "reversion_cmd": reversion_cmd})
    orden = {"decision_id": decision_id, "accion_id": accion_id, "nodo_objetivo": dispositivo,
             "nodo_ip": nodo.get("ip"), "params": {"ip": ip}, "impacto": catalogo[accion_id]["impacto"]}
    res = conector.ejecutar_orden(orden, catalogo, ejecutor, timestamp)
    if res.get("exito"):
        return (f"OK: {accion_id} aplicada en {dispositivo} (rc={res.get('codigo_salida')})",
                {"accion_id": accion_id, "exito": True, "reversion_cmd": reversion_cmd, "resultado": res})
    return (f"Error: fallo en {dispositivo} (rc={res.get('codigo_salida')})",
            {"accion_id": accion_id, "exito": False, "reversion_cmd": reversion_cmd, "resultado": res})
