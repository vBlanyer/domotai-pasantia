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
