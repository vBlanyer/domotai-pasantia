import json, os, unittest, yaml
from lab.dataset import construir

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def texto(n):
    return open(os.path.join(FX, n), encoding="utf-8").read()

class TestConstruir(unittest.TestCase):
    def test_puebla_particion_y_etiqueta(self):
        campaña = {
            "alertas": [json.loads(texto("alerta_ssh_vp.json").strip())],
            "hallazgos": json.loads(texto("hallazgos.json")),
            "ficha": yaml.safe_load(texto("campaña.yml")),
        }
        regs = construir.construir(
            [campaña],
            particion_map={"2026-08-31-fuerzabruta": "evaluacion"},
            resoluciones={},
        )
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["etiqueta"], "VP")
        self.assertEqual(regs[0]["particion"], "evaluacion")
