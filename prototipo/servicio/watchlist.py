"""Watchlist / IoC local: lista de indicadores (IP o CIDR) que el analista marca como malos. Es una
capa de ANOTACIÓN del analista (como los casos), NO entra en el motor: no cambia ninguna decisión ni
las métricas. El visor la consume para marcar los orígenes que coinciden.

Persistencia simple: un fichero JSON (lista de entradas) con escritura atómica y un lock de proceso.
Cada entrada: {indicador, nota, operador, agregado_en}."""
import ipaddress
import json
import os
import threading

_LOCK = threading.Lock()
_TOPE_NOTA = 200


def _valido(indicador):
    """¿`indicador` es una IP o un CIDR parseables? (RNF-07: no se adivina)."""
    try:
        if "/" in indicador:
            ipaddress.ip_network(indicador, strict=False)
        else:
            ipaddress.ip_address(indicador)
        return True
    except ValueError:
        return False


def cargar(ruta):
    """La lista de entradas, o [] si el fichero no existe o está corrupto."""
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (FileNotFoundError, ValueError, OSError):
        return []


def _guardar(ruta, entradas):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entradas, f, ensure_ascii=False)
    os.replace(tmp, ruta)                 # reemplazo atómico


def agregar(ruta, indicador, nota="", operador=None, ts=None):
    """Añade un indicador (IP o CIDR) a la watchlist. Lanza ValueError si no es válido. Deduplica.
    Devuelve la lista resultante."""
    indicador = (indicador or "").strip()
    if not _valido(indicador):
        raise ValueError("el indicador no es una IP o un CIDR válido")
    with _LOCK:
        ent = cargar(ruta)
        if any(e.get("indicador") == indicador for e in ent):
            return ent
        ent.append({"indicador": indicador, "nota": (nota or "").strip()[:_TOPE_NOTA],
                    "operador": operador, "agregado_en": ts})
        _guardar(ruta, ent)
        return ent


def quitar(ruta, indicador):
    """Retira `indicador` de la watchlist. Devuelve la lista resultante."""
    with _LOCK:
        ent = [e for e in cargar(ruta) if e.get("indicador") != indicador]
        _guardar(ruta, ent)
        return ent
