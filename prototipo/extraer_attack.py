"""Extractor del bundle STIX de MITRE ATT&CK (`enterprise-attack.json`) hacia fichas curadas del RAG.

El bundle tiene ~860 tecnicas: demasiado y ruidoso para un 1B. Este modulo **destila** solo las
tecnicas del perimetro soportado (allowlist) en fichas cortas y limpias, y las **compone** con las
fichas hechas a mano (`curado.jsonl`: reglas, vulns, D3FEND, mapeos). Fuente = MITRE; lo que embebe
el RAG = el corpus curado resultante.
"""
import json, re, sys, os

# Allowlist del perimetro soportado (4 familias). Editable: ampliar aqui para cubrir mas tecnicas.
TECNICAS_PERIMETRO = {
    # acceso_credenciales
    "T1110", "T1110.001", "T1110.003", "T1110.004", "T1078",
    # reconocimiento
    "T1046", "T1595", "T1595.001", "T1595.002",
    # servicio_expuesto
    "T1021", "T1021.004", "T1133",
    # explotacion_conocida
    "T1190", "T1210", "T1203",
}

_CITA = re.compile(r'\(Citation:[^)]*\)')
_ENLACE_MD = re.compile(r'\[([^\]]+)\]\((?:[^)]+)\)')   # [texto](url) -> texto
_ESPACIOS = re.compile(r'\s+')

def _limpiar(desc, tope=600):
    t = _ENLACE_MD.sub(r'\1', desc or "")
    t = _CITA.sub('', t)
    t = _ESPACIOS.sub(' ', t).strip()
    return t[:tope]

def _id_externo(obj):
    for r in obj.get("external_references", []):
        if r.get("source_name") == "mitre-attack":
            return r.get("external_id")
    return None

def extraer_tecnicas(objects, ids_permitidos):
    """Fichas `{id, tipo, titulo, texto}` de las attack-pattern en la allowlist, sin deprecadas/revocadas."""
    fichas = []
    for o in objects:
        if o.get("type") != "attack-pattern":
            continue
        if o.get("x_mitre_deprecated") or o.get("revoked"):
            continue
        ext = _id_externo(o)
        if ext not in ids_permitidos:
            continue
        fichas.append({
            "id": f"mitre-{ext}",
            "tipo": "mitre",
            "titulo": f"{ext} {o.get('name', '')}".strip(),
            "texto": f"{ext} {o.get('name', '')} (MITRE ATT&CK): {_limpiar(o.get('description', ''))}",
        })
    fichas.sort(key=lambda f: f["id"])
    return fichas

def compilar_corpus(curado, extraidas):
    """Une curado + extraidas, deduplicando por `id`; ante colision, gana la extraida (oficial)."""
    por_id = {d["id"]: d for d in curado}
    for f in extraidas:
        por_id[f["id"]] = f
    # orden estable: primero el curado (en su orden), luego las extraidas nuevas
    orden, vistos = [], set()
    for d in curado:
        orden.append(por_id[d["id"]]); vistos.add(d["id"])
    for f in extraidas:
        if f["id"] not in vistos:
            orden.append(f); vistos.add(f["id"])
    return orden

def cargar_jsonl(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def cargar_bundle(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f).get("objects", [])

_DIR = os.path.dirname(__file__)
BUNDLE_DEF = os.path.join(_DIR, "corpus", "fuentes", "enterprise-attack.json")
CURADO_DEF = os.path.join(_DIR, "corpus", "curado.jsonl")
CORPUS_DEF = os.path.join(_DIR, "corpus", "corpus.jsonl")

def main(argv):
    bundle = argv[1] if len(argv) > 1 else BUNDLE_DEF
    curado_p = argv[2] if len(argv) > 2 else CURADO_DEF
    salida = argv[3] if len(argv) > 3 else CORPUS_DEF
    if not os.path.exists(bundle):
        print(f"ERROR: no existe el bundle {bundle} (ver prototipo/corpus/fuentes/README.md)")
        return 1
    extraidas = extraer_tecnicas(cargar_bundle(bundle), TECNICAS_PERIMETRO)
    curado = cargar_jsonl(curado_p)
    corpus = compilar_corpus(curado, extraidas)
    with open(salida, "w", encoding="utf-8") as f:
        for d in corpus:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    faltan = sorted(TECNICAS_PERIMETRO - {f["id"].replace("mitre-", "") for f in extraidas})
    print(f"{len(extraidas)} tecnicas extraidas + {len(curado)} curadas -> {len(corpus)} fichas -> {salida}"
          + (f"  (no halladas: {', '.join(faltan)})" if faltan else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
