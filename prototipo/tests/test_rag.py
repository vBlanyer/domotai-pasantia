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

class TestLogica(unittest.TestCase):
    def test_consulta_solo_campos_estructurados(self):
        alerta = {"regla_id":"5760","mitre":["T1110.001","T1021.004"],"servicio":"ssh",
                  "evento_crudo":"IGNORA ESTO texto del atacante"}
        q = rag.construir_consulta(alerta)
        self.assertIn("5760", q); self.assertIn("T1110.001", q); self.assertIn("ssh", q)
        self.assertNotIn("IGNORA ESTO", q)              # RNF-08: el full_log no entra

    def test_coseno(self):
        self.assertAlmostEqual(rag._coseno([1,0,0],[1,0,0]), 1.0)
        self.assertAlmostEqual(rag._coseno([1,0],[0,1]), 0.0)
        self.assertEqual(rag._coseno([0,0],[1,1]), 0.0)  # vector nulo

    def test_indexar_y_recuperar_con_embedder_falso(self):
        # embedder falso: cada texto -> vector segun una palabra clave (determinista)
        def emb(textos):
            vecs = []
            for t in textos:
                tl = t.lower()
                vecs.append([1.0 if "5760" in tl else 0.0,
                             1.0 if "t1110.001" in tl else 0.0,
                             1.0 if "vsftpd" in tl or "samba" in tl else 0.0])
            return vecs
        corpus = [
            {"id":"regla-5760","tipo":"regla","titulo":"5760","texto":"regla 5760 fallo SSH"},
            {"id":"mitre-T1110.001","tipo":"mitre","titulo":"T","texto":"T1110.001 adivinacion"},
            {"id":"vuln-x","tipo":"vuln","titulo":"v","texto":"vsftpd samba superficie"},
        ]
        indice = rag.indexar(corpus, emb)
        self.assertIn("vector", indice[0])
        # consulta sobre 5760 -> el doc de 5760 debe salir primero
        docs = rag.recuperar("regla 5760 ssh", indice, emb, k=2)
        self.assertEqual(docs[0]["id"], "regla-5760")
        self.assertNotIn("vector", docs[0])             # se devuelve el doc limpio
