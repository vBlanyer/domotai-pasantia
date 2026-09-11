"""Ráfaga: cuántas alertas del mismo origen en una ventana de tiempo.

Es el rasgo que las cinco reglas del clasificador no tenían y que el clasificador entrenado
(evaluacion/entrenado.py) señaló como el único con evidencia fuerte: una ráfaga es un ataque
venga de donde venga, también desde la dirección declarada del administrador, que puede estar
suplantada o comprometida. Se calcula aquí, fuera del clasificador, y viaja en la alerta
normalizada como el campo estructurado `rafaga_60s` (RNF-08: es un conteo, no texto libre).

Dos formas de calcularlo: sobre un lote cerrado (la campaña de evaluación, con todas las alertas
del dataset a la vista) y en línea (el servicio en tiempo real, con una ventana deslizante por
origen que avanza con el reloj de las propias alertas).
"""
import collections
import datetime

VENTANA_S = 60
CAMPO = "rafaga_60s"


def _instante(alerta):
    t = (alerta.get("timestamp") or "")[:19]
    try:
        return datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def contar_en_lote(alertas, ventana_s=VENTANA_S):
    """Anota en cada alerta cuantas del mismo origen hay a menos de `ventana_s` segundos (ella
    incluida), mirando hacia atras y hacia delante: en un lote cerrado se conoce toda la rafaga."""
    por_origen = collections.defaultdict(list)
    for a in alertas:
        if a.get("origen_ip"):
            por_origen[a["origen_ip"]].append(a)
    for a in alertas:
        t = _instante(a)
        vecinas = por_origen.get(a.get("origen_ip"), [a])
        if t is None:
            a[CAMPO] = 1
            continue
        a[CAMPO] = sum(1 for g in vecinas if _instante(g) is not None
                       and abs((_instante(g) - t).total_seconds()) <= ventana_s)
    return alertas


class Ventana:
    """Ventana deslizante por origen para el servicio en tiempo real. `registrar` anota una alerta
    y `contar` dice cuantas del origen quedan dentro de la ventana; el tiempo es el de las
    alertas, no el de pared, para que una repeticion de la traza cuente lo mismo (RNF-03)."""
    def __init__(self, ventana_s=VENTANA_S):
        self.ventana_s = ventana_s
        self._por_origen = collections.defaultdict(collections.deque)

    def registrar(self, alerta):
        origen, t = alerta.get("origen_ip"), _instante(alerta)
        if not origen or t is None:
            return 1
        cola = self._por_origen[origen]
        cola.append(t)
        self._purgar(cola, t)
        return len(cola)

    def contar(self, origen, ahora=None):
        cola = self._por_origen.get(origen)
        if not cola:
            return 0
        self._purgar(cola, ahora or cola[-1])
        return len(cola)

    def _purgar(self, cola, ahora):
        while cola and (ahora - cola[0]).total_seconds() > self.ventana_s:
            cola.popleft()
