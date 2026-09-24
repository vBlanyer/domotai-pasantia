"""Tablero web de observabilidad y aprobacion del prototipo (solo biblioteca estandar).

Este fichero NO importa nada de lab/: la salud se lee como JSONL generico y las dependencias
llegan desde el perfil. Contiene el estado compartido y la costura de aprobacion (Task 1), los
lectores de datos (Task 2) y el servidor HTTP (Task 3).
"""
import itertools
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prototipo import traza

_MARCA_INCIDENTE = "⚠"   # el resumen de incidente de stream empieza por esta marca


class EstadoTablero:
    """Estado en memoria del tablero, seguro entre hilos: pendientes de aprobacion y las lineas del
    incidente en curso. El feed de decisiones resueltas NO vive aqui (sale de la traza)."""
    def __init__(self):
        self._lock = threading.Lock()
        self._pendientes = {}
        self._lineas = []
        self._seq = itertools.count(1)

    def anotar_linea(self, linea):
        with self._lock:
            if linea.startswith(_MARCA_INCIDENTE):
                self._lineas = []
            self._lineas.append(linea)

    def registrar_pendiente(self, tipo, prompt):
        ev = threading.Event()
        with self._lock:
            pid = str(next(self._seq))
            self._pendientes[pid] = {"id": pid, "tipo": tipo, "prompt": prompt,
                                     "lineas": list(self._lineas), "respuesta": None, "_event": ev}
        return pid, ev

    def pendientes(self):
        with self._lock:
            return [{k: v for k, v in p.items() if not k.startswith("_")}
                    for p in self._pendientes.values()]

    def resolver(self, pid, respuesta):
        with self._lock:
            p = self._pendientes.get(pid)
            if p is None or p["respuesta"] is not None:
                return False
            p["respuesta"] = respuesta
            p["_event"].set()
            return True

    def respuesta_de(self, pid):
        with self._lock:
            p = self._pendientes.get(pid)
            return p["respuesta"] if p else None

    def quitar(self, pid):
        with self._lock:
            self._pendientes.pop(pid, None)


class LectorWeb:
    """leer(prompt)->str respaldado por la web: registra una pendiente y bloquea hasta que la web
    responde. Clasifica el prompt igual que Lector (escalada si contiene '[s/N]', si no menu)."""
    def __init__(self, estado, timeout=None):
        self.estado = estado
        self.timeout = timeout

    @staticmethod
    def _tipo(prompt):
        return "escalada" if "[s/N]" in prompt else "menu"

    def __call__(self, prompt=""):
        pid, ev = self.estado.registrar_pendiente(self._tipo(prompt), prompt)
        respondio = ev.wait(self.timeout)
        respuesta = self.estado.respuesta_de(pid) if respondio else ""
        self.estado.quitar(pid)
        return respuesta if respuesta is not None else ""


def escribir_web(estado, escribir=print):
    """Envuelve un `escribir`: imprime y acumula la linea en el incidente en curso (para la tarjeta)."""
    def _f(texto):
        escribir(texto)
        estado.anotar_linea(texto)
    return _f


def leer_salud(ruta=None, contenedor=None, fichero_en_contenedor=None, ejecutar=subprocess.run):
    """Ultima muestra {t, estados} del monitor: de un fichero local (ruta) o via docker exec a un
    contenedor. Devuelve None si no hay datos o no se puede leer. No conoce nada del banco."""
    linea = None
    if ruta is not None:
        try:
            with open(ruta, encoding="utf-8") as f:
                lineas = [l for l in f if l.strip()]
        except OSError:
            return None
        linea = lineas[-1] if lineas else None
    elif contenedor is not None:
        try:
            r = ejecutar(["docker", "exec", contenedor, "tail", "-n1", fichero_en_contenedor],
                         capture_output=True, text=True)
        except OSError:
            return None
        if r.returncode != 0 or not r.stdout.strip():
            return None
        linea = r.stdout.strip().splitlines()[-1]
    if not linea:
        return None
    try:
        return json.loads(linea)
    except json.JSONDecodeError:
        return None


def estado_salud(muestra, dependencias=None):
    """Convierte una muestra {t, estados} en el JSON del panel de salud, decorando dependencias."""
    if muestra is None:
        return {"sin_datos": True}
    dependencias = dependencias or {}
    estados = muestra["estados"]
    servicios = [{"nombre": n, "estado": e, "depende_de": dependencias.get(n, [])}
                 for n, e in sorted(estados.items())]
    caidos = sum(1 for e in estados.values() if e != "ok")
    return {"t": muestra.get("t"), "servicios": servicios, "caidos": caidos, "total": len(estados)}


def _categoria_equipo(nombre, info, topologia):
    """Categoría del dispositivo para el inventario: cortafuegos (por rol en la topología),
    gestión (SOC/SIEM/MDR, por función), endpoint (sin servicios prestados) o servidor."""
    if (topologia.get(nombre) or {}).get("rol") == "firewall_perimetral":
        return "cortafuegos"
    funcion = (info.get("funcion") or "").lower()
    if any(p in funcion for p in ("soc", "siem", "mdr", "gestion")):
        return "gestion"
    return "servidor" if info.get("servicios_prestados") else "endpoint"


def estado_equipos(activos, topologia, salud):
    """Inventario de dispositivos del cliente (del perfil), con categoría y estado.

    `activos` = {nombre: {ip, funcion, criticidad, servicios_prestados, depende_de}} del perfil;
    `topologia` = {nombre: {rol, ip, gateway}} (aporta los cortafuegos que no están en activos);
    `salud` = el JSON de estado_salud ({servicios:[{nombre,estado}]} | {sin_datos} | None): de ahí
    sale el `estado` de los nodos monitoreados; el resto queda en None (sin monitor de salud)."""
    activos, topologia = activos or {}, topologia or {}
    estados = {s["nombre"]: s["estado"] for s in (salud or {}).get("servicios", [])}
    equipos = []
    for nombre in list(activos) + [n for n in topologia if n not in activos]:
        info = activos.get(nombre) or {}
        topo = topologia.get(nombre) or {}
        if nombre not in activos:                       # nodo solo en la topología (p.ej. cortafuegos)
            info = {"ip": topo.get("ip"), "funcion": "cortafuegos perimetral",
                    "criticidad": "alta", "servicios_prestados": [], "depende_de": []}
        equipos.append({
            "nombre": nombre, "ip": info.get("ip") or topo.get("ip"),
            "funcion": info.get("funcion"), "criticidad": info.get("criticidad"),
            "categoria": _categoria_equipo(nombre, info, topologia),
            "servicios_prestados": info.get("servicios_prestados") or [],
            "depende_de": info.get("depende_de") or [],
            "estado": estados.get(nombre),
        })
    return sorted(equipos, key=lambda e: e["nombre"])


def _resumen_traza(reg):
    imp = reg.get("impacto_determinado") or {}
    est = reg.get("justificacion_estructurada") or {}
    return {"id_decision": reg.get("id_decision"), "timestamp": reg.get("timestamp"),
            "activo": reg.get("activo"), "clase": reg.get("clase"), "confianza": reg.get("confianza"),
            "accion_final": reg.get("accion_final"), "requiere_humano": reg.get("requiere_humano"),
            "impacto": reg.get("impacto") or imp.get("nivel"), "motivo": imp.get("motivo"),
            "origen_ip": (est.get("evidencia") or {}).get("origen_ip"),
            # de dónde viene la justificación (plantilla vs LLM), la técnica y si consultó el RAG:
            # el detalle completo (texto + pasajes) sale por /api/traza/<id>.
            "version_justificador": reg.get("version_justificador"),
            "tecnica_mitre": est.get("tecnica_mitre") or [],
            "con_rag": bool(reg.get("pasajes_usados")),
            # cadena de hashes (RF-09) para el registro auditable del panel Trazas
            "hash": reg.get("hash"), "hash_previo": reg.get("hash_previo"),
            # discriminador de los resumenes de supresion (RF-11) para que el visor los marque
            "tipo": reg.get("tipo"), "alertas_suprimidas": reg.get("alertas_suprimidas")}


def lista_trazas(ruta, n=None):
    try:
        regs = traza.leer_registros(ruta)
    except FileNotFoundError:
        return []
    if n:
        regs = regs[-n:]
    return [_resumen_traza(r) for r in regs]


_CORPUS_POR_ID = None


def _corpus_por_id():
    """Corpus del RAG indexado por id (cacheado). Vacío si el corpus no está disponible."""
    global _CORPUS_POR_ID
    if _CORPUS_POR_ID is None:
        try:
            from prototipo import rag
            _CORPUS_POR_ID = {d["id"]: d for d in rag.cargar_corpus()}
        except Exception:
            _CORPUS_POR_ID = {}
    return _CORPUS_POR_ID


def _hidratar_pasajes(reg, corpus):
    """La traza guarda `pasajes_usados` como IDs; los resolvemos a {id, titulo, texto} del corpus
    (en el campo `pasajes`) para que el visor muestre el conocimiento recuperado, no los IDs."""
    ids = reg.get("pasajes_usados") or []
    reg["pasajes"] = [{"id": i, "titulo": corpus[i].get("titulo"), "texto": corpus[i].get("texto")}
                      for i in ids if isinstance(i, str) and i in corpus]
    return reg


def traza_detalle(ruta, id_decision):
    try:
        regs = traza.leer_registros(ruta)
    except FileNotFoundError:
        return None
    # La última coincidencia: si se relanzó el daemon sobre la misma traza, los id_decision se
    # repiten entre corridas; la vigente (la del feed) es la más reciente.
    hallado = None
    for r in regs:
        if r.get("id_decision") == id_decision:
            hallado = r
    return _hidratar_pasajes(hallado, _corpus_por_id()) if hallado is not None else None


def verificar_traza(ruta):
    try:
        regs = traza.leer_registros(ruta)
    except FileNotFoundError:
        regs = []
    v = traza.verificar(regs)
    return {"ok": v["valida"], "roto_en": v["primer_fallo"], "motivo": v["motivo"], "n": v["n"]}


_TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
          ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json",
          ".ico": "image/x-icon", ".png": "image/png", ".woff2": "font/woff2", ".woff": "font/woff",
          ".map": "application/json"}
_DIR_ESTATICOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "visor", "dist")


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):        # silencioso: el daemon ya imprime lo suyo
        pass

    def _cors(self):
        # Liga solo a 127.0.0.1, asi que abrir CORS es aceptable (el visor React lo consume en dev).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _responder(self, obj, codigo=200):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _servir_archivo(self, rel):
        # Sirve cualquier fichero bajo la raiz de estaticos (el build de Vite: index.html + assets/),
        # resolviendo la ruta y rechazando la travesia con realpath (no escapa de la raiz).
        rel = rel.lstrip("/") or "index.html"
        raiz = os.path.realpath(self.server.estaticos)
        ruta = os.path.realpath(os.path.join(raiz, rel))
        if not (ruta == raiz or ruta.startswith(raiz + os.sep)) or not os.path.isfile(ruta):
            return self._responder({"error": "no encontrado"}, 404)
        try:
            with open(ruta, "rb") as f:
                datos = f.read()
        except OSError:
            return self._responder({"error": "no encontrado"}, 404)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", _TIPOS.get(os.path.splitext(ruta)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        s = self.server
        ruta = self.path.split("?", 1)[0]
        try:
            if ruta == "/api/salud":
                return self._responder(estado_salud(leer_salud(ejecutar=s.salud_ejecutar, **s.salud),
                                                    s.dependencias))
            if ruta == "/api/equipos":
                salud = estado_salud(leer_salud(ejecutar=s.salud_ejecutar, **s.salud), s.dependencias)
                return self._responder(estado_equipos(s.activos, s.topologia, salud))
            if ruta == "/api/decisiones":
                return self._responder(lista_trazas(s.ruta_traza, n=50))
            if ruta == "/api/pendientes":
                return self._responder(s.estado.pendientes())
            if ruta == "/api/trazas":
                return self._responder(lista_trazas(s.ruta_traza))
            if ruta.startswith("/api/traza/"):
                d = traza_detalle(s.ruta_traza, ruta[len("/api/traza/"):])
                return self._responder(d) if d is not None else self._responder({"error": "no encontrada"}, 404)
            if ruta == "/api/verificar":
                return self._responder(verificar_traza(s.ruta_traza))
            if ruta.startswith("/api/"):
                return self._responder({"error": "no encontrado"}, 404)
            return self._servir_archivo(ruta)          # el build de React (index.html + assets/)
        except Exception as e:            # nunca tumbar el servidor por un handler
            return self._responder({"error": str(e)}, 500)

    def do_POST(self):
        try:
            if self.path.split("?", 1)[0] != "/api/aprobar":
                return self._responder({"error": "no encontrado"}, 404)
            n = int(self.headers.get("Content-Length") or 0)
            cuerpo = json.loads(self.rfile.read(n) or b"{}")
            ok = self.server.estado.resolver(str(cuerpo.get("id")), str(cuerpo.get("respuesta", "")))
            return self._responder({"ok": True}) if ok else self._responder({"error": "pendiente no vigente"}, 409)
        except Exception as e:
            return self._responder({"error": str(e)}, 500)


def crear_servidor(estado, ruta_traza, salud=None, dependencias=None, estaticos=None,
                   puerto=8787, salud_ejecutar=subprocess.run, activos=None, topologia=None):
    """ThreadingHTTPServer ligado SOLO a 127.0.0.1. `salud` es {} o {ruta} o {contenedor,
    fichero_en_contenedor}. `activos`/`topologia` (del perfil) alimentan /api/equipos. Guarda la
    config en atributos del servidor para el manejador."""
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), _Manejador)
    srv.estado = estado
    srv.ruta_traza = ruta_traza
    srv.salud = salud or {}
    srv.dependencias = dependencias or {}
    srv.estaticos = estaticos or _DIR_ESTATICOS
    srv.salud_ejecutar = salud_ejecutar
    srv.activos = activos or {}
    srv.topologia = topologia or {}
    return srv
