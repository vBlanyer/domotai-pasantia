"""Banco de simulación y evaluación del RAG (calibración con escenarios de ataque del perímetro MITRE).

Separa la LÓGICA de métricas (pura, testeable con fakes) del RUN real (índice + 1B, en `main`). Mide
la recuperación vectorial con Hit Rate@K, Precision@K y MRR sobre alertas sintéticas etiquetadas, y la
síntesis del 1B por su tasa de anclaje. La recuperación se mide contra el `id` de ficha esperado (verdad
estructural), no contra el texto de las fichas (sin circularidad).
"""
import json, os, sys

RUTA_SIM = os.path.join(os.path.dirname(__file__), "simulaciones", "ataques.jsonl")

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
