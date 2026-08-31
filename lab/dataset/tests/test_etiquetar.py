import json, os, unittest
from lab.dataset import etiquetar

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar_json(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read())

class TestPostura(unittest.TestCase):
    def setUp(self):
        self.h = cargar_json("hallazgos.json")

    def test_servicio_expuesto(self):
        p = etiquetar.postura_de(self.h, "objetivo-vuln", "ssh")
        self.assertTrue(p["expuesto"])

    def test_servicio_no_expuesto(self):
        p = etiquetar.postura_de(self.h, "puesto", "ssh")
        self.assertFalse(p["expuesto"])

    def test_nodo_desconocido_es_gris(self):
        self.assertIsNone(etiquetar.postura_de(self.h, "nodo-fantasma", "ssh"))
