import os, unittest
from evaluacion import prioridad

RUTA = os.path.join(os.path.dirname(__file__), "..", "prioridad_esperada.yml")

class TestPrioridad(unittest.TestCase):
    def test_carga_y_consulta(self):
        tabla = prioridad.cargar_esperada(RUTA)
        self.assertEqual(prioridad.esperada("objetivo-vuln", "VP", tabla), 4)
        self.assertEqual(prioridad.esperada("objetivo-vuln", "FP", tabla), 1)

    def test_no_mapeado_es_none(self):
        tabla = prioridad.cargar_esperada(RUTA)
        self.assertIsNone(prioridad.esperada("nodo-desconocido", "VP", tabla))
