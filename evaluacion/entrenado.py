"""Clasificador entrenado (arbol) frente al determinista, sobre el conjunto etiquetado.

    python3 -m evaluacion.entrenado [--perfil prototipo/perfiles/empresarial.yml] [--prof 4] [--hoja 3]

Rasgos por alerta, SOLO de campos estructurados (RNF-08): los que ya usa el determinista (familia,
origen declarado, postura del activo) mas los que no usa: la regla y el nivel de Wazuh, y tres
rasgos de RAFAGA calculados sobre el flujo de alertas del mismo origen ---cuantas en un minuto,
cuantas reglas distintas, y si hubo un acceso correcto despues---. La direccion de origen NO es
un rasgo: memorizaria direcciones, no comportamientos.

Se entrena en la particion 'entrenamiento' y se mide en 'evaluacion', igual que todo lo demas.
"""
import datetime
import json
import os
import sys

from evaluacion import cargar, metricas
from prototipo import analisis, arbol
from prototipo import perfil as perfilm
from prototipo.postura import postura_de

RASGOS = ["familia", "regla_id", "nivel_wazuh", "servicio", "origen_legitimo", "expuesto",
          "n_origen_60s", "reglas_60s", "nivel_max_60s", "exito_120s"]
REGLAS_EXITO = {"5715", "5501"}      # sshd: acceso correcto; PAM: sesion abierta


def _ts(fila):
    t = (fila.get("timestamp") or "")[:19]
    try:
        return datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def rasgos_rafaga(filas):
    """Anade a cada fila los rasgos de rafaga, calculados sobre TODAS las alertas del mismo origen
    (tambien las no soportadas: el acceso correcto que descarta un error de tecleo es una de ellas)."""
    por_origen = {}
    for f in filas:
        if f.get("origen_ip"):
            por_origen.setdefault(f["origen_ip"], []).append(f)
    for f in filas:
        t, vecinas = _ts(f), por_origen.get(f.get("origen_ip"), [f])   # sin origen: solo ella misma
        if t is None:
            f.update(n_origen_60s=1, reglas_60s=1, nivel_max_60s=f.get("nivel_wazuh") or 0, exito_120s=False)
            continue
        ventana = [g for g in vecinas if _ts(g) and abs((_ts(g) - t).total_seconds()) <= 60]
        despues = [g for g in vecinas if _ts(g) and 0 <= (_ts(g) - t).total_seconds() <= 120]
        f["n_origen_60s"] = len(ventana)
        f["reglas_60s"] = len({g.get("regla_id") for g in ventana})
        f["nivel_max_60s"] = max((g.get("nivel_wazuh") or 0) for g in ventana)
        f["exito_120s"] = any(g.get("regla_id") in REGLAS_EXITO for g in despues)
    return filas


def preparar(filas, perfil, hallazgos):
    """Rasgos estructurados + rafaga. Devuelve las filas soportadas (VP/FP), listas para el arbol."""
    legitimos = set(perfil.get("origenes_legitimos") or [])
    rasgos_rafaga(filas)
    salida = []
    for f in filas:
        if f.get("etiqueta") not in ("VP", "FP"):
            continue
        p = postura_de(hallazgos, f.get("activo"), f.get("servicio"))
        g = dict(f)
        g["origen_legitimo"] = f.get("origen_ip") in legitimos
        g["expuesto"] = bool(p and p.get("expuesto"))
        g["nivel_wazuh"] = f.get("nivel_wazuh") or 0
        salida.append(g)
    return salida


def _metricas(verd, pred):
    m = metricas.matriz(pred, verd)
    return {"matriz": m, "precision": metricas.precision(m), "recall": metricas.recall(m),
            "f1": metricas.f1(m), "tasa_fp": metricas.tasa_fp(m)}


def _determinista(filas, perfil, hallazgos):
    pred = []
    for f in filas:
        ctx = analisis.enriquecer(f, hallazgos, perfil)
        pred.append(analisis.clasificar(f, ctx)["clase"].startswith("vp_"))
    return pred


def experimento(ruta_dataset, perfil, hallazgos, max_prof=4, min_hoja=3):
    todas = cargar.cargar(ruta_dataset, particion=None)
    listas = preparar(todas, perfil, hallazgos)
    entren = [f for f in listas if f.get("particion") == "entrenamiento"]
    evalu = [f for f in listas if f.get("particion") == "evaluacion"]
    modelo = arbol.entrenar(entren, RASGOS, max_prof=max_prof, min_hoja=min_hoja)
    verd = [f["etiqueta"] == "VP" for f in evalu]
    res = {
        "n_entrenamiento": len(entren), "n_evaluacion": len(evalu),
        "arbol": arbol.a_texto(modelo), "profundidad": arbol.profundidad(modelo),
        "entrenado": _metricas(verd, [arbol.predecir(modelo, f) == "VP" for f in evalu]),
        "determinista": _metricas(verd, _determinista(evalu, perfil, hallazgos)),
        "por_origen_etiqueta": {},
    }
    # donde difieren: por (etiqueta_por, etiqueta) para ver si el arbol arregla los casos declarados
    for f, v in zip(evalu, verd):
        k = f"{f.get('etiqueta_por')}/{f['etiqueta']}"
        d = res["por_origen_etiqueta"].setdefault(k, {"n": 0, "arbol_ok": 0, "determinista_ok": 0})
        d["n"] += 1
        d["arbol_ok"] += int((arbol.predecir(modelo, f) == "VP") == v)
    det = _determinista(evalu, perfil, hallazgos)
    for f, v, p in zip(evalu, verd, det):
        res["por_origen_etiqueta"][f"{f.get('etiqueta_por')}/{f['etiqueta']}"]["determinista_ok"] += int(p == v)
    return res, modelo


def formatear(res):
    L = ["# Clasificador entrenado (arbol CART) frente al determinista", "",
         f"Entrenado con {res['n_entrenamiento']} alertas soportadas; medido sobre {res['n_evaluacion']} "
         f"(particion de evaluacion). Profundidad del arbol: {res['profundidad']}.", "",
         "| Metrica | Determinista (5 reglas) | Arbol entrenado |", "|---|---|---|"]
    for k, nombre in (("precision", "Precision"), ("recall", "Exhaustividad"), ("f1", "F1"), ("tasa_fp", "Tasa de FP")):
        L.append(f"| {nombre} | {res['determinista'][k]:.3f} | {res['entrenado'][k]:.3f} |")
    L += ["", f"Matriz determinista: {res['determinista']['matriz']}", f"Matriz arbol: {res['entrenado']['matriz']}", "",
          "## Aciertos por procedencia de la etiqueta", "",
          "| Etiqueta (por) | n | determinista | arbol |", "|---|---|---|---|"]
    for k, d in sorted(res["por_origen_etiqueta"].items()):
        L.append(f"| {k} | {d['n']} | {d['determinista_ok']}/{d['n']} | {d['arbol_ok']}/{d['n']} |")
    L += ["", "## El arbol, como reglas", "", "```", res["arbol"].rstrip(), "```", ""]
    return "\n".join(L)


def main(argv):
    perfil_ruta = argv[argv.index("--perfil") + 1] if "--perfil" in argv else "prototipo/perfiles/empresarial.yml"
    prof = int(argv[argv.index("--prof") + 1]) if "--prof" in argv else 4
    hoja = int(argv[argv.index("--hoja") + 1]) if "--hoja" in argv else 3
    salida_dir = argv[argv.index("--salida-dir") + 1] if "--salida-dir" in argv else "evaluacion/resultados"
    perfil = perfilm.cargar(perfil_ruta)
    with open("lab/campañas/2026-08-31-evaluacion/hallazgos.json", encoding="utf-8") as f:
        hallazgos = json.load(f)
    res, _ = experimento("lab/dataset/etiquetado.jsonl", perfil, hallazgos, prof, hoja)
    texto = formatear(res)
    os.makedirs(salida_dir, exist_ok=True)
    ruta = os.path.join(salida_dir, f"entrenado-{datetime.date.today().isoformat()}.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto + f"-> {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
