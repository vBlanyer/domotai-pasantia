"""RAG local para el justificador: corpus curado + recuperacion semantica por embeddings."""
import json, math, os, re, subprocess, tempfile

_IP = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

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

def construir_prompt_consulta(alerta):
    """Prompt del paso agentico: pide UNA linea de busqueda desde campos estructurados (RNF-08)."""
    mitre = ", ".join(alerta.get("mitre", []) or ["s/tecnica"])
    return ("Eres un analista. Formula UNA linea de busqueda para recuperar conocimiento defensivo "
            "sobre esta alerta, citando SOLO estos datos y, si aplica, la contramedida D3FEND. "
            "No inventes IPs ni datos.\n"
            f"Datos: regla {alerta.get('regla_id')}, tecnicas MITRE {mitre}, servicio {alerta.get('servicio')}.\n"
            "Busqueda:")

def _limpiar_consulta(texto):
    t = texto or ""
    if "Busqueda:" in t:                     # quedarse con lo generado tras el prompt
        t = t.split("Busqueda:", 1)[-1]
    for linea in t.splitlines():
        linea = linea.strip()
        if linea:
            return linea
    return ""

def consulta_agentica(alerta, generador, fallback=construir_consulta):
    """Paso de consulta agentico (1 salto): el modelo decide QUE recuperar. Degrada a la consulta
    fija (RNF-09) si la salida es vacia o trae IPs inventadas (RNF-08/anclaje). Marca `agentica`."""
    try:
        q = _limpiar_consulta(generador(construir_prompt_consulta(alerta)))
    except Exception:
        q = ""
    if q and not _IP.search(q):
        return {"consulta": q, "agentica": True}
    return {"consulta": fallback(alerta), "agentica": False}

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

BINARIO = os.environ.get("LLAMA_EMBED_BIN",
                         os.path.expanduser("~/miniforge3/envs/triaje-ml/bin/llama-embedding"))
MODELO = os.environ.get("LLAMA_MODELO", "modelos/llama-3.2-1b-q4.gguf")
RUTA_INDICE = os.path.join(os.path.dirname(__file__), "corpus", "indice.json")

def embedder_llama(textos, modelo=MODELO, binario=BINARIO, timeout=180):
    """Un vector por texto via llama-embedding (--pooling mean). [] ante fallo (RNF-09)."""
    # cada texto en una linea; se limpian saltos internos para no romper el conteo por linea
    limpio = [t.replace("\n", " ").strip() for t in textos]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(limpio) + "\n")
        ruta = f.name
    try:
        cp = subprocess.run([binario, "-m", modelo, "-f", ruta,
                             "--pooling", "mean", "--embd-output-format", "json"],
                            capture_output=True, text=True, timeout=timeout)
        datos = json.loads(cp.stdout)["data"]
        vecs = [None] * len(limpio)
        for item in datos:
            vecs[item["index"]] = item["embedding"]
        if any(v is None for v in vecs):
            return []
        return vecs
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError, KeyError, IndexError):
        return []
    finally:
        os.unlink(ruta)

def guardar_indice(indice, ruta=RUTA_INDICE):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False)

def cargar_indice(ruta=RUTA_INDICE):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)

def _main(argv):
    import sys
    if "--indexar" in argv:
        indice = indexar(cargar_corpus(), embedder_llama)
        if not indice:
            print("ERROR: el embedder no devolvio vectores"); return 1
        guardar_indice(indice)
        print(f"indice regenerado: {len(indice)} documentos -> {RUTA_INDICE}")
        return 0
    if "--consulta" in argv:
        consulta = argv[argv.index("--consulta") + 1]
        docs = recuperar(consulta, cargar_indice(), embedder_llama, k=3)
        for d in docs:
            print(f"[{d['id']}] {d['titulo']}: {d['texto'][:120]}...")
        return 0
    print("uso: python3 -m prototipo.rag [--indexar | --consulta \"...\"]")
    return 1

if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
