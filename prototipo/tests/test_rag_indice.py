"""#2 de la revisión del 15/11: el índice del RAG (corpus/indice.json) debe cubrir el corpus tal cual está.
Si se añade o se cambia una ficha sin reindexar, el justificador no la recupera nunca y nadie se entera.
Sin modelo: compara ids y textos. Reindexar: python3 -m prototipo.explicacion.rag --indexar"""
import unittest

from prototipo.explicacion import rag


class TestIndiceCubreElCorpus(unittest.TestCase):
    def test_indice_cubre_el_corpus(self):
        corpus = {d["id"]: d["texto"] for d in rag.cargar_corpus()}
        indice = {d["id"]: d["texto"] for d in rag.cargar_indice()}
        self.assertEqual(sorted(set(corpus) - set(indice)), [], "fichas del corpus sin indexar: reindexa")
        self.assertEqual(sorted(set(indice) - set(corpus)), [], "fichas indexadas que ya no están en el corpus")
        self.assertEqual(sorted(i for i in corpus if corpus[i] != indice[i]), [], "fichas cambiadas sin reindexar")


if __name__ == "__main__":
    unittest.main()
