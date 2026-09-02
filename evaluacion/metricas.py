"""Funciones puras de medición para la Fase 6. No conocen el motor ni Wazuh."""
import math

def _div(a, b):
    return a / b if b else "n/d"

def matriz(pred, verdad):
    vp = fp = vn = fn = 0
    for p, v in zip(pred, verdad):
        if p and v: vp += 1
        elif p and not v: fp += 1
        elif not p and not v: vn += 1
        else: fn += 1
    return {"vp": vp, "fp": fp, "vn": vn, "fn": fn}

def precision(m): return _div(m["vp"], m["vp"] + m["fp"])
def recall(m):    return _div(m["vp"], m["vp"] + m["fn"])
def tasa_fp(m):   return _div(m["fp"], m["fp"] + m["vn"])

def f1(m):
    p, r = precision(m), recall(m)
    if p == "n/d" or r == "n/d" or (p + r) == 0:
        return "n/d"
    return 2 * p * r / (p + r)

def cobertura(clases):
    if not clases: return 0.0
    return sum(1 for c in clases if c != "no_soportada") / len(clases)

def tasa(bools):
    if not bools: return 0.0
    return sum(1 for b in bools if b) / len(bools)

def acierto_prioridad(pred_prio, esp_prio):
    if not pred_prio: return "n/d"
    return sum(1 for p, e in zip(pred_prio, esp_prio) if abs(p - e) <= 1) / len(pred_prio)

def _rangos(xs):
    orden = sorted(range(len(xs)), key=lambda i: xs[i])
    rang = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[orden[j + 1]] == xs[orden[i]]:
            j += 1
        promedio = (i + j) / 2 + 1  # rango 1-based, promediado en empates
        for k in range(i, j + 1):
            rang[orden[k]] = promedio
        i = j + 1
    return rang

def spearman(a, b):
    n = len(a)
    if n < 2: return "n/d"
    ra, rb = _rangos(a), _rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = math.sqrt(sum((ra[i] - ma) ** 2 for i in range(n)))
    db = math.sqrt(sum((rb[i] - mb) ** 2 for i in range(n)))
    if da == 0 or db == 0: return "n/d"
    return num / (da * db)

def continuidad(registros):
    disruptivas = [r for r in registros
                   if r["impacto"] == "alcanza_servicio" and r["etiqueta"] == "FP"]
    retenidas = sum(1 for r in disruptivas if r["requiere_humano"])
    return {"disruptivas_indebidas": len(disruptivas),
            "retencion_correcta": _div(retenidas, len(disruptivas))}
