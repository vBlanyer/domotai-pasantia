"""Identificadores de decisión estructurados: `PREFIJO-AAAAMMDD-NNNN` (diseno-identificadores-estructurados.md).

`BCO-20261123-0042` dice de qué cliente es (el prefijo del perfil), de qué día (UTC) y su orden en ese día;
no se repite entre ficheros de traza ni entre instalaciones con prefijos distintos. La actividad propia del
MDR lleva su propia secuencia (`BCO-20261123-P0005`) para no dejar huecos en la de las decisiones. Los
derivados conservan su sufijo (`…-0042~sup`, `…-0042~tope`). Las trazas antiguas (`s23`) se siguen leyendo.
"""
import datetime
import re
import threading

from prototipo.motor.perfil import prefijo_id as prefijo_de   # «BCO»; None si falta o no vale

# [PREFIJO-]AAAAMMDD-[P]NNNN[~sufijo]
_ID = re.compile(r"^(?:[A-Z0-9]{1,8}-)?(\d{8})-(P?)(\d{4,})(?:~|$)")


def _hoy_utc():
    return datetime.datetime.now(datetime.timezone.utc)


class Numerador:
    """Da el siguiente id: `siguiente()` para una decisión, `siguiente("P")` para actividad propia. La
    secuencia es por día (UTC) y por tipo, y vuelve a 1 al cambiar de día. Con lock: el lazo y los hilos del
    modo agente piden ids a la vez."""

    def __init__(self, prefijo=None, reloj=_hoy_utc, ultimos=None):
        self.prefijo = prefijo
        self._reloj = reloj
        self._ultimos = dict(ultimos or {})          # (AAAAMMDD, tipo) -> último número dado
        self._lock = threading.Lock()

    def siguiente(self, tipo=""):
        with self._lock:
            dia = self._reloj().astimezone(datetime.timezone.utc).strftime("%Y%m%d")
            n = self._ultimos.get((dia, tipo), 0) + 1
            self._ultimos[(dia, tipo)] = n
        cuerpo = f"{dia}-{tipo}{n:04d}"
        return f"{self.prefijo}-{cuerpo}" if self.prefijo else cuerpo


def desde_traza(registros, prefijo=None, reloj=_hoy_utc):
    """Numerador que continúa la traza que se retoma: el mayor número de cada día y tipo (sea cual sea el
    prefijo con que se escribió, para no repetir números si el prefijo cambia a mitad del día). Los ids
    antiguos (`s23`, `p4`) no cuentan: la numeración nueva no choca con ellos."""
    ultimos = {}
    for reg in registros or ():
        m = _ID.match(str((reg or {}).get("id_decision") or ""))
        if m:
            clave = (m.group(1), m.group(2))
            ultimos[clave] = max(ultimos.get(clave, 0), int(m.group(3)))
    return Numerador(prefijo, reloj=reloj, ultimos=ultimos)
