import unittest
from evaluacion import baseline

FILAS = [
    {"etiqueta":"VP","nivel_wazuh":10}, {"etiqueta":"VP","nivel_wazuh":10},
    {"etiqueta":"FP","nivel_wazuh":5},  {"etiqueta":"no_soportada","nivel_wazuh":3},
]

class TestBaseline(unittest.TestCase):
    def test_predecir_umbral(self):
        self.assertTrue(baseline.predecir(10, 10))
        self.assertFalse(baseline.predecir(9, 10))

    def test_verdad_binaria(self):
        self.assertEqual(baseline.verdad_binaria(FILAS), [True, True, False, False])

    def test_barrido_tiene_un_punto_por_umbral_y_optimo(self):
        r = baseline.barrido(FILAS, range(3, 13))
        self.assertEqual(len(r["puntos"]), 10)
        # umbral 10: predice amenaza solo los dos nivel-10 (ambos VP) -> F1 perfecto
        self.assertEqual(r["optimo"]["umbral"], 10)
        self.assertEqual(r["optimo"]["matriz"], {"vp":2,"fp":0,"vn":2,"fn":0})
