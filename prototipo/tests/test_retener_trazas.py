import json
import os
import tempfile
import unittest

from prototipo import retener_trazas as rt, traza


class TestPlanRetencion(unittest.TestCase):
    """#6: política de retención pura. El más reciente (el activo) nunca se poda."""
    F = [("a.jsonl", 100), ("b.jsonl", 400), ("c.jsonl", 200), ("d.jsonl", 300)]   # (ruta, mtime)

    def test_sin_politica_no_poda_nada(self):
        conservar, podar = rt.plan_retencion(self.F)
        self.assertEqual(podar, [])
        self.assertEqual(sorted(conservar), ["a.jsonl", "b.jsonl", "c.jsonl", "d.jsonl"])

    def test_max_n_conserva_los_n_mas_recientes(self):
        _, podar = rt.plan_retencion(self.F, max_n=2)
        self.assertEqual(sorted(podar), ["a.jsonl", "c.jsonl"])   # b(400) y d(300) son los 2 más recientes

    def test_max_dias_poda_los_viejos_pero_nunca_el_activo(self):
        # ahora=1_000_000; todos muy viejos. Aun así el más reciente (b) se conserva.
        _, podar = rt.plan_retencion(self.F, max_dias=1, ahora=1_000_000)
        self.assertNotIn("b.jsonl", podar)                       # el activo nunca se poda
        self.assertEqual(sorted(podar), ["a.jsonl", "c.jsonl", "d.jsonl"])


class TestRetenerMain(unittest.TestCase):
    def _fichero(self, d, nombre, mtime, registros):
        ruta = os.path.join(d, nombre)
        prev = traza.GENESIS
        with open(ruta, "w", encoding="utf-8") as f:
            for r in registros:
                enc = traza.encadenar(r, prev); prev = enc["hash"]
                f.write(json.dumps(enc) + "\n")
        os.utime(ruta, (mtime, mtime))
        return ruta

    def test_seco_no_borra_nada(self):
        d = tempfile.mkdtemp()
        self._fichero(d, "trazas-1.jsonl", 100, [{"tipo": "decision", "id_decision": "s1"}])
        self._fichero(d, "trazas-2.jsonl", 200, [{"tipo": "decision", "id_decision": "s1"}])
        rt._main([d, "--max", "1"])                              # sin --aplicar: dry-run
        self.assertEqual(sorted(os.listdir(d)), ["trazas-1.jsonl", "trazas-2.jsonl"])

    def test_aplicar_poda_el_viejo_y_conserva_el_activo(self):
        d = tempfile.mkdtemp()
        self._fichero(d, "trazas-1.jsonl", 100, [{"tipo": "decision", "id_decision": "s1"}])
        self._fichero(d, "trazas-2.jsonl", 200, [{"tipo": "decision", "id_decision": "s1"}])
        rt._main([d, "--max", "1", "--aplicar"])
        self.assertEqual(os.listdir(d), ["trazas-2.jsonl"])      # el activo (más reciente) se queda

    def test_excepto_protege_el_activo_por_nombre(self):
        # --excepto nombra el fichero vivo del daemon: no se poda aunque la política lo marque.
        d = tempfile.mkdtemp()
        self._fichero(d, "trazas-1.jsonl", 100, [{"tipo": "decision", "id_decision": "s1"}])
        activo = self._fichero(d, "trazas-2.jsonl", 200, [{"tipo": "decision", "id_decision": "s1"}])
        self._fichero(d, "trazas-3.jsonl", 300, [{"tipo": "decision", "id_decision": "s1"}])
        rt._main([d, "--max", "1", "--excepto", activo, "--aplicar"])
        # el más reciente (trazas-3) se conserva por ser activo-por-mtime; trazas-2 por --excepto;
        # solo trazas-1 se poda.
        self.assertEqual(sorted(os.listdir(d)), ["trazas-2.jsonl", "trazas-3.jsonl"])

    def test_no_borra_un_fichero_con_la_cadena_rota(self):
        # Una traza con la cadena rota puede ser evidencia de manipulación: se conserva y se avisa.
        d = tempfile.mkdtemp()
        self._fichero(d, "trazas-2.jsonl", 200, [{"tipo": "decision", "id_decision": "s1"}])
        roto = os.path.join(d, "trazas-1.jsonl")
        with open(roto, "w", encoding="utf-8") as f:
            f.write(json.dumps({"tipo": "decision", "id_decision": "s1", "hash": "x", "hash_previo": "y"}) + "\n")
        os.utime(roto, (100, 100))
        rt._main([d, "--max", "1", "--aplicar"])
        self.assertIn("trazas-1.jsonl", os.listdir(d))           # NO se borra pese a la política


if __name__ == "__main__":
    unittest.main()
