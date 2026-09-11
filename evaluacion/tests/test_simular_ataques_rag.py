import os, unittest
from collections import Counter
from evaluacion import simular_ataques_rag as sim

RUTA = os.path.join(os.path.dirname(__file__), "..", "simulaciones", "ataques.jsonl")


class TestSet(unittest.TestCase):
    def test_carga_14_alertas_de_4_familias(self):
        # 12 originales (3 por familia, etiquetas MITRE "ideales") + 2 de reconocimiento con las
        # etiquetas que Wazuh pone de verdad a las reglas 5706/5701 (T1021.004, T1190), anadidas
        # cuando la campana real mostro que el banco no reproducia los datos que llegan.
        alertas = sim.cargar_simulaciones(RUTA)
        self.assertEqual(len(alertas), 14)
        c = Counter(a["familia"] for a in alertas)
        self.assertEqual(len(c), 4)
        self.assertEqual(c["reconocimiento"], 5)
        self.assertTrue(all(v >= 3 for v in c.values()))

    def test_los_casos_reales_llevan_la_etiqueta_de_wazuh_no_la_ideal(self):
        reales = {a["regla_id"]: a for a in sim.cargar_simulaciones(RUTA) if a["id_alerta"].startswith("sim-rc-real")}
        self.assertEqual(reales["5706"]["mitre"], ["T1021.004"])
        self.assertEqual(reales["5701"]["mitre"], ["T1190"])
        for a in reales.values():
            self.assertIn("mapeo-reconocimiento", a["esperado"])

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


class TestInforme(unittest.TestCase):
    def _agg(self, mrr, h, p):
        return {"agregado": {"mrr": mrr, "por_k": {k: {"hit_rate": h, "precision": p} for k in (1, 3, 5)}}}

    def test_formatear_incluye_metricas_y_columnas(self):
        md = sim.formatear_informe(self._agg(0.5, 0.4, 0.4), self._agg(0.6, 0.5, 0.5),
                                   {"tasa_anclaje": 0.83, "tasa_termino": 0.5, "n": 12})
        for frag in ("Hit Rate@1", "Precision@3", "MRR", "Fija", "Agéntica", "anclaje"):
            self.assertIn(frag, md)


if __name__ == "__main__":
    unittest.main()
