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

    def test_salta_dirs_sin_ficha_de_campaña(self):
        # lab/campañas tambien aloja capturas y regresiones sueltas (banco-*, captura-cef) sin
        # campaña.yml: no son campañas etiquetables y no deben tumbar el build del dataset.
        import tempfile
        with tempfile.TemporaryDirectory() as raiz:
            real = os.path.join(raiz, "2026-01-01-real"); os.mkdir(real)
            open(os.path.join(real, "campaña.yml"), "w").close()
            suelto = os.path.join(raiz, "2026-01-02-captura"); os.mkdir(suelto)
            self.assertTrue(construir._es_dir_campaña(real))
            self.assertFalse(construir._es_dir_campaña(suelto))

    def test_campaña_sin_particion_lanza_error_en_vez_de_particion_null(self):
        # I3: un cid ausente de particion_map no debe colarse como None.
        campaña = {
            "alertas": [json.loads(texto("alerta_ssh_vp.json").strip())],
            "hallazgos": json.loads(texto("hallazgos.json")),
            "ficha": yaml.safe_load(texto("campaña.yml")),
        }
        with self.assertRaises(ValueError):
            construir.construir([campaña], particion_map={}, resoluciones={})
