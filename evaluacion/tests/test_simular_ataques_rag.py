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


class TestRecuperacion(unittest.TestCase):
    def test_metricas_agregadas(self):
        alertas = [{"id_alerta": "a", "esperado": ["X"]}, {"id_alerta": "b", "esperado": ["Y"]}]
        salidas = {"a": ["Z", "X", "W", "V", "U"], "b": ["Y", "Q", "R", "S", "T"]}
        rec = lambda al: salidas[al["id_alerta"]]
        ag = sim.evaluar_recuperacion(alertas, rec, ks=(1, 3, 5))["agregado"]
        # a: relevante en rango 2; b: rango 1
        self.assertAlmostEqual(ag["por_k"][1]["hit_rate"], 0.5)   # solo b acierta @1
        self.assertAlmostEqual(ag["por_k"][3]["hit_rate"], 1.0)   # ambos @3
        self.assertAlmostEqual(ag["por_k"][1]["precision"], 0.5)  # a=0, b=1
        self.assertAlmostEqual(ag["por_k"][3]["precision"], 1 / 3)  # cada uno 1/3
        self.assertAlmostEqual(ag["mrr"], 0.75)                   # (1/2 + 1/1)/2

    def test_sin_relevante_da_ceros(self):
        res = sim.evaluar_recuperacion([{"id_alerta": "a", "esperado": ["X"]}],
                                       lambda al: ["Z", "W"], ks=(1, 3))
        self.assertEqual(res["agregado"]["mrr"], 0.0)
        self.assertEqual(res["agregado"]["por_k"][3]["hit_rate"], 0.0)


class TestSintesis(unittest.TestCase):
    def test_tasa_anclaje_y_termino(self):
        alertas = [{"id_alerta": "a", "termino_esperado": "5760"},
                   {"id_alerta": "b", "termino_esperado": "5758"}]
        textos = {"a": "regla 5760 fuerza bruta anclada", "b": ""}
        anclado_fn = lambda texto, al: bool(texto)          # fake: anclado si hay texto
        res = sim.evaluar_sintesis(alertas, lambda al: textos[al["id_alerta"]], anclado_fn)
        self.assertAlmostEqual(res["tasa_anclaje"], 0.5)     # a anclada, b vacia
        self.assertAlmostEqual(res["tasa_termino"], 0.5)     # a cita 5760, b no


if __name__ == "__main__":
    unittest.main()
