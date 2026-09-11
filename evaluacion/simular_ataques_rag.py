"""Banco de simulación y evaluación del RAG (calibración con escenarios de ataque del perímetro MITRE).

Separa la LÓGICA de métricas (pura, testeable con fakes) del RUN real (índice + 1B, en `main`). Mide
la recuperación vectorial con Hit Rate@K, Precision@K y MRR sobre alertas sintéticas etiquetadas, y la
síntesis del 1B por su tasa de anclaje. La recuperación se mide contra el `id` de ficha esperado (verdad
estructural), no contra el texto de las fichas (sin circularidad).
"""
import datetime, json, os, sys

RUTA_SIM = os.path.join(os.path.dirname(__file__), "simulaciones", "ataques.jsonl")
DIR_RESULTADOS = os.path.join(os.path.dirname(__file__), "resultados")

def cargar_simulaciones(ruta=RUTA_SIM):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

# ------------------------------------------------------------- recuperación --

def _reciprocal_rank(ids_recuperados, esperados):
    esp = set(esperados)
    for i, d in enumerate(ids_recuperados, 1):
        if d in esp:
            return 1.0 / i
    return 0.0

def _metricas_alerta(ids_recuperados, esperados, ks):
    esp = set(esperados)
    por_k = {}
    for k in ks:
        topk = ids_recuperados[:k]
        rel = sum(1 for d in topk if d in esp)
        por_k[k] = {"hit": 1.0 if rel > 0 else 0.0, "precision": rel / k}
    return {"rr": _reciprocal_rank(ids_recuperados, esperados), "por_k": por_k}

def evaluar_recuperacion(alertas, recuperar_ids, ks=(1, 3, 5)):
    """Mide la recuperación vectorial. `recuperar_ids(alerta) -> [id,...]` ordenado por relevancia.
    Devuelve por-alerta y agregado (Hit Rate@K, Precision@K, MRR). Puro: `recuperar_ids` inyectable."""
    filas = [{"id_alerta": a.get("id_alerta"), **_metricas_alerta(recuperar_ids(a), a["esperado"], ks)}
             for a in alertas]
    n = len(filas) or 1
    agg = {"mrr": sum(f["rr"] for f in filas) / n, "por_k": {}}
    for k in ks:
        agg["por_k"][k] = {
            "hit_rate": sum(f["por_k"][k]["hit"] for f in filas) / n,
            "precision": sum(f["por_k"][k]["precision"] for f in filas) / n,
        }
    return {"n": len(filas), "filas": filas, "agregado": agg}

# ---------------------------------------------------------------- síntesis --

def evaluar_sintesis(alertas, justificar_texto, anclado_fn):
    """Mide cómo el 1B sintetiza la justificación: `anclado_fn(texto, alerta)` (reusa verificar_anclaje)
    y si aparece `termino_esperado`. `justificar_texto(alerta) -> str` inyectable."""
    filas = []
    for a in alertas:
        texto = justificar_texto(a) or ""
        term = a.get("termino_esperado", "")
        filas.append({"id_alerta": a.get("id_alerta"),
                      "anclado": bool(anclado_fn(texto, a)),
                      "menciona_termino": bool(term and term in texto)})
    n = len(filas) or 1
    return {"n": len(filas),
            "tasa_anclaje": sum(f["anclado"] for f in filas) / n,
            "tasa_termino": sum(f["menciona_termino"] for f in filas) / n,
            "filas": filas}

# ---------------------------------------------------------------- informe --

def _fmt(x):
    return f"{x:.2f}"

def formatear_informe(rec_fija, rec_agentica, sintesis=None, ks=(1, 3, 5), condiciones=None):
    af, aa = rec_fija["agregado"], rec_agentica["agregado"]
    L = ["# Evaluación del RAG por simulación de ataques", "",
         f"Sobre {rec_fija.get('n', '')} alertas sintéticas etiquetadas (perímetro MITRE). Recuperación medida "
         "contra el `id` de ficha esperado (verdad estructural).", ""]
    # Sin esto, dos corridas con modelos distintos se leen como si fueran comparables.
    if condiciones:
        L += [f"**Condiciones:** {condiciones}", ""]
    L += [
         "## Recuperación: consulta Fija vs Agéntica", "",
         "| Métrica | Fija | Agéntica |", "|---|---|---|"]
    for k in ks:
        L.append(f"| Hit Rate@{k} | {_fmt(af['por_k'][k]['hit_rate'])} | {_fmt(aa['por_k'][k]['hit_rate'])} |")
    for k in ks:
        L.append(f"| Precision@{k} | {_fmt(af['por_k'][k]['precision'])} | {_fmt(aa['por_k'][k]['precision'])} |")
    L.append(f"| MRR | {_fmt(af['mrr'])} | {_fmt(aa['mrr'])} |")
    if sintesis:
        L += ["", "## Síntesis del 1B (justificación con contexto recuperado)",
              f"- Tasa de anclaje: {_fmt(sintesis['tasa_anclaje'])}  ·  Tasa de término: {_fmt(sintesis['tasa_termino'])}"]
    return "\n".join(L) + "\n"

# -------------------------------------------------------------------- run --

def _recuperar_ids_fijo(indice, embedder, k):
    from prototipo import rag
    # via consultar_conocimiento (generador=None) para aplicar el mismo filtro de conocimiento (palanca 3)
    return lambda a: [p["id"] for p in rag.consultar_conocimiento(a, indice, embedder, generador=None, k=k)["pasajes"]]

def _recuperar_ids_agentico(indice, embedder, generador, k):
    from prototipo import rag
    def _fn(a):
        r = rag.consultar_conocimiento(a, indice, embedder, generador=generador, k=k)
        return [p["id"] for p in r["pasajes"]]
    return _fn

def main(argv):
    from prototipo import rag, justificador_llm as jl
    ks = (1, 3, 5)
    kmax = max(ks)
    con_sintesis = "--con-sintesis" in argv
    salida_dir = argv[argv.index("--salida-dir") + 1] if "--salida-dir" in argv else DIR_RESULTADOS
    alertas = cargar_simulaciones()
    indice = rag.cargar_indice()
    emb, gen = rag.embedder_por_defecto(), jl.generador_por_defecto()
    print(f"Evaluando recuperación (fija y agéntica) sobre {len(alertas)} alertas... (usa el 1B, lento)")
    rec_fija = evaluar_recuperacion(alertas, _recuperar_ids_fijo(indice, emb, kmax), ks)
    rec_ag = evaluar_recuperacion(alertas, _recuperar_ids_agentico(indice, emb, gen, kmax), ks)
    sintesis = None
    if con_sintesis:
        print("Evaluando síntesis del 1B (justificación con RAG)...")
        rec_fn = rag.recuperar_fn_agentico(indice, emb, generador=gen, k=kmax)
        def _just_texto(a):
            ctx = {"postura": {"expuesto": True}, "criticidad": "alta"}
            return jl.justificar_con_rag(a, ctx, "vp_intento_acceso", gen, rec_fn).get("texto", "")
        sintesis = evaluar_sintesis(alertas, _just_texto, jl.verificar_anclaje)
    condiciones = (f"embedder `{os.path.basename(rag.MODELO)}` ({emb.__name__}) · "
                   f"generador `{jl._version_llm()}` ({gen.__name__})")
    informe = formatear_informe(rec_fija, rec_ag, sintesis, ks, condiciones=condiciones)
    os.makedirs(salida_dir, exist_ok=True)
    ruta = os.path.join(salida_dir, f"rag-simulacion-{datetime.date.today().isoformat()}.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(informe)
    print("\n" + informe + f"-> {ruta}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
