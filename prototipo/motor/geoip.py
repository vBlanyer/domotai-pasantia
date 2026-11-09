"""Bases de datos de IPs, OFFLINE: el MDR no consulta ningún servicio externo.

Dos bases, cada una un CSV (también .csv.gz) que DB-IP publica cada mes con licencia CC BY 4.0:

- **país** (`TRIAJE_GEOIP`, «IP to Country Lite»): `inicio,fin,país`. El nombre en español y el punto
  en el mapa de cada país salen de `corpus/paises.json`.
- **ASN** (`TRIAJE_ASN`, «IP to ASN Lite»): `inicio,fin,número_AS,organización`.

Sin base no se inventa nada: la IP sale sin país o sin organización, y la consola lo dice. La
búsqueda es binaria sobre los rangos ordenados; IPv4 se guarda en arrays compactos.
"""
import bisect
import csv
import gzip
import json
import os
import socket
import threading
from array import array

VARIABLE = {"pais": "TRIAJE_GEOIP", "asn": "TRIAJE_ASN"}
FORMATO = {"pais": "inicio,fin,país", "asn": "inicio,fin,número_AS,organización"}

_PAISES = None
_CARGADAS = {}          # tipo -> (ruta, Base)
_ERRORES = {}           # tipo -> (ruta, motivo)
_CERROJO = threading.Lock()


def _a_entero(ip):
    """(familia, entero) de una IP en texto, o None."""
    for fam, n in ((socket.AF_INET, 4), (socket.AF_INET6, 6)):
        try:
            return n, int.from_bytes(socket.inet_pton(fam, ip.strip()), "big")
        except (OSError, ValueError, AttributeError):
            continue
    return None


def _valor_pais(fila):
    cc = fila[2].strip().upper()
    return cc if len(cc) == 2 and cc.isalpha() and cc != "ZZ" else None


def _valor_asn(fila):
    numero = fila[2].strip()
    if not numero.isdigit():
        return None
    asn = f"AS{numero}"
    org = fila[3].strip() if len(fila) > 3 else ""
    return (asn, org or asn)


_VALOR = {"pais": _valor_pais, "asn": _valor_asn}


class Base:
    def __init__(self, filas, tipo="pais", fuente="csv"):
        # Directo a arrays, sin listas intermedias: las bases de DB-IP vienen ordenadas (cientos de
        # miles de filas). Si no lo estuvieran, se ordena al final. Los valores repetidos se comparten.
        valor_de = _VALOR[tipo]
        v4 = (array("L"), array("L"), [])
        v6 = ([], [], [])
        unicos = {}
        for fila in filas:
            if len(fila) < 3:
                continue
            ini, fin, valor = _a_entero(fila[0]), _a_entero(fila[1]), valor_de(fila)
            if not ini or not fin or ini[0] != fin[0] or valor is None:
                continue
            destino = v4 if ini[0] == 4 else v6
            destino[0].append(ini[1])
            destino[1].append(fin[1])
            destino[2].append(unicos.setdefault(valor, valor))
        self._v4 = _ordenado(*v4, tipo="L")
        self._v6 = _ordenado(*v6, tipo=None)
        self.rangos = len(self._v4[0]) + len(self._v6[0])
        self.tipo, self.fuente = tipo, fuente

    def buscar(self, ip):
        """El valor del rango que contiene `ip` (código de país, o (AS, organización)), o None."""
        e = _a_entero(ip) if isinstance(ip, str) else None
        if not e:
            return None
        ini, fin, val = self._v4 if e[0] == 4 else self._v6
        i = bisect.bisect_right(ini, e[1]) - 1
        return val[i] if i >= 0 and e[1] <= fin[i] else None


def _ordenado(ini, fin, val, tipo):
    if all(ini[i] <= ini[i + 1] for i in range(len(ini) - 1)):
        return ini, fin, val
    orden = sorted(range(len(ini)), key=ini.__getitem__)
    nuevo = (lambda xs: array(tipo, xs)) if tipo else list
    return nuevo(ini[i] for i in orden), nuevo(fin[i] for i in orden), [val[i] for i in orden]


def leer(ruta, tipo="pais"):
    """Carga la base de `ruta` (.csv o .csv.gz). ValueError si no trae ningún rango válido."""
    abrir = gzip.open if ruta.endswith(".gz") else open
    with abrir(ruta, "rt", encoding="utf-8", newline="") as f:
        b = Base(csv.reader(f), tipo, fuente="dbip" if "dbip" in os.path.basename(ruta) else "csv")
    if not b.rangos:
        raise ValueError(f"{ruta}: no tiene ningún rango «{FORMATO[tipo]}» válido")
    return b


def base(tipo="pais"):
    """La base del tipo, cargada una vez de su variable; None si no está configurada o no se lee."""
    ruta = os.environ.get(VARIABLE[tipo])
    if not ruta:
        return None
    with _CERROJO:
        cargada, error = _CARGADAS.get(tipo), _ERRORES.get(tipo)
        if cargada and cargada[0] == ruta:
            return cargada[1]
        if error and error[0] == ruta:
            return None
        try:
            b = leer(ruta, tipo)
        except (OSError, ValueError, EOFError, csv.Error) as e:
            _CARGADAS.pop(tipo, None)
            _ERRORES[tipo] = (ruta, f"{ruta}: {e}")
            return None
        _CARGADAS[tipo] = (ruta, b)
        _ERRORES.pop(tipo, None)
        return b


def estado(tipo="pais"):
    """{configurada, ruta, rangos, fuente, error} para el arranque y la consola."""
    ruta = os.environ.get(VARIABLE[tipo])
    b = base(tipo)
    error = _ERRORES.get(tipo)
    return {"configurada": b is not None, "ruta": ruta, "rangos": b.rangos if b else 0,
            "fuente": b.fuente if b else None,
            "error": error[1] if (error and error[0] == ruta) else None}


def reiniciar():
    """Olvida las bases cargadas (tests, o tras instalar una nueva sin reiniciar el proceso)."""
    with _CERROJO:
        _CARGADAS.clear()
        _ERRORES.clear()


def pais(codigo):
    """{pais, codigo, lat, lon} de un código ISO. Uno que no está en la tabla sale con su código y
    sin punto en el mapa (solo en la tabla de Ubicaciones)."""
    global _PAISES
    if _PAISES is None:
        ruta = os.path.join(os.path.dirname(os.path.dirname(__file__)), "corpus", "paises.json")
        try:
            with open(ruta, encoding="utf-8") as f:
                _PAISES = json.load(f)
        except (OSError, ValueError):
            _PAISES = {}
    p = _PAISES.get(codigo) or {}
    return {"pais": p.get("pais") or codigo, "codigo": codigo, "lat": p.get("lat"), "lon": p.get("lon")}
