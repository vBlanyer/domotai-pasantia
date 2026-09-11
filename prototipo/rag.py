"""RAG local para el justificador: corpus curado + recuperacion semantica por embeddings."""
import json, math, os, re, subprocess, tempfile

from prototipo.analisis import CLASES_SIN_AMENAZA

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

# Que buscar cuando el motor ya decidio que NO hay amenaza. La consulta de ataque no sirve
# aqui: pedir "tecnica MITRE T1110 fuerza bruta contramedida" para una alerta descartada
# recupera exactamente el material que contradice el descarte. Cada frase apunta al motivo
# real del descarte, que es lo que la ficha correspondiente del corpus explica.
CONSULTA_DESCARTE = {
    "fp_actividad_legitima": "descarte falso positivo el origen es administracion legitima "
                              "declarada por el cliente, no un atacante",
    "fp_exposicion_inexistente": "descarte falso positivo el servicio no esta expuesto en el "
                                  "activo segun el inventario, el intento no puede prosperar",
    "no_soportada": "alerta fuera del perimetro del caso de uso, sin criterio fundado, "
                     "se deja a juicio humano conservando su severidad",
}

def construir_consulta(alerta, clase=None):
    # La consulta depende de la PREGUNTA que la justificacion va a responder, y esa pregunta la
    # fija la clase ya decidida (misma razon que en el enunciado del justificador). Sin esto, un
    # falso positivo recupera fichas sobre la tecnica de ataque y no hay forma de que el corpus
    # fundamente el descarte, por muchas fichas de descarte que se anadan.
    if clase in CLASES_SIN_AMENAZA:
        # Indexar sin .get: una clase sin amenaza a la que falte su consulta debe fallar aqui,
        # no caer en silencio a la consulta de ataque.
        return f"{CONSULTA_DESCARTE[clase]} servicio {alerta.get('servicio')}"
    mitre = " ".join(alerta.get("mitre", []) or [])
    familia = (alerta.get("familia") or "").replace("_", " ")
    # Lidera con la SEMANTICA del ataque (tecnica MITRE + familia + servicio) y la intencion de
    # contramedida, para recuperar las fichas mitre/mapeo/D3FEND. Se OMITE el numero de regla: sesga
    # los embeddings hacia las fichas regla-* (medido en el banco de simulacion, palanca 1).
    # SOLO campos estructurados (RNF-08): nunca el full_log/evento_crudo.
    return (f"tecnica MITRE {mitre} {familia} servicio {alerta.get('servicio')} "
            f"contramedida defensiva").strip()

def construir_prompt_consulta(alerta, clase=None):
    """Prompt del paso agentico: pide UNA linea de busqueda desde campos estructurados (RNF-08).

    El encargo depende de la clase por el mismo motivo que la consulta fija: si se le pide
    "conocimiento defensivo" sobre una alerta que el motor ya descarto, el modelo aumenta la
    consulta con vocabulario de ataque y la arrastra de vuelta al material que contradice el
    descarte, deshaciendo la correccion.
    """
    mitre = ", ".join(alerta.get("mitre", []) or ["s/tecnica"])
    if clase in CLASES_SIN_AMENAZA:
        encargo = (f"El motor ya clasifico esta alerta como {clase}: NO es una amenaza. Formula UNA "
                   "linea de busqueda para recuperar el criterio por el que una alerta asi se "
                   "descarta, citando SOLO estos datos.")
    else:
        encargo = ("Formula UNA linea de busqueda para recuperar conocimiento defensivo sobre esta "
                   "alerta, citando SOLO estos datos y, si aplica, la contramedida D3FEND.")
    return (f"Eres un analista. {encargo} No inventes IPs ni datos.\n"
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

def consulta_agentica(alerta, generador, clase=None, fallback=construir_consulta):
    """Paso de consulta agentico (1 salto): el modelo decide QUE anadir a la busqueda. **Aumenta** la
    consulta fija (conserva los anclajes estructurados) con la aportacion del modelo, para que nunca sea
    peor que la fija — un 1B formula consultas debiles. Degrada a la fija (RNF-09) si la salida es vacia
    o trae IPs inventadas (RNF-08/anclaje). Marca `agentica`."""
    base = fallback(alerta, clase)
    try:
        q = _limpiar_consulta(generador(construir_prompt_consulta(alerta, clase)))
    except Exception:
        q = ""
    if q and not _IP.search(q):
        return {"consulta": f"{base} {q}".strip(), "agentica": True}
    return {"consulta": base, "agentica": False}

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
    # Si alguien cambia el embedder y no reindexa, `_coseno` truncaria al vector mas corto con
    # `zip` y devolveria similitudes plausibles pero sin sentido. Un fallo silencioso en la capa
    # de recuperacion es peor que una parada: aqui se para.
    if indice and len(q) != len(indice[0].get("vector", ())):
        raise ValueError(
            f"el indice tiene vectores de {len(indice[0].get('vector', ()))} dimensiones y el "
            f"embedder produce {len(q)}: reindexa con 'python3 -m prototipo.rag --indexar'")
    puntuados = sorted(indice, key=lambda d: _coseno(q, d["vector"]), reverse=True)
    return [{c: d[c] for c in d if c != "vector"} for d in puntuados[:k]]

# Tipos de ficha que NO son conocimiento defensivo y compiten en la recuperacion (medido en el banco de
# simulacion, palanca 3): las 'regla-*' describen reglas de Wazuh, casi identicas a los ataques de
# credenciales/servicio, y expulsan a las mitre/mapeo/d3fend esperadas. Se excluyen del conocimiento.
EXCLUIR_CONOCIMIENTO = ("regla",)

# El corpus responde a dos preguntas distintas y sus fichas no son intercambiables. Las de ataque
# explican por que una amenaza importa y que contramedida aplica; las de descarte, por que una
# alerta NO es una amenaza. Ofrecer las primeras para justificar un descarte es servir justo el
# material que lo contradice, y esta medido que el modelo lo usa: una alerta clasificada como
# actividad legitima se explicaba como "ataque de fuerza bruta en curso". Se separan por
# construccion en vez de confiar en que la distancia coseno las deje fuera. Las fichas 'vuln'
# (postura del activo) no entran en la particion: son pertinentes para las dos preguntas.
TIPOS_ATAQUE = ("mitre", "mapeo", "d3fend")
TIPOS_DESCARTE = ("descarte",)

def tipos_excluidos(clase, base=EXCLUIR_CONOCIMIENTO):
    """Tipos de ficha que no compiten en la recuperacion, segun la clase ya decidida."""
    extra = TIPOS_ATAQUE if clase in CLASES_SIN_AMENAZA else TIPOS_DESCARTE
    return tuple(base or ()) + extra

def consultar_conocimiento(alerta, indice, embedder, generador=None, k=3,
                           excluir_tipos=EXCLUIR_CONOCIMIENTO, clase=None):
    """Herramienta de conocimiento (Opcion C): decide la consulta (agentica si hay generador) y
    recupera del indice de conocimiento (filtrado por tipo). Devuelve {consulta, agentica, pasajes}.

    `clase` es la clase que el motor YA decidio. Gobierna tanto la consulta como el subconjunto
    del corpus en el que se busca: sin ella, un falso positivo recupera fichas sobre la tecnica de
    ataque y ninguna ficha de descarte llega nunca al enunciado."""
    excluir = tipos_excluidos(clase, excluir_tipos)
    idx = [d for d in indice if d.get("tipo") not in excluir]
    if generador is not None:
        ca = consulta_agentica(alerta, generador, clase)
    else:
        ca = {"consulta": construir_consulta(alerta, clase), "agentica": False}
    pasajes = recuperar(ca["consulta"], idx, embedder, k=k)
    return {"consulta": ca["consulta"], "agentica": ca["agentica"], "pasajes": pasajes}

def recuperar_fn_agentico(indice, embedder, generador=None, k=3, excluir_tipos=EXCLUIR_CONOCIMIENTO):
    """Un recuperar_fn `(alerta, clase) -> {consulta, agentica, pasajes}` para el justificador y el
    agente. `clase` es opcional para que un llamador antiguo siga funcionando con el camino de
    amenaza, que es el comportamiento previo."""
    def _fn(alerta, clase=None):
        return consultar_conocimiento(alerta, indice, embedder, generador=generador, k=k,
                                      excluir_tipos=excluir_tipos, clase=clase)
    return _fn

BINARIO = os.environ.get("LLAMA_EMBED_BIN",
                         os.path.expanduser("~/miniforge3/envs/triaje-ml/bin/llama-embedding"))
# Variable propia, distinta de la del generador: si el embedder compartiera LLAMA_MODELO,
# apuntar el justificador a otro modelo cambiaria en silencio los vectores y dejaria
# inservible el indice ya calculado (dimensiones distintas).
MODELO = os.environ.get("LLAMA_EMBED_MODELO", "modelos/bge-m3-q8.gguf")
# Agrupacion del embedder: "cls" para los modelos de la familia BGE (asi se entrenaron),
# "mean" para un modelo generativo usado como embedder. Va con el modelo, no aparte.
POOLING = os.environ.get("LLAMA_EMBED_POOLING", "cls")
RUTA_INDICE = os.path.join(os.path.dirname(__file__), "corpus", "indice.json")

def embedder_llama(textos, modelo=MODELO, binario=BINARIO, timeout=180, pooling=POOLING):
    """Un vector por texto via llama-embedding. [] ante fallo (RNF-09).

    `pooling` no es un detalle: los modelos de embeddings de la familia BGE se entrenan con
    agrupacion por CLS y rinden peor con la media, mientras que un modelo generativo usado como
    embedder necesita la media. Cambiar de modelo sin cambiar esto degrada la recuperacion en
    silencio.
    """
    # cada texto en una linea; se limpian saltos internos para no romper el conteo por linea
    limpio = [t.replace("\n", " ").strip() for t in textos]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(limpio) + "\n")
        ruta = f.name
    try:
        cp = subprocess.run([binario, "-m", modelo, "-f", ruta,
                             "--pooling", pooling, "--embd-output-format", "json"],
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
