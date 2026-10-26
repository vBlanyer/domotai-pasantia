"""Tablero web de observabilidad y aprobacion del prototipo (solo biblioteca estandar).

Este fichero NO importa nada de lab/: la salud se lee como JSONL generico y las dependencias
llegan desde el perfil. Contiene el estado compartido y la costura de aprobacion (Task 1), los
lectores de datos (Task 2) y el servidor HTTP (Task 3).
"""
import glob
import hmac
import itertools
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prototipo.motor import actores, familias
from prototipo.servicio import casos, red, traza

_MARCA_INCIDENTE = "⚠"   # el resumen de incidente de stream empieza por esta marca
# Cota del listado /api/trazas: el visor lo sondea cada 2 s, y sin ella cada tick releería y
# enviaría la traza entera. Los totales del periodo salen de /api/metricas (fichero completo).
LIMITE_TRAZAS = 500
# Tope de la cola de pendientes (M3 de la auditoría 20/10): a diferencia de la supresión (que deduplica
# por clave), un atacante que controla sus logs fabrica CLAVES infinitas (un srcip distinto por alerta,
# ni siquiera tiene que ser una IP) y cada una encola tarjeta nueva -> memoria sin límite y /api/pendientes
# ordenando todo en cada sondeo. Al tope se desaloja la MENOS severa y más vieja (la que el analista
# vería la última), nunca una en curso; el desalojo se cuenta y deja rastro.
MAX_PENDIENTES = 500
# Buffer circular de la vista «Consola» del visor: el registro vivo del daemon (lo que narra la
# terminal), acotado — el visor lo pide incremental (/api/consola?desde=N), nunca el histórico
# (para eso están Trazas y las métricas).
CONSOLA_MAX = 1000


class EstadoTablero:
    """Estado en memoria del tablero, seguro entre hilos: pendientes de aprobacion y las lineas del
    incidente en curso. El feed de decisiones resueltas NO vive aqui (sale de la traza)."""
    def __init__(self, max_pendientes=MAX_PENDIENTES, consola_max=CONSOLA_MAX):
        self._lock = threading.Lock()
        self._pendientes = {}
        self._lineas = []
        import collections
        self._consola = collections.deque(maxlen=consola_max)   # feed vivo para la vista «Consola»
        self._consola_n = 0                                     # secuencia total (para ?desde=N)
        self._seq = itertools.count(1)
        self._cola = {}                    # cola de decisiones humanas (modo web no bloqueante)
        self._max_pendientes = max_pendientes
        self.descartadas_tope = 0          # desalojadas por el tope (M3); visible en el log
        self._ultimo_aviso_tope = None
        self._orden = itertools.count(1)   # orden de llegada, para desempatar por severidad
        self._resolutor = None             # fn(pid, respuesta, paso=None)->bool, la registra el daemon (ejecuta+traza)
        self._actualizador = None          # fn(id_decision, estado/asignado/nota, operador)->bool: añade un `actualizacion_caso` a la cadena
        self._descartador = None           # fn(entrada): traza el desalojo por tope (RF-09, nada en silencio)
        self._pausada = False              # kill switch (#8): con True, toda auto-ejecución pasa a esperar humano

    def pausar(self, valor, operador=None):
        """Activa/desactiva la pausa global de la automatización (#8). Estado de sesión en memoria:
        un reinicio del daemon la limpia. Narra en la Consola solo el CAMBIO (quién pulsó el kill
        switch importa en el diario; un reenvío idempotente no hace ruido)."""
        with self._lock:
            antes, self._pausada = self._pausada, bool(valor)
            ahora = self._pausada
        if antes != ahora:   # fuera del lock: anotar_linea lo toma
            self.anotar_linea(("⏻ automatización EN PAUSA — toda contención espera al humano"
                               if ahora else "⏻ automatización reanudada")
                              + (f" · por {operador}" if operador else ""))
        return ahora

    def pausada(self):
        with self._lock:
            return self._pausada

    def fijar_descartador(self, fn):
        """El daemon registra cómo trazar un desalojo por tope (RF-09): una tarjeta que el analista
        nunca verá no puede desaparecer del rastro auditado."""
        self._descartador = fn

    def encolar_decision(self, entrada):
        """Encola una decisión que espera al humano (modo web no bloqueante). `entrada` lleva la
        `clave` (IP, familia) para deduplicar, `severidad` para ordenar, y el contexto para resolver.
        Si ya hay una en cola con la misma clave, incrementa su contador en vez de duplicar."""
        desalojada, avisar = None, False
        with self._lock:
            clave = entrada.get("clave")
            if clave is not None:
                for p in self._cola.values():
                    # Una tarjeta en curso ya tiene respuesta: lo que se encole ahora (la escalada que
                    # esa respuesta provoca) es una tarjeta nueva, no una repetición de aquella.
                    if p.get("clave") == clave and not p.get("en_curso"):
                        p["suprimidas"] += 1
                        return p["id"]
            if len(self._cola) >= self._max_pendientes:
                vivas = [p for p in self._cola.values() if not p.get("en_curso")]
                if vivas:                  # nunca se desaloja una en curso (su resolución ya se ejecuta)
                    # La severidad viene de la alerta (influenciable por quien controla sus logs):
                    # bajo un flood dirigido el desalojo puede tocar tarjetas legítimas — residual
                    # inevitable de toda cola acotada; la mitigación es que CADA desalojo se traza.
                    desalojada = min(vivas, key=lambda p: (p.get("severidad") or 0, p.get("orden", 0)))
                    del self._cola[desalojada["id"]]
                    self.descartadas_tope += 1
                    ahora = time.monotonic()
                    if self._ultimo_aviso_tope is None or ahora - self._ultimo_aviso_tope >= 60.0:
                        self._ultimo_aviso_tope = ahora
                        avisar = True
            pid = str(next(self._seq))
            # `paso` identifica el menú que se está mostrando; avanza al cambiar de menú (reclasificar)
            # para que una respuesta dada al menú anterior no se aplique al nuevo. `encolado_en` es la
            # hora de PARED al encolar (no la de la alerta, influenciable): el SLA del analista en el
            # visor («lleva esperando X»). Vive solo en esta cola en memoria, no en la traza auditada.
            self._cola[pid] = {**entrada, "id": pid, "orden": next(self._orden), "suprimidas": 0, "paso": 0,
                               "encolado_en": datetime.now(timezone.utc).isoformat()}
        # El aviso y la traza del desalojo van FUERA del lock: un stderr atascado (journald con
        # backpressure) o la E/S de la cadena no pueden congelar la cola entera.
        if desalojada is not None:
            if avisar:
                print(f"[aviso] cola de pendientes al tope ({self._max_pendientes}): desalojada la "
                      f"menos severa más vieja ({self.descartadas_tope} desalojadas en total)",
                      file=sys.stderr)
            if self._descartador is not None:
                try:
                    self._descartador(desalojada)
                except Exception as e:     # trazar el desalojo no puede romper el encolado
                    print(f"[aviso] no se pudo trazar el desalojo por tope: {type(e).__name__}: {e}",
                          file=sys.stderr)
        return pid

    def sumar_repeticion(self, claves, n=1):
        """Si hay en cola una decisión con alguna de `claves`, suma `n` repeticiones a su contador y
        devuelve su id_decision (el `sN` que se trazará al resolverla); si no, None. El daemon lo
        consulta ANTES de triar una repetición: así no se vuelve a clasificar, justificar ni
        ejecutar (SSH) algo que ya espera al analista."""
        with self._lock:
            for p in self._cola.values():
                if p.get("clave") in claves:
                    p["suprimidas"] += n
                    return (p.get("decision") or {}).get("id_decision") or p["id"]
        return None

    def tomar_decision(self, pid):
        """Marca la decisión como en curso (el analista ya respondió y se está ejecutando) y la
        devuelve; None si no está o ya la tomó otra respuesta. Sigue en la cola hasta sacar_decision:
        así sumar_repeticion la encuentra mientras dura la ejecución."""
        with self._lock:
            p = self._cola.get(pid)
            if p is None or p.get("en_curso"):
                return None
            p["en_curso"] = True
            return dict(p)

    def decisiones_pendientes(self):
        """Las decisiones que esperan al analista (sin las que ya se están ejecutando), ordenadas por
        severidad (desc) y, a igualdad, por llegada."""
        with self._lock:
            return sorted((dict(p) for p in self._cola.values() if not p.get("en_curso")),
                          key=lambda p: (-(p.get("severidad") or 0), p.get("orden", 0)))

    def sacar_decision(self, pid):
        """Saca (y devuelve) la decisión de la cola, o None si no está o ya fue resuelta."""
        with self._lock:
            return self._cola.pop(pid, None)

    def ver_decision(self, pid):
        """Copia de la decisión en cola (sin quitarla), o None."""
        with self._lock:
            p = self._cola.get(pid)
            return dict(p) if p else None

    def actualizar_decision(self, pid, campos):
        """Mezcla `campos` en la decisión en cola (p. ej. pasar al submenú de clases al reclasificar)."""
        with self._lock:
            if pid in self._cola:
                self._cola[pid].update(campos)

    def fijar_resolutor(self, fn):
        """El daemon registra aquí cómo aplicar un veredicto (ejecuta la contención + escribe la traza)."""
        self._resolutor = fn

    def resolver_decision(self, pid, respuesta, paso=None, operador=None):
        """Aplica la respuesta del analista a la decisión en cola, vía el resolutor del daemon.
        `paso` es el del menú que vio el analista (None = no se comprueba). `operador` queda en la
        traza (no repudio: quién aprobó)."""
        return bool(self._resolutor and self._resolutor(pid, respuesta, paso=paso, operador=operador))

    def fijar_actualizador(self, fn):
        """El daemon registra aquí cómo anotar un caso: añadir un `actualizacion_caso` a la cadena."""
        self._actualizador = fn

    def actualizar_caso(self, id_decision, estado=None, asignado=None, nota=None, operador=None):
        """Cambio de ciclo de vida del caso (estado/asignado/nota) de una decisión: lo añade a la
        traza como registro encadenado (ciclo de caso, NO muta la decisión). Propaga ValueError
        (estado inválido / actualización vacía) para que el handler responda 400. `operador` = no
        repudio (del token). Devuelve True si se anotó; False si no hay actualizador (ruta bloqueante)."""
        if not self._actualizador:
            return False
        return bool(self._actualizador(id_decision, estado=estado, asignado=asignado, nota=nota, operador=operador))

    def anotar_linea(self, linea):
        # texto_terminal también aquí (B3): la línea viaja al navegador y puede llevar campos del
        # log del atacante. React escapa el HTML, pero los controles no tienen por qué llegar.
        from prototipo.servicio import validacion
        sana = validacion.texto_terminal(linea)
        with self._lock:
            if linea.startswith(_MARCA_INCIDENTE):
                self._lineas = []
            self._lineas.append(sana)   # ambas superficies viajan al navegador: ambas saneadas
            self._consola_n += 1
            self._consola.append({"n": self._consola_n, "t": datetime.now().strftime("%H:%M:%S"),
                                  "linea": sana})

    def consola(self, desde=0):
        """Las líneas del feed con secuencia > `desde` (incremental) y la secuencia más alta."""
        with self._lock:
            return self._consola_n, [dict(l) for l in self._consola if l["n"] > desde]

    def registrar_pendiente(self, tipo, prompt, lineas=None):
        # `lineas`: contexto propio de la tarjeta (un agente por incidente trae el suyo); sin él, el
        # buffer compartido del incidente en curso (camino de un solo incidente a la vez).
        ev = threading.Event()
        with self._lock:
            pid = str(next(self._seq))
            self._pendientes[pid] = {"id": pid, "tipo": tipo, "prompt": prompt,
                                     "lineas": list(self._lineas if lineas is None else lineas),
                                     "respuesta": None, "_event": ev}
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
    def __init__(self, estado, timeout=None, lineas=None):
        self.estado = estado
        self.timeout = timeout
        self.lineas = lineas          # contexto propio de este incidente (agentes concurrentes); None = buffer compartido

    @staticmethod
    def _tipo(prompt):
        return "escalada" if "[s/N]" in prompt else "menu"

    def __call__(self, prompt=""):
        pid, ev = self.estado.registrar_pendiente(self._tipo(prompt), prompt, lineas=self.lineas)
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
                         capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):     # sin docker, o un contenedor pausado
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


def _resumen_traza(reg, ips=None, externos=()):
    imp = reg.get("impacto_determinado") or {}
    est = reg.get("justificacion_estructurada") or {}
    _conten = contencion_de(reg)                 # una sola vez (desenlace + dispositivo)
    return {"id_decision": reg.get("id_decision"), "timestamp": reg.get("timestamp"),
            "activo": reg.get("activo"), "clase": reg.get("clase"), "confianza": reg.get("confianza"),
            "accion_final": reg.get("accion_final"), "requiere_humano": reg.get("requiere_humano"),
            # gravedad (ordena la cola), propuesta vs final y cómo la trató el filtro del perfil
            # (veta/degrada/permite), y qué decidió el analista y a qué clase corrigió
            "prioridad": reg.get("prioridad"), "accion_propuesta": reg.get("accion_propuesta"),
            "resultado_filtro": reg.get("resultado_filtro"),
            "recomendacion": reg.get("recomendacion"),   # respuesta dirigida recomendada (asesora)
            "veredicto_humano": reg.get("veredicto_humano"),
            "clase_reclasificada": reg.get("clase_reclasificada"),
            "impacto": reg.get("impacto") or imp.get("nivel"), "motivo": imp.get("motivo"),
            # activos que caerían en cascada por la acción: se marca en la fila (aviso de seguridad)
            "cascada": imp.get("activos_afectados_en_cascada") or [],
            "origen_ip": (est.get("evidencia") or {}).get("origen_ip"),
            # de dónde viene la justificación (plantilla vs LLM), la técnica y si consultó el RAG:
            # el detalle completo (texto + pasajes) sale por /api/traza/<id>.
            "version_justificador": reg.get("version_justificador"),
            "tecnica_mitre": est.get("tecnica_mitre") or [],
            "con_rag": bool(reg.get("pasajes_usados")),
            # cadena de hashes (RF-09) para el registro auditable del panel Trazas
            "hash": reg.get("hash"), "hash_previo": reg.get("hash_previo"),
            # discriminador de los resumenes de supresion (RF-11) para que el visor los marque
            "tipo": reg.get("tipo"), "alertas_suprimidas": reg.get("alertas_suprimidas"),
            # reversión: qué decisión deshizo, dónde y si se aplicó; error: por qué no se procesó
            "id_decision_revertida": reg.get("id_decision_revertida"),
            "indice_revertido": reg.get("indice_revertido"), "exito": reg.get("exito"),
            "accion_id": reg.get("accion_id"), "nodo": reg.get("nodo"), "error": reg.get("error"),
            # relación evento-equipo y desenlace de la contención, para la vista Red
            "relaciones": relaciones(reg, ips or {}, externos),
            "contencion": _conten[0], "dispositivo": _conten[1],
            # ciclo de vida del caso (registro `actualizacion_caso`): el visor pliega estos campos
            # (datos.estadoDeCasos). None en una decisión normal (no estorba).
            "estado": reg.get("estado"), "asignado": reg.get("asignado"), "nota": reg.get("nota"),
            "operador": reg.get("operador"), "decidido_en": reg.get("decidido_en")}


# Registros de la traza que no son decisiones: repeticiones suprimidas, el eco de gestión del MDR,
# fallos al procesar un incidente y reversiones de una contención ya decidida.
_NO_DECISIONES = ("actividad_suprimida", "actividad_propia", "error", "reversion", "actualizacion_caso")


_ESTADO_PLAN = {"mitigado": "contenida", "fallido": "fallida", "cancelado_por_humano": "cancelada",
                "degradado": "degradada"}


def contencion_de(reg):
    """(estado, dispositivo) del desenlace de una decisión; misma lógica que datos.contencionDe del
    visor, que la muestra en el detalle. `dispositivo` es donde quedó contenida (o la ruta si se
    enrutó)."""
    agente = reg.get("mitigacion_agente")
    if agente:
        return _ESTADO_PLAN.get(agente.get("resultado"), "fallida"), agente.get("dispositivo_ejecutor")
    orden = reg.get("orden")
    if not orden:
        if reg.get("ruta"):
            return "enrutada", reg.get("ruta")
        return ("retenida" if reg.get("veredicto_humano") in ("rechazar", "reclasificar") else "sin_accion"), None
    if (reg.get("ejecucion") or {}).get("exito") and (reg.get("verificacion") or {}).get("verificado"):
        return "contenida", orden.get("nodo_objetivo")
    esc = reg.get("escalada")
    if esc:
        estado = _ESTADO_PLAN.get(esc.get("resultado"), "fallida")
        return estado, esc.get("dispositivo_ejecutor") if estado == "contenida" else None
    return "fallida", None


def _red_segura(perfil):
    """red.red_de que nunca lanza por culpa de la sección `red` (solo presentación): si algo
    inesperado revienta, se reconstruye sin ella y se avisa. Devuelve (mapa, avisos_extra)."""
    try:
        return red.red_de(perfil), []
    except Exception as e:
        sin_red = {k: v for k, v in (perfil or {}).items() if k != "red"}
        return red.red_de(sin_red), [f"sección red inutilizable ({type(e).__name__}: {e}), se ignora"]


def ips_de(perfil):
    return {n: v.get("ip") for n, v in _red_segura(perfil)[0]["nodos"].items() if v.get("ip")}


def relaciones(reg, ips, externos=()):
    """{equipo: [etiquetas]} de un registro: `objetivo` (el activo atacado), `origen` (la IP de origen
    es la del equipo) y `contuvo_aqui` (el dispositivo donde quedó contenida). Solo decisiones.

    `externos`: nodos de tipo `externo` (p. ej. internet). La IP de un atacante de fuera no coincide
    con ningún equipo inventariado, así que se atribuye su origen a esos nodos: «entra desde internet»."""
    if reg.get("tipo") in _NO_DECISIONES:
        return {}
    rel = {}
    def _anadir(nombre, etiqueta):
        if nombre and etiqueta not in rel.setdefault(nombre, []):
            rel[nombre].append(etiqueta)
    _anadir(reg.get("activo"), "objetivo")
    ip = ((reg.get("contexto") or {}).get("origen_ip")
          or (((reg.get("justificacion_estructurada") or {}).get("evidencia")) or {}).get("origen_ip"))
    if ip:
        internos = [n for n, ip_nodo in ips.items() if actores._coincide(ip, ip_nodo)]
        for nombre in internos:
            _anadir(nombre, "origen")
        if not internos:                       # fuente no inventariada -> viene de internet
            for nombre in externos:
                _anadir(nombre, "origen")
    estado, dispositivo = contencion_de(reg)
    if estado == "contenida":
        _anadir(dispositivo, "contuvo_aqui")
    return rel


def _estado_nodo(salud, a):
    if salud and salud != "ok":
        return "caido"
    if a["pendientes"]:
        return "pendiente"
    ultima = a["_ultima_objetivo"]
    if ultima is not None:
        clase = ultima.get("clase_reclasificada") or ultima.get("clase") or ""
        estado, _ = contencion_de(ultima)
        if ((clase.startswith("vp_") or clase == "amenaza_enrutada") and estado != "contenida"
                and ultima.get("veredicto_humano") != "rechazar"):
            return "atacado"
    if a["_contenido"]:
        return "contenido"
    if a.get("origen"):                        # solo originó ataques (p. ej. internet): se señala, no es «sin actividad»
        return "origen"
    return "sin_actividad"


def estado_red(perfil, registros, pendientes=(), salud=None):
    """El mapa de la red con la actividad de cada equipo, para /api/red (ver prototipo/servicio/red.py)."""
    r, extra_avisos = _red_segura(perfil)
    ips = {n: v.get("ip") for n, v in r["nodos"].items() if v.get("ip")}
    externos = [n for n, v in r["nodos"].items() if v.get("tipo") == "externo"]
    salud_de = {s["nombre"]: s["estado"] for s in (salud or {}).get("servicios", [])}
    act = {n: {"objetivo": 0, "origen": 0, "contuvo_aqui": 0, "pendientes": 0, "ultima": None,
               "_ultima_objetivo": None, "_contenido": False} for n in r["nodos"]}
    for reg in registros:
        for nombre, etiquetas in relaciones(reg, ips, externos).items():
            a = act.get(nombre)
            if a is None:
                continue
            for e in etiquetas:
                a[e] += 1
            ts = reg.get("timestamp")
            if ts and (a["ultima"] is None or ts > a["ultima"]):
                a["ultima"] = ts
            if "objetivo" in etiquetas:
                a["_ultima_objetivo"] = reg            # la traza está en orden de escritura
            if ("objetivo" in etiquetas or "contuvo_aqui" in etiquetas) and contencion_de(reg)[0] == "contenida":
                a["_contenido"] = True
    for p in pendientes or ():
        alerta = p.get("alerta") or p
        for nombre, ip in ips.items():
            if alerta.get("activo") == nombre or (alerta.get("origen_ip")
                                                   and actores._coincide(alerta["origen_ip"], ip)):
                act[nombre]["pendientes"] += 1
        if alerta.get("activo") in act and alerta.get("activo") not in ips:
            act[alerta["activo"]]["pendientes"] += 1
    nodos = []
    for nombre, n in r["nodos"].items():
        a = act[nombre]
        visible = {k: v for k, v in a.items() if not k.startswith("_")}
        visible["estado"] = _estado_nodo(salud_de.get(nombre), a)
        nodos.append({**n, "salud": salud_de.get(nombre), "actividad": visible})
    return {"nodos": nodos, "enlaces": [[h, p] for h, p in r["enlaces"].items()],
            "dependencias": [[n["nombre"], d] for n in r["nodos"].values() for d in n["depende_de"]
                             if d in r["nodos"]],
            "zonas": [{"nombre": z, "nodos": ms} for z, ms in r["zonas"]], "avisos": r["avisos"] + extra_avisos}

def metricas(regs, desde=None, hasta=None):
    """Indicadores del periodo (vista SLA) calculados de la traza: tasa de FP, % automatizado, MTTR
    (tiempo medio de respuesta humana, de recibido_en/resuelto_en), ruido evitado (suprimidas), y
    distribuciones por clase, veredicto, día, activo y técnica MITRE.

    Con `desde`/`hasta` (YYYY-MM-DD) acota al periodo por el día del `timestamp` (para el informe
    exportable). Sin ellos, sobre todo el fichero (comportamiento de siempre)."""
    if desde or hasta:
        def _en_rango(r):
            dia = (r.get("timestamp") or "")[:10]
            return bool(dia) and (not desde or dia >= desde) and (not hasta or dia <= hasta)
        regs = [r for r in regs if _en_rango(r)]
    # Ni los resúmenes de supresión ni el eco del login del propio MDR son decisiones.
    dec = [r for r in regs if r.get("tipo") not in _NO_DECISIONES]
    total = len(dec)
    por_clase, veredictos, por_dia, activos, mitre = {}, {}, {}, {}, {}
    fp = auto = 0
    tiempos = []
    reg_familias = familias.registro()
    for r in dec:
        c = r.get("clase") or "otra"
        por_clase[c] = por_clase.get(c, 0) + 1
        if c.startswith("fp_"):
            fp += 1
        if not r.get("requiere_humano"):
            auto += 1
        v = r.get("veredicto_humano")
        if v:
            veredictos[v] = veredictos.get(v, 0) + 1
        dia = (r.get("timestamp") or "")[:10]
        if dia:
            por_dia[dia] = por_dia.get(dia, 0) + 1
        a = r.get("activo")
        if a:
            activos[a] = activos.get(a, 0) + 1
        # Matriz ATT&CK = COBERTURA POR FAMILIA: cada decisión cuenta por TODAS las técnicas que su
        # familia declara en familias.yml, no solo la que trajo la regla (una regla etiqueta menos
        # técnicas que su familia: fuerza bruta solo T1110, pero acceso_credenciales cubre T1110+T1078).
        # Así un ataque por familia enciende la columna entera y el visor refleja la cobertura real del
        # MDR, no el ruido de qué subtécnica concreta puso Wazuh. La traza por incidente conserva la
        # técnica cruda (justificacion_estructurada.tecnica_mitre); esto es solo el agregado de cobertura.
        familia = (r.get("contexto") or {}).get("familia")
        for t in (reg_familias.get(familia) or {}).get("mitre") or []:
            mitre[t] = mitre.get(t, 0) + 1
        ini, fin = r.get("recibido_en"), r.get("resuelto_en")
        if isinstance(ini, (int, float)) and isinstance(fin, (int, float)):
            tiempos.append(fin - ini)
    ranking = lambda d, k: sorted(({k: n, "n": c} for n, c in d.items()), key=lambda x: -x["n"])[:8]
    # Métricas de valor: cuánta carga va al humano (lo que el MDR NO resuelve solo) y con qué
    # frecuencia el analista corrige al motor (rechazar o reclasificar una decisión).
    escalado_humano = total - auto
    resueltos_humano = sum(veredictos.values())
    override = veredictos.get("rechazar", 0) + veredictos.get("reclasificar", 0)
    return {
        "total": total, "fp": fp, "tasa_fp": round(fp / total, 3) if total else 0.0,
        "auto": auto, "pct_auto": round(auto / total, 3) if total else 0.0,
        "escalado_humano": escalado_humano, "pct_humano": round(escalado_humano / total, 3) if total else 0.0,
        "resueltos_humano": resueltos_humano, "override": override,
        "tasa_override": round(override / resueltos_humano, 3) if resueltos_humano else 0.0,
        "suprimidas": sum((r.get("alertas_suprimidas") or 0) for r in regs if r.get("tipo") == "actividad_suprimida"),
        "mttr_seg": round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
        "por_clase": por_clase, "veredictos": veredictos,
        "por_dia": [{"dia": d[5:], "n": n} for d, n in sorted(por_dia.items())],
        "top_activos": ranking(activos, "nombre"), "mitre": ranking(mitre, "tecnica"),
        "desde": desde, "hasta": hasta,
    }


def _entero(path, nombre):
    """El parámetro `nombre` de la consulta como entero, o None si falta o no lo es."""
    valor = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query).get(nombre, [""])[0]
    try:
        return int(valor)
    except ValueError:
        return None


def _limite(path):
    """`?limite=N` (entero > 0) de la consulta, o la cota por defecto si falta o no es válido."""
    n = _entero(path, "limite")
    return n if n is not None and n > 0 else LIMITE_TRAZAS


def _fecha(path, nombre):
    """El parámetro `nombre` de la consulta como fecha YYYY-MM-DD válida (solo dígitos y guiones), o
    None. Se usa para comparar con `timestamp[:10]`; no llega a ningún comando."""
    v = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query).get(nombre, [""])[0]
    p = v.split("-")
    return v if len(p) == 3 and len(p[0]) == 4 and all(t.isdigit() for t in p) else None


_cache_traza = {"ruta": None, "firma": None, "regs": []}
_cache_traza_lock = threading.Lock()

def _registros_cacheados(ruta):
    """Registros de la traza, releídos solo si el fichero cambió (mtime+tamaño). El visor sondea
    cada 2 s cinco endpoints que releían la traza entera cada vez; con la caché, mientras no llegue
    una decisión nueva la lectura es gratis. [] si el fichero no existe aún."""
    try:
        st = os.stat(ruta)
        firma = (st.st_mtime_ns, st.st_size)
    except OSError:
        return []
    with _cache_traza_lock:
        c = _cache_traza
        if c["ruta"] == ruta and c["firma"] == firma:
            return c["regs"]
        regs = traza.leer_registros(ruta)
        c.update(ruta=ruta, firma=firma, regs=regs)
        return regs


def _registros_periodo(ruta):
    """Registros de TODAS las trazas del directorio (hay una por ejecución del daemon: trazas-*.jsonl),
    para que el informe por periodo cubra el histórico y no solo la ejecución en curso. Sin caché: es
    de uso bajo demanda (el informe), no el sondeo cada 2 s."""
    carpeta = os.path.dirname(ruta) or "."
    regs = []
    for f in sorted(glob.glob(os.path.join(carpeta, "trazas-*.jsonl"))):
        try:
            regs.extend(traza.leer_registros(f))
        except OSError:
            pass
    return regs


def lista_trazas(ruta, n=None, perfil=None):
    regs = _registros_cacheados(ruta)
    if not regs and not os.path.exists(ruta):
        return []
    # `indice` es la posición del registro en la cadena completa: identifica cada fila en el visor
    # (los id_decision se repiten entre relanzamientos) y casa con el roto_en de /api/verificar.
    inicio = max(0, len(regs) - n) if n else 0
    ips, externos = {}, []
    if perfil:
        mapa = _red_segura(perfil)[0]
        ips = {nm: v.get("ip") for nm, v in mapa["nodos"].items() if v.get("ip")}
        externos = [nm for nm, v in mapa["nodos"].items() if v.get("tipo") == "externo"]
    return [{**_resumen_traza(r, ips, externos), "indice": inicio + k} for k, r in enumerate(regs[inicio:])]


_CORPUS_POR_ID = None


def _corpus_por_id():
    """Corpus del RAG indexado por id (cacheado). Vacío si el corpus no está disponible."""
    global _CORPUS_POR_ID
    if _CORPUS_POR_ID is None:
        try:
            from prototipo.explicacion import rag
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


def traza_detalle(ruta, id_decision, indice=None):
    regs = _registros_cacheados(ruta)
    # Los id_decision se repiten si se relanzó el daemon sobre la misma traza. Con `indice` (la
    # posición que la fila conoce, ver lista_trazas) se toma ESE registro si es del id pedido; si no,
    # la última coincidencia, que es la vigente.
    hallado = None
    if indice is not None and 0 <= indice < len(regs) and regs[indice].get("id_decision") == id_decision:
        hallado = regs[indice]
    else:
        for r in regs:
            # Las actualizaciones de caso comparten el id_decision de la decisión; en el fallback (sin
            # índice o desfasado) solo interesa la DECISIÓN, no un `actualizacion_caso`/reversión que
            # no trae justificacion/ejecucion. Se saltan los que no son decisión.
            if r.get("id_decision") == id_decision and r.get("tipo") in (None, "decision"):
                hallado = r
    return _hidratar_pasajes(dict(hallado), _corpus_por_id()) if hallado is not None else None


def verificar_traza(ruta):
    regs = _registros_cacheados(ruta)
    v = traza.verificar(regs)
    return {"ok": v["valida"], "roto_en": v["primer_fallo"], "motivo": v["motivo"], "n": v["n"]}


_TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
          ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json",
          ".ico": "image/x-icon", ".png": "image/png", ".woff2": "font/woff2", ".woff": "font/woff",
          ".map": "application/json"}
_DIR_ESTATICOS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "visor", "dist")


# Solo estos hostnames son el propio tablero. Ligamos a 127.0.0.1, así que un `Host` u `Origin` con
# otro hostname es un navegador ajeno (ataque entre-sitios) o un DNS-rebinding que apunta a nuestra IP
# con un nombre de dominio del atacante. En ambos casos se rechaza. (El puerto no se compara: el
# hostname basta para distinguir al propio tablero del navegador de evil.com.)
_HOSTS_OK = frozenset({"127.0.0.1", "localhost", "::1"})
_revertir_todo_lock = threading.Lock()  # un solo des-bloqueo en masa a la vez (B2)


def _origen_permitido(origen, puerto_srv):
    """El Origin exacto que puede leer la API: el propio tablero (host loopback Y su puerto) y, solo
    como OPT-IN (`TRIAJE_CORS_DEV=5173`), el visor en desarrollo — con el puerto dev siempre abierto,
    cualquier proceso local podía ligarlo en producción y heredar el CORS. Comparar solo el host (B1)
    dejaba a cualquier página en localhost:<otro> leer y forzar toda la API."""
    try:
        u = urllib.parse.urlsplit(origen)
        if u.scheme not in ("http", "https") or u.hostname not in _HOSTS_OK:
            return False
        # dentro del try: urlsplit valida PEREZOSAMENTE y u.port lanza ValueError con un puerto
        # malformado («:evil», fuera de rango) — el guard niega, no revienta el handler.
        puerto = u.port if u.port is not None else (80 if u.scheme == "http" else 443)
    except ValueError:
        return False
    dev = os.environ.get("TRIAJE_CORS_DEV", "")
    return puerto == puerto_srv or (dev.isdigit() and puerto == int(dev))
_MAX_CUERPO = 64 * 1024   # tope del cuerpo de un POST (anti-DoS por memoria): los legítimos son < 1 KiB


def _host_de(valor):
    """Hostname (sin esquema ni puerto), en minúsculas, de una cabecera Host u Origin. '' si no hay."""
    if not valor:
        return ""
    v = valor.strip().lower()
    if "://" in v:
        v = v.split("://", 1)[1]
    if v.startswith("["):                       # IPv6 entre corchetes: [::1]:puerto -> ::1
        return v[1:v.index("]")] if "]" in v else v[1:]
    return v.split(":", 1)[0]


def _token_de(cabecera):
    """El token de una cabecera 'Authorization: Bearer <token>'; '' si no hay o no es Bearer
    (el esquema es case-insensitive, RFC 6750)."""
    c = (cabecera or "").strip()
    return c[7:].strip() if c[:7].lower() == "bearer " else ""


def autorizado(tokens_validos, cabecera_authorization):
    """Auth OPCIONAL de la consola (#6). `tokens_validos` es el token compartido (str) o la colección
    de tokens válidos (uno por persona, #8). Vacío/None -> True (consola abierta, como hoy). Si hay
    tokens, exige 'Bearer <token>' con uno de ellos (compare_digest sobre bytes: tiempo constante y
    admite no-ASCII sin reventar)."""
    if isinstance(tokens_validos, str):
        tokens_validos = [tokens_validos]
    tokens = [t for t in (tokens_validos or []) if t]
    if not tokens:
        return True
    presentado = _token_de(cabecera_authorization)
    if not presentado:
        return False
    pb = presentado.encode("utf-8")
    return any(hmac.compare_digest(pb, t.encode("utf-8")) for t in tokens)


def operador_de(operadores, cabecera_authorization):
    """El operador que identifica el token presentado (no repudio, #8), o None. `operadores` mapea
    token->nombre: un token por persona da atribución real; el token compartido simple no mapea."""
    if not isinstance(operadores, dict):
        return None
    return operadores.get(_token_de(cabecera_authorization)) or None


def resolver_operador(operadores, cabecera_authorization, cuerpo):
    """Quién firma la acción (no repudio, #8). CON mapa de operadores, SOLO el token identifica:
    el campo `operador` del cuerpo es falseable, y aceptarlo dejaba al usuario del token compartido
    atribuir su veredicto a cualquier nombre (M5). Sin mapa (None o VACÍO: construir_web normaliza
    la config ausente/ilegible a {}), se cae al cuerpo (compat con la consola abierta), acotado."""
    if isinstance(operadores, dict) and operadores:
        return operador_de(operadores, cabecera_authorization)
    del_cuerpo = cuerpo.get("operador") if isinstance(cuerpo, dict) else None
    # Una sola regla de saneo/tope para el nombre del operador en toda la cadena (la de casos).
    return (casos._limpiar(str(del_cuerpo), casos._TOPE_CAMPO) or None) if del_cuerpo else None


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):        # silencioso: el daemon ya imprime lo suyo
        pass

    def _host_ok(self):
        # Anti DNS-rebinding: el navegador manda el hostname que escribió el usuario; si no es el
        # propio tablero (localhost), la petición viene de un dominio ajeno que resuelve a nuestra IP.
        return _host_de(self.headers.get("Host")) in _HOSTS_OK

    def _auth_ok(self):
        # Auth opcional (#6): válido = el token compartido Y cualquiera del mapa de operadores (#8),
        # para que un token por persona autentique y además atribuya. Sin ninguno, consola abierta.
        s = self.server
        ops = getattr(s, "operadores", None)
        claves = list(ops.keys()) if isinstance(ops, dict) else []
        return autorizado([getattr(s, "token", None), *claves], self.headers.get("Authorization"))

    def _origen_ok(self):
        # Anti-CSRF para las acciones: un POST desde el navegador SIEMPRE trae Origin; si viene de un
        # sitio que no es localhost, es una web de terceros forzando una acción. Sin Origin = cliente
        # no-navegador (curl, la propia herramienta): no es el vector entre-sitios, se permite.
        o = self.headers.get("Origin")
        return o is None or _origen_permitido(o, self.server.server_address[1])

    def _cors(self):
        # NO '*': se refleja el Origin solo si es el propio tablero (su host loopback Y su puerto,
        # más el visor en dev :5173). Así ni una web de terceros ni otra página LOCAL en otro
        # puerto (B1) puede LEER las respuestas de la API (fuga del estado del SOC).
        o = self.headers.get("Origin")
        if o and _origen_permitido(o, self.server.server_address[1]):
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            # El visor ancla el SLA a la hora del daemon (cabecera Date): en dev (origen :5173) el
            # navegador solo deja leerla si se expone explícitamente.
            self.send_header("Access-Control-Expose-Headers", "Date")

    def do_OPTIONS(self):
        if not self._host_ok():
            return self._responder({"error": "host no permitido"}, 403)
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
        if not self._host_ok():
            return self._responder({"error": "host no permitido"}, 403)
        # La API va protegida; los estáticos no, para que la SPA cargue y pida el token al operador.
        if self.path.startswith("/api/") and not self._auth_ok():
            return self._responder({"error": "no autorizado"}, 401)
        s = self.server
        ruta = self.path.split("?", 1)[0]
        try:
            if ruta == "/api/pausa":   # estado del kill switch (#8)
                return self._responder({"pausada": s.estado.pausada()})
            if ruta == "/healthz":    # salud del PROPIO daemon (#5), distinto de /api/salud (servicios del cliente)
                return self._responder(s.latido.estado() if s.latido
                                       else {"ok": True, "alertas": 0, "lazo_quietud_s": 0.0, "ingesta_silencio_s": None})
            if ruta == "/api/salud":
                return self._responder(estado_salud(leer_salud(ejecutar=s.salud_ejecutar, **s.salud),
                                                    s.dependencias))
            if ruta == "/api/red":
                salud = estado_salud(leer_salud(ejecutar=s.salud_ejecutar, **s.salud), s.dependencias)
                regs = _registros_cacheados(s.ruta_traza)
                pend = s.estado.decisiones_pendientes() if getattr(s, "async_web", False) else []
                return self._responder(estado_red(s.perfil, regs, pend, salud))
            if ruta == "/api/decisiones":
                return self._responder(lista_trazas(s.ruta_traza, n=50, perfil=s.perfil))
            if ruta == "/api/pendientes":
                if getattr(s, "async_web", False):     # cola no bloqueante: lista ordenada por severidad
                    return self._responder([_vista_pendiente(p) for p in s.estado.decisiones_pendientes()])
                return self._responder(s.estado.pendientes())
            if ruta == "/api/trazas":
                return self._responder(lista_trazas(s.ruta_traza, n=_limite(self.path), perfil=s.perfil))
            if ruta.startswith("/api/traza/"):
                d = traza_detalle(s.ruta_traza, ruta[len("/api/traza/"):], indice=_entero(self.path, "indice"))
                return self._responder(d) if d is not None else self._responder({"error": "no encontrada"}, 404)
            if ruta == "/api/consola":    # feed vivo del daemon (vista «Consola»), incremental
                hasta, lineas = s.estado.consola(desde=_entero(self.path, "desde") or 0)
                return self._responder({"hasta": hasta, "lineas": lineas})
            if ruta.startswith("/api/caso/"):
                # Ciclo de caso plegado sobre el fichero COMPLETO (como /api/metricas): el caso no
                # «rejuvenece» cuando sus actualizaciones salen de la ventana de /api/trazas.
                idd = urllib.parse.unquote(ruta[len("/api/caso/"):])
                c = casos.estado_de_casos(_registros_cacheados(s.ruta_traza)).get(idd)
                return self._responder(c or {"estado": "nuevo", "asignado": None, "notas": []})
            if ruta == "/api/verificar":
                return self._responder(verificar_traza(s.ruta_traza))
            if ruta == "/api/contenciones":
                from prototipo.accion import contenciones
                return self._responder(contenciones.activas(_registros_cacheados(s.ruta_traza), s.catalogo))
            if ruta == "/api/metricas":
                desde, hasta = _fecha(self.path, "desde"), _fecha(self.path, "hasta")
                # El informe (con periodo) agrega TODAS las trazas; las métricas en vivo, la ejecución actual.
                regs = _registros_periodo(s.ruta_traza) if (desde or hasta) else _registros_cacheados(s.ruta_traza)
                return self._responder(metricas(regs, desde=desde, hasta=hasta))
            if ruta.startswith("/api/"):
                return self._responder({"error": "no encontrado"}, 404)
            return self._servir_archivo(ruta)          # el build de React (index.html + assets/)
        except Exception as e:            # nunca tumbar el servidor por un handler
            # B5: el detalle de la excepción va al stderr del operador, no al cliente HTTP.
            print(f"[aviso] tablero: error interno en {self.path}: {type(e).__name__}: {e}", file=sys.stderr)
            return self._responder({"error": "error interno"}, 500)

    def do_POST(self):
        # Guardia de seguridad ANTES de resolver nada (el POST ejecuta una contención real): Host del
        # propio tablero (anti-rebinding) y Origin de confianza (anti-CSRF entre-sitios).
        if not self._host_ok():
            return self._responder({"error": "host no permitido"}, 403)
        if not self._origen_ok():
            return self._responder({"error": "origen no permitido"}, 403)
        if not self._auth_ok():        # un POST ejecuta una contención real: exige auth si hay token
            return self._responder({"error": "no autorizado"}, 401)
        try:
            s = self.server
            ruta = self.path.split("?", 1)[0]
            if ruta not in ("/api/aprobar", "/api/pausa", "/api/revertir-todo", "/api/caso"):
                return self._responder({"error": "no encontrado"}, 404)
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._responder({"error": "Content-Length invalido"}, 400)
            # Un Content-Length NEGATIVO no es > max y haría `rfile.read(n<0)` leer hasta EOF (sin
            # tope): se rechaza explícitamente. Los cuerpos legítimos (id/respuesta/paso) son < 1 KiB.
            if not 0 <= n <= _MAX_CUERPO:
                return self._responder({"error": "Content-Length fuera de rango"}, 413)
            cuerpo = json.loads(self.rfile.read(n) or b"{}")
            operador = resolver_operador(getattr(s, "operadores", None),
                                         self.headers.get("Authorization"), cuerpo)
            if ruta == "/api/pausa":      # kill switch (#8): fija la pausa global de la automatización
                return self._responder({"pausada": s.estado.pausar(bool(cuerpo.get("pausar")),
                                                                   operador=operador)})
            if ruta == "/api/revertir-todo":   # des-bloqueo en masa (#8)
                # B2: levanta TODOS los bloqueos del atacante — exige el gesto explícito
                # (`confirmar`) y solo UNO a la vez (dos concurrentes duplicaban los iptables -D).
                if (cuerpo.get("confirmar") if isinstance(cuerpo, dict) else None) is not True:
                    return self._responder({"error": "falta confirmar: true"}, 400)
                if not _revertir_todo_lock.acquire(blocking=False):
                    return self._responder({"error": "ya hay un des-bloqueo en curso"}, 409)
                try:
                    from prototipo.accion import revertir, conector
                    ejecutor = getattr(s, "ejecutor", None) or conector.ejecutor_por_defecto()
                    res = revertir.revertir_todas(s.ruta_traza, s.catalogo, ejecutor,
                                                  motivo="des-bloqueo en masa (kill switch)",
                                                  operador=operador)
                finally:
                    _revertir_todo_lock.release()
                # narración en la Consola (caja negra): el kill switch también deja su línea
                s.estado.anotar_linea(f"↶ des-bloqueo en masa: {res.get('revertidas', 0)} revertida(s), "
                                      f"{res.get('fallidas', 0)} fallida(s)"
                                      + (f" · por {operador}" if operador else ""))
                return self._responder(res)
            if ruta == "/api/caso":   # ciclo de vida del caso: añade un `actualizacion_caso` a la cadena
                try:
                    ok = s.estado.actualizar_caso(cuerpo.get("id"), estado=cuerpo.get("estado"),
                                                  asignado=cuerpo.get("asignado"), nota=cuerpo.get("nota"),
                                                  operador=operador)
                except ValueError as e:
                    return self._responder({"error": str(e)}, 400)   # estado inválido o actualización vacía
                if ok:   # el ciclo de caso también es diario del operador (anotar_linea sanea B3)
                    partes = [f"estado → {cuerpo.get('estado')}" if cuerpo.get("estado") else None,
                              f"asignado a {cuerpo.get('asignado')}" if cuerpo.get("asignado") else None,
                              "nota añadida" if cuerpo.get("nota") else None,
                              f"por {operador}" if operador else None]
                    s.estado.anotar_linea(f"☰ {cuerpo.get('id')} caso: "
                                          + " · ".join(p for p in partes if p))
                return self._responder({"ok": True}) if ok else self._responder({"error": "no disponible en este modo"}, 409)
            pid, resp = str(cuerpo.get("id")), str(cuerpo.get("respuesta", ""))
            # cola no bloqueante -> el resolutor del daemon ejecuta y traza; si no, el lazo bloqueante.
            # `paso` es opcional: solo lo usa la cola (la ruta bloqueante no tiene menús con paso).
            if getattr(s, "async_web", False):
                ok = s.estado.resolver_decision(pid, resp, paso=cuerpo.get("paso"), operador=operador)
            else:
                ok = s.estado.resolver(pid, resp)
            return self._responder({"ok": True}) if ok else self._responder({"error": "pendiente no vigente"}, 409)
        except Exception as e:
            # B5: el detalle de la excepción (rutas, tipos internos) va al stderr del operador,
            # nunca al cliente HTTP.
            print(f"[aviso] tablero: error interno en {self.path}: {type(e).__name__}: {e}", file=sys.stderr)
            return self._responder({"error": "error interno"}, 500)


_INTERNO_PENDIENTE = ("decision", "alerta", "clave", "orden", "desde")   # no se serializan a la web


def _vista_pendiente(p):
    """La vista serializable de una decisión en cola (sin el contexto interno de resolución)."""
    alerta = p.get("alerta") or {}
    return {**{k: v for k, v in p.items() if k not in _INTERNO_PENDIENTE},
            "activo": alerta.get("activo"), "origen_ip": alerta.get("origen_ip")}


def crear_servidor(estado, ruta_traza, salud=None, dependencias=None, estaticos=None,
                   puerto=8787, salud_ejecutar=subprocess.run, activos=None, topologia=None,
                   async_web=False, perfil=None, catalogo=None, latido=None, ejecutor=None,
                   token=None, operadores=None):
    """ThreadingHTTPServer ligado SOLO a 127.0.0.1. `salud` es {} o {ruta} o {contenedor,
    fichero_en_contenedor}. `async_web` activa la cola de aprobación no bloqueante. `token` (opcional,
    #6): si se da, toda la API exige 'Authorization: Bearer <token>'; `operadores` (token->nombre, #8)
    da no repudio. Guarda la config en atributos del servidor."""
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), _Manejador)
    srv.estado = estado
    srv.ruta_traza = ruta_traza
    srv.salud = salud or {}
    srv.dependencias = dependencias or {}
    srv.estaticos = estaticos or _DIR_ESTATICOS
    srv.salud_ejecutar = salud_ejecutar
    srv.async_web = async_web
    srv.perfil = perfil or {"activos": activos or {}, "topologia": topologia or {}}
    srv.catalogo = catalogo or {}        # para reconstruir las contenciones activas (#4)
    srv.latido = latido                  # salud del propio daemon para /healthz (#5)
    srv.ejecutor = ejecutor              # el ejecutor del daemon, para el des-bloqueo en masa (#8)
    srv.token = token                    # auth opcional de la consola (#6): None = abierta
    srv.operadores = operadores or {}    # token->operador para el no repudio (#8)
    return srv
