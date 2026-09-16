import unittest
from prototipo import familias

class TestRegistroFamilias(unittest.TestCase):
    def test_familia_actuar_trae_nivel_y_mitre(self):
        e = familias.registro()["acceso_credenciales"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertIn("T1110", e["mitre"])

    def test_familia_enrutada_trae_ruta(self):
        e = familias.registro()["explotacion_conocida"]
        self.assertEqual(e["nivel"], "triar_y_enrutar")
        self.assertEqual(e["ruta"], "appsec")

    def test_familia_ausente_es_none(self):
        self.assertIsNone(familias.registro().get("plataforma"))
