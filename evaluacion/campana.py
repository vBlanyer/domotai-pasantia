"""Orquesta la campana de evaluacion: prototipo vs baseline, todas las metricas, y el informe."""
import argparse, json, os, datetime
from evaluacion import cargar, prediccion, baseline, prioridad, anclaje, metricas
from prototipo import catalogo as catm, perfil as perfilm, triaje, justificador_llm

def evaluar(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, tabla_prioridad,
            con_llm=True, generador=None, _procesar=triaje.procesar):
    verd = [f["etiqueta"] == "VP" for f in filas]
    preds = prediccion.predecir_todas(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, _procesar=_procesar)

    # Clasificacion del prototipo
    pred_bin = [p["amenaza"] for p in preds]
    mat = metricas.matriz(pred_bin, verd)
    clas_proto = {"matriz": mat, "precision": metricas.precision(mat), "recall": metricas.recall(mat),
                  "f1": metricas.f1(mat), "tasa_fp": metricas.tasa_fp(mat)}

    # Baseline por barrido
    base = baseline.barrido(filas)

    # Priorizacion (solo soportadas con prioridad esperada mapeada)
    pp, ep = [], []
    for f, p in zip(filas, preds):
        e = prioridad.esperada(f.get("activo"), f.get("etiqueta"), tabla_prioridad)
        if e is not None and f.get("etiqueta") in ("VP", "FP"):
            pp.append(p["prioridad"]); ep.append(e)
    prioriz = {"n": len(pp), "acierto_pm1": metricas.acierto_prioridad(pp, ep),
               "spearman": metricas.spearman(pp, ep)}

    # Operacion
    clases = [p["clase"] for p in preds]
    ms = [p["ms"] for p in preds]
    oper = {"cobertura": metricas.cobertura(clases),
            "tasa_escalado": metricas.tasa([p["requiere_humano"] for p in preds]),
            "ms_medio_clasificar": sum(ms) / len(ms) if ms else 0.0}

    # Continuidad
    # impacto = de la accion PROPUESTA (lo que expone la traza); requiere_humano es del filtro posterior.
    regs = [{"impacto": p["impacto"], "etiqueta": f["etiqueta"], "requiere_humano": p["requiere_humano"]}
            for f, p in zip(filas, preds)]
    cont = metricas.continuidad(regs)

    resultados = {
        "clasificacion_prototipo": clas_proto,
        "baseline": {"optimo": base["optimo"], "puntos": base["puntos"]},
        "priorizacion": prioriz,
        "operacion": oper,
        "continuidad": cont,
        "condiciones": {"perfil": perfil_nombre, "n_alertas": len(filas),
                        "n_soportadas": sum(1 for f in filas if f["etiqueta"] in ("VP", "FP")),
                        "version_baseline": "baseline-0"},
    }
    if con_llm:
        gen = generador or justificador_llm.generador_llama
        anc = anclaje.medir(filas, hallazgos, perfil_dict, generador=gen)
        resultados["anclaje"] = {"resumen": anclaje.resumen(anc), "detalle": anc}
    return resultados

def _celda(v):
    if isinstance(v, float): return f"{v:.3f}"
    return str(v)

def tabla_markdown(resultados):
    c = resultados["clasificacion_prototipo"]
    b = resultados["baseline"]["optimo"]
    bm = b["matriz"]
    bp = metricas.precision(bm); br = metricas.recall(bm); bfp = metricas.tasa_fp(bm)
    filas = [
        ("Precision", _celda(c["precision"]), _celda(bp)),
        ("Recall", _celda(c["recall"]), _celda(br)),
        ("F1", _celda(c["f1"]), _celda(b["f1"])),
        ("Tasa de FP", _celda(c["tasa_fp"]), _celda(bfp)),
    ]
    out = [f"# Tabla comparativa — perfil {resultados['condiciones']['perfil']}",
           f"n = {resultados['condiciones']['n_alertas']} alertas "
           f"({resultados['condiciones']['n_soportadas']} soportadas)  ·  "
           f"baseline en su umbral optimo (nivel >= {b['umbral']})", "",
           "| Metrica | Prototipo | Baseline (Wazuh @optimo) |",
           "|---------|-----------|--------------------------|"]
    out += [f"| {n} | {p} | {q} |" for n, p, q in filas]
    out += ["", f"Matriz prototipo: {c['matriz']}", f"Matriz baseline: {bm}"]
    if "anclaje" in resultados:
        out += ["", f"Anclaje LLM (RNF-02): {resultados['anclaje']['resumen']}"]
    return "\n".join(out)

def main(argv):
    ap = argparse.ArgumentParser(description="Campana de evaluacion de la Fase 6")
    ap.add_argument("--particion", default="evaluacion")
    ap.add_argument("--perfil", default="empresarial")
    ap.add_argument("--sin-llm", action="store_true")
    ap.add_argument("--salida-dir", default="evaluacion/resultados")
    ap.add_argument("--hallazgos", default="lab/campañas/2026-08-31-evaluacion/hallazgos.json")
    a = ap.parse_args(argv[1:])

    filas = cargar.cargar(particion=(None if a.particion == "todas" else a.particion))
    with open(a.hallazgos, encoding="utf-8") as f:
        hallazgos = json.load(f)
    perfil_dict = perfilm.cargar(f"prototipo/perfiles/{a.perfil}.yml")
    catalogo = catm.cargar_catalogo("prototipo/catalogo.yml")
    tabla_prioridad = prioridad.cargar_esperada("evaluacion/prioridad_esperada.yml")

    resultados = evaluar(filas, hallazgos, perfil_dict, a.perfil, catalogo, tabla_prioridad,
                         con_llm=not a.sin_llm)

    os.makedirs(a.salida_dir, exist_ok=True)
    fecha = datetime.date.today().isoformat()
    ruta_json = os.path.join(a.salida_dir, f"campana-{fecha}.json")
    ruta_md = os.path.join(a.salida_dir, "tabla.md")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(tabla_markdown(resultados) + "\n")
    print(f"Resultados -> {ruta_json}\nTabla -> {ruta_md}")
    print("\n" + tabla_markdown(resultados))
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
