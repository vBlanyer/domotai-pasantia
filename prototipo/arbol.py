"""Árbol de decisión (CART, impureza de Gini) en biblioteca estándar.

Por qué un árbol y no un codificador con ajuste fino: con unos cientos de filas, un modelo grande
memoriza y no se puede validar sin fuga; un árbol de profundidad acotada se entrena en
milisegundos, se imprime como reglas y se puede leer al lado de las cinco reglas escritas a mano
del clasificador determinista. Es la escala honesta para este conjunto de datos, y produce un
resultado que un analista puede auditar: la decisión sigue siendo un camino de condiciones.

Rasgos: numericos (umbral <=) o categoricos (igualdad). Sin dependencias.
"""
from collections import Counter


def _gini(conteo, n):
    return 1.0 - sum((c / n) ** 2 for c in conteo.values()) if n else 0.0


def _mejor_corte(filas, rasgos, etiqueta, min_hoja):
    """(rasgo, tipo, valor, ganancia) del corte que mas reduce la impureza, o None."""
    n = len(filas)
    base = _gini(Counter(f[etiqueta] for f in filas), n)
    mejor = None
    for rasgo in rasgos:
        valores = [f.get(rasgo) for f in filas]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valores):
            candidatos = sorted(set(valores))
            cortes = [("num", (a + b) / 2) for a, b in zip(candidatos, candidatos[1:])]
        else:
            cortes = [("cat", v) for v in sorted(set(valores), key=str)]
        for tipo, valor in cortes:
            izq = [f for f in filas if _va_izq(f.get(rasgo), tipo, valor)]
            der = [f for f in filas if not _va_izq(f.get(rasgo), tipo, valor)]
            if len(izq) < min_hoja or len(der) < min_hoja:
                continue
            impureza = (len(izq) * _gini(Counter(f[etiqueta] for f in izq), len(izq))
                        + len(der) * _gini(Counter(f[etiqueta] for f in der), len(der))) / n
            ganancia = base - impureza
            if ganancia > 1e-12 and (mejor is None or ganancia > mejor[3]):
                mejor = (rasgo, tipo, valor, ganancia)
    return mejor


def _va_izq(v, tipo, valor):
    return (v is not None and v <= valor) if tipo == "num" else (v == valor)


def _hoja(filas, etiqueta):
    dist = Counter(f[etiqueta] for f in filas)
    return {"hoja": True, "clase": dist.most_common(1)[0][0], "n": len(filas), "dist": dict(dist)}


def entrenar(filas, rasgos, etiqueta="etiqueta", max_prof=4, min_hoja=3, _prof=0):
    """Devuelve el arbol como dicts anidados. Para si es puro, si no cabe otro corte, o en max_prof."""
    dist = Counter(f[etiqueta] for f in filas)
    if len(dist) == 1 or _prof >= max_prof or len(filas) < 2 * min_hoja:
        return _hoja(filas, etiqueta)
    corte = _mejor_corte(filas, rasgos, etiqueta, min_hoja)
    if corte is None:
        return _hoja(filas, etiqueta)
    rasgo, tipo, valor, _ = corte
    izq = [f for f in filas if _va_izq(f.get(rasgo), tipo, valor)]
    der = [f for f in filas if not _va_izq(f.get(rasgo), tipo, valor)]
    return {"hoja": False, "rasgo": rasgo, "tipo": tipo, "valor": valor, "n": len(filas),
            "izq": entrenar(izq, rasgos, etiqueta, max_prof, min_hoja, _prof + 1),
            "der": entrenar(der, rasgos, etiqueta, max_prof, min_hoja, _prof + 1)}


def predecir(nodo, fila):
    while not nodo["hoja"]:
        nodo = nodo["izq"] if _va_izq(fila.get(nodo["rasgo"]), nodo["tipo"], nodo["valor"]) else nodo["der"]
    return nodo["clase"]


def _cond(nodo, lado):
    if nodo["tipo"] == "num":
        return f"{nodo['rasgo']} {'<=' if lado == 'izq' else '>'} {nodo['valor']:g}"
    return f"{nodo['rasgo']} {'==' if lado == 'izq' else '!='} {nodo['valor']!r}"


def a_texto(nodo, _sangria=""):
    """El arbol como reglas legibles, con el tamano y la distribucion de cada hoja."""
    if nodo["hoja"]:
        return f"{_sangria}-> {nodo['clase']}  (n={nodo['n']}, {nodo['dist']})\n"
    return (f"{_sangria}si {_cond(nodo, 'izq')}:\n" + a_texto(nodo["izq"], _sangria + "    ")
            + f"{_sangria}si no ({_cond(nodo, 'der')}):\n" + a_texto(nodo["der"], _sangria + "    "))


def profundidad(nodo):
    return 0 if nodo["hoja"] else 1 + max(profundidad(nodo["izq"]), profundidad(nodo["der"]))
