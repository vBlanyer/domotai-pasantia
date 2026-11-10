"""Memoria de fallos por equipo (fase 5 de documentacion/05-fase5-implementacion-del-prototipo/plan-manejo-fallos-contencion.md). Interruptor
TRIAJE_MEMORIA_FALLOS=1, apagado por defecto.

Para qué: que 25 alertas seguidas contra un equipo inalcanzable no paguen 25 veces la espera. Riesgo: que
esconda que un atacante dejó al SOC sin acceso. Por eso solo ACELERA (no se intenta en el equipo: se escala
desde el principio o queda como fallo a la vista del analista) y SUBE la alerta (una por equipo, que se
actualiza); nunca calla nada.

Reglas:
- Solo F4 (el equipo no acepta la clave del conector) y F5 (inalcanzable). F3, F6, F7 y F8 NUNCA la abren:
  F3 y F8 pueden ser un ataque y se quieren ver en cada intento; F6 y F7 entraron en el equipo.
- Se abre tras 3 fallos seguidos del mismo equipo en 5 minutos. Cualquier otra clase o un éxito cortan la
  racha.
- Abierta, se sondea el equipo cada 60 s con un comando inocuo; al primer acceso se cierra y se anota.
"""
import threading
import time
from datetime import datetime, timezone

CLASES = ("F4", "F5")
UMBRAL, VENTANA_S, SONDEO_S = 3, 300, 60

_lock = threading.Lock()
_rachas = {}        # ip -> [instantes monotónicos de fallos F4/F5 seguidos]
_abiertas = {}      # ip -> {desde, clase, fallos, regresion, ultimo_sondeo, _t}
_cerradas = []      # las últimas cerradas: {ip, desde, hasta}
_aviso = None       # fn(texto) para la consola del daemon


def configurar_aviso(fn):
    global _aviso
    _aviso = fn


def _avisar(texto):
    if _aviso:
        try:
            _aviso(texto)
        except Exception:
            pass


def _hora(iso):
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%H:%M")
    except (TypeError, ValueError):
        return "?"


def _ahora_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def registrar(ip, causa, ahora=None):
    """Resultado de una contención real en `ip` (causa None = contenida y verificada ahí)."""
    if not ip:
        return
    t = time.monotonic() if ahora is None else ahora
    abierta = None
    with _lock:
        clase = (causa or {}).get("clase")
        if clase not in CLASES:
            _rachas.pop(ip, None)          # otra clase o un éxito: se corta la racha
            if causa is None and ip in _abiertas:
                cerrada = _cerrar(ip)
            else:
                cerrada = None
        else:
            cerrada = None
            racha = [x for x in _rachas.get(ip, []) if t - x <= VENTANA_S] + [t]
            _rachas[ip] = racha
            if ip in _abiertas:
                _abiertas[ip]["fallos"] += 1
            elif len(racha) >= UMBRAL:
                _abiertas[ip] = abierta = {"desde": _ahora_iso(), "clase": clase, "fallos": len(racha),
                                           "regresion": bool((causa or {}).get("regresion")),
                                           "ultimo_sondeo": None, "_t": t}
    if abierta:
        _avisar(f"[aviso] el MDR no tiene acceso a {ip} desde las {_hora(abierta['desde'])} "
                f"({len(_rachas.get(ip, []))} fallos seguidos, {clase}): las contenciones escalan directamente; "
                f"se reprueba cada {SONDEO_S} s")
    if cerrada:
        _avisar(f"[aviso] el MDR recupera el acceso a {ip} (sin acceso desde las {_hora(cerrada['desde'])})")


def _cerrar(ip):
    a = _abiertas.pop(ip)
    _rachas.pop(ip, None)
    c = {"ip": ip, "desde": a["desde"], "hasta": _ahora_iso()}
    _cerradas.append(c)
    del _cerradas[:-20]
    return c


def abierta(ip):
    """{clase, desde, regresion, …} si el MDR no tiene acceso a `ip`; None si se intenta como siempre."""
    with _lock:
        a = _abiertas.get(ip)
        return {k: v for k, v in a.items() if not k.startswith("_")} if a else None


def estado():
    with _lock:
        return {ip: {k: v for k, v in a.items() if not k.startswith("_")} for ip, a in _abiertas.items()}


def por_sondear(ahora=None):
    """Las IPs abiertas cuyo último sondeo (o apertura) fue hace SONDEO_S o más."""
    t = time.monotonic() if ahora is None else ahora
    with _lock:
        return [ip for ip, a in _abiertas.items() if t - a["_t"] >= SONDEO_S]


def sondeo(ip, entro, ahora=None):
    """Resultado del sondeo inocuo: si entró, se cierra; si no, se anota cuándo se probó."""
    t = time.monotonic() if ahora is None else ahora
    cerrada = None
    with _lock:
        if ip not in _abiertas:
            return
        if entro:
            cerrada = _cerrar(ip)
        else:
            _abiertas[ip].update(ultimo_sondeo=_ahora_iso(), _t=t)
    if cerrada:
        _avisar(f"[aviso] el MDR recupera el acceso a {ip} (sin acceso desde las {_hora(cerrada['desde'])})")


def reiniciar():
    """Para las pruebas."""
    with _lock:
        _rachas.clear()
        _abiertas.clear()
        _cerradas.clear()
