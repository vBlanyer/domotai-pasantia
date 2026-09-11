"""RAG local para el justificador: corpus curado + recuperacion semantica por embeddings."""
import json, math, os, re, subprocess, tempfile, urllib.request

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
        # Un modelo instruido antepone a veces un preambulo ("La busqueda que te propongo es:")
        # y pone la busqueda en la linea siguiente, entre acentos graves. Quedarse con la primera
        # linea no vacia devolvia el preambulo, que no busca nada, y lo pegaba a la consulta.
        linea = linea.strip().strip("`").strip()
        if linea and not linea.endswith(":"):
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

# Por que UN texto por llamada, en el subproceso y en el servidor: se midio que el vector de un
# texto cambia (coseno 0,99975 consigo mismo) segun que otros textos vayan en el mismo lote, en
# los dos caminos, porque el empaquetado altera la aritmetica. Con un texto por llamada, el
# subproceso y el servidor dan el mismo vector hasta la ultima cifra, el indice de uno vale para
# el otro, y el vector es funcion del texto y de nada mas (RNF-03). El coste lo paga la
# indexacion (una llamada por ficha), no la consulta, que siempre fue de un texto.

def _embedder_llama_uno(texto, modelo, binario, timeout, pooling):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(texto + "\n")
        ruta = f.name
    try:
        cp = subprocess.run([binario, "-m", modelo, "-f", ruta,
                             "--pooling", pooling, "--embd-output-format", "json"],
                            capture_output=True, text=True, timeout=timeout)
        return json.loads(cp.stdout)["data"][0]["embedding"]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError, KeyError, IndexError):
        return None
    finally:
        os.unlink(ruta)

def embedder_llama(textos, modelo=MODELO, binario=BINARIO, timeout=180, pooling=POOLING):
    """Un vector por texto via llama-embedding, una invocacion por texto. [] ante fallo (RNF-09).

    `pooling` no es un detalle: los modelos de embeddings de la familia BGE se entrenan con
    agrupacion por CLS y rinden peor con la media, mientras que un modelo generativo usado como
    embedder necesita la media. Cambiar de modelo sin cambiar esto degrada la recuperacion en
    silencio.
    """
    vecs = []
    for t in textos:
        v = _embedder_llama_uno(t.replace("\n", " ").strip(), modelo, binario, timeout, pooling)
        if v is None:
            return []
        vecs.append(v)
    return vecs

# Servidor residente de embeddings (llama-server --embedding --pooling cls). El subproceso
# carga bge-m3 en cada llamada: unos 5 s de los 7,5 s que tardaba una justificacion en el
# daemon, cuando el generador ya respondia en 0,4 s. Con el modelo cargado, milisegundos.
EMBED_URL = os.environ.get("LLAMA_EMBED_URL", "http://127.0.0.1:8082")

def embedder_servidor(textos, url=EMBED_URL, timeout=60, _abrir=urllib.request.urlopen):
    """Un vector por texto via POST /v1/embeddings. [] ante fallo (RNF-09), como el subproceso.

    El servidor debe arrancarse con el mismo modelo y la misma agrupacion que el subproceso
    (lab/scripts/llm-server.sh --embedder): se verifico que entonces, a un texto por peticion,
    produce exactamente los mismos vectores, asi que el indice construido con uno vale para el
    otro. Si el modelo no coincide, la guarda de dimensiones de `recuperar` para; una diferencia
    de agrupacion no la pararia nadie.
    """
    vecs = []
    for t in textos:
        peticion = urllib.request.Request(url.rstrip("/") + "/v1/embeddings",
                                          json.dumps({"input": t.replace("\n", " ").strip()}).encode("utf-8"),
                                          {"Content-Type": "application/json"})
        try:
            with _abrir(peticion, timeout=timeout) as respuesta:
                vecs.append(json.load(respuesta)["data"][0]["embedding"])
        except Exception:
            return []
    return vecs

def embedder_por_defecto():
    """El servidor si responde; si no, el subproceso, que da el mismo vector mas despacio.

    A diferencia del generador, aqui SI se cae al subproceso: el resultado es identico y solo
    cambia el tiempo, asi que degradar no altera ninguna decision. LLAMA_EMBED_MODO=subproceso
    fuerza el camino lento (para reproducir mediciones antiguas)."""
    if os.environ.get("LLAMA_EMBED_MODO") == "subproceso":
        return embedder_llama
    def _fn(textos):
        return embedder_servidor(textos) or embedder_llama(textos)
    _fn.__name__ = "embedder_por_defecto"
    return _fn

def guardar_indice(indice, ruta=RUTA_INDICE):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False)

def cargar_indice(ruta=RUTA_INDICE):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)

def _main(argv):
    import sys
    if "--indexar" in argv:
        indice = indexar(cargar_corpus(), embedder_por_defecto())
        if not indice:
            print("ERROR: el embedder no devolvio vectores"); return 1
        guardar_indice(indice)
        print(f"indice regenerado: {len(indice)} documentos -> {RUTA_INDICE}")
        return 0
    if "--consulta" in argv:
        consulta = argv[argv.index("--consulta") + 1]
        docs = recuperar(consulta, cargar_indice(), embedder_por_defecto(), k=3)
        for d in docs:
            print(f"[{d['id']}] {d['titulo']}: {d['texto'][:120]}...")
        return 0
    print("uso: python3 -m prototipo.rag [--indexar | --consulta \"...\"]")
    return 1

if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
