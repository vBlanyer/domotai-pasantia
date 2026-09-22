"""Tablero web de observabilidad y aprobacion del prototipo (solo biblioteca estandar).

Este fichero NO importa nada de lab/: la salud se lee como JSONL generico y las dependencias
llegan desde el perfil. Contiene el estado compartido y la costura de aprobacion (Task 1), los
lectores de datos (Task 2) y el servidor HTTP (Task 3).
"""
import itertools
import threading

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
