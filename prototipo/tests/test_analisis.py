import json, os, unittest, yaml
from prototipo import analisis

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar_json(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read().strip())
def cargar_yaml(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return yaml.safe_load(f)

class TestEnriquecer(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")
        self.hallazgos = cargar_json("hallazgos.json")
        self.perfil = cargar_yaml("perfil.yml")

    def test_postura_expuesta_para_ssh_en_objetivo(self):
        ctx = analisis.enriquecer(self.alerta, self.hallazgos, self.perfil)
        self.assertTrue(ctx["postura"]["expuesto"])

    def test_criticidad_del_perfil(self):
        ctx = analisis.enriquecer(self.alerta, self.hallazgos, self.perfil)
        self.assertEqual(ctx["criticidad"], "alta")

    def test_activo_desconocido_criticidad_media(self):
        a = dict(self.alerta); a["activo"] = "fantasma"
        ctx = analisis.enriquecer(a, self.hallazgos, self.perfil)
        self.assertEqual(ctx["criticidad"], "media")
