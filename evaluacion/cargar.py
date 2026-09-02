"""Carga el dataset etiquetado y lo filtra por partición."""
import json

RUTA_DATASET = "lab/dataset/etiquetado.jsonl"

def cargar(ruta=RUTA_DATASET, particion="evaluacion"):
    filas = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            fila = json.loads(linea)
            if particion is None or fila.get("particion") == particion:
                filas.append(fila)
    return filas
