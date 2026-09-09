import os, unittest
from collections import Counter
from evaluacion import simular_ataques_rag as sim

RUTA = os.path.join(os.path.dirname(__file__), "..", "simulaciones", "ataques.jsonl")


class TestSet(unittest.TestCase):
    def test_carga_12_alertas_3_por_familia(self):
        alertas = sim.cargar_simulaciones(RUTA)
        self.assertEqual(len(alertas), 12)
        c = Counter(a["familia"] for a in alertas)
        self.assertEqual(len(c), 4)
        self.assertEqual(set(c.values()), {3})

    def test_cada_alerta_espera_su_mapeo_y_tiene_campos_criticos(self):
        for a in sim.cargar_simulaciones(RUTA):
            self.assertTrue(a["esperado"])
            self.assertIn(f"mapeo-{a['familia']}", a["esperado"])   # verdad de referencia por familia
            for campo in ("regla_id", "mitre", "servicio", "origen_ip", "activo"):
                self.assertTrue(a.get(campo))                       # RNF-07: sin campos vacios


if __name__ == "__main__":
    unittest.main()
