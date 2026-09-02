import os, unittest
from prototipo import rag

RUTA_CORPUS = os.path.join(os.path.dirname(__file__), "..", "corpus", "corpus.jsonl")

class TestCorpus(unittest.TestCase):
    def test_carga_el_corpus(self):
        corpus = rag.cargar_corpus(RUTA_CORPUS)
        self.assertGreaterEqual(len(corpus), 9)
        for d in corpus:
            for campo in ("id", "tipo", "titulo", "texto"):
                self.assertIn(campo, d)
        ids = {d["id"] for d in corpus}
        self.assertIn("regla-5760", ids)
        self.assertIn("mitre-T1110.001", ids)

    def test_la_regla_5760_no_es_un_protocolo(self):
        # el corpus debe describir 5760 correctamente (fallo de login), no como "protocolo"
        corpus = {d["id"]: d for d in rag.cargar_corpus(RUTA_CORPUS)}
        self.assertIn("fallo de autenticacion", corpus["regla-5760"]["texto"].lower())
