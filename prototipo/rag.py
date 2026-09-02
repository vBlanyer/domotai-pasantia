"""RAG local para el justificador: corpus curado + recuperacion semantica por embeddings."""
import json, math, os, subprocess, tempfile

RUTA_CORPUS = os.path.join(os.path.dirname(__file__), "corpus", "corpus.jsonl")

def cargar_corpus(ruta=RUTA_CORPUS):
    docs = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                docs.append(json.loads(linea))
    return docs

def construir_consulta(alerta):
    mitre = " ".join(alerta.get("mitre", []) or [])
    # SOLO campos estructurados (RNF-08): nunca el full_log/evento_crudo.
    return (f"regla {alerta.get('regla_id')} tecnicas MITRE {mitre} "
            f"servicio {alerta.get('servicio')}").strip()

def _coseno(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)

def indexar(corpus, embedder):
    vectores = embedder([d["texto"] for d in corpus])
    return [{**d, "vector": v} for d, v in zip(corpus, vectores)]

def recuperar(consulta, indice, embedder, k=3):
    qv = embedder([consulta])
    if not qv or not qv[0]:
        return []
    q = qv[0]
    puntuados = sorted(indice, key=lambda d: _coseno(q, d["vector"]), reverse=True)
    return [{c: d[c] for c in d if c != "vector"} for d in puntuados[:k]]
