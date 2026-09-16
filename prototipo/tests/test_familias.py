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

    def test_triar_y_enrutar_sin_ruta_falla_al_cargar(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8") as f:
            f.write("mala: { mitre: [T1], nivel: triar_y_enrutar }\n")  # sin ruta
            ruta = f.name
        try:
            with self.assertRaises(ValueError):
                familias.cargar_registro(ruta)
        finally:
            os.unlink(ruta)
