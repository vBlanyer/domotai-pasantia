import os, unittest
from prototipo import catalogo

RAIZ = os.path.join(os.path.dirname(__file__), "..", "catalogo.yml")

class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.cat = catalogo.cargar_catalogo(RAIZ)

    def test_carga_las_14_acciones(self):
        self.assertEqual(len(self.cat), 14)

    def test_impacto_de_bloquear_ip_es_localizado(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "BLOQUEAR_IP"), "localizado")

    def test_impacto_de_bloquear_puerto_es_alcanza_servicio(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "BLOQUEAR_PUERTO"), "alcanza_servicio")

    def test_observacion_es_impacto_ninguno(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "OBS_CONEXIONES"), "ninguno")
