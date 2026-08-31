import json, os, unittest
from lab.dataset import etiquetar, esquema

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar_json(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read())

def cargar_texto(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return f.read()

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

class TestEtiquetar(unittest.TestCase):
    def setUp(self):
        import yaml
        self.h = cargar_json("hallazgos.json")
        self.ficha = yaml.safe_load(cargar_texto("campaña.yml"))
        self.ssh = json.loads(cargar_texto("alerta_ssh_vp.json").strip())
        self.auditor = json.loads(cargar_texto("alerta_auditor.json").strip())

    def _reg(self, cruda):
        return esquema.normalizar_alerta(cruda, "2026-08-31-fuerzabruta")

    def test_actividad_del_auditor_es_propia(self):
        r = etiquetar.etiquetar(self._reg(self.auditor), self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "PROPIA")

    def test_fuerza_bruta_contra_servicio_expuesto_es_vp(self):
        r = etiquetar.etiquetar(self._reg(self.ssh), self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "VP")
        self.assertEqual(r["etiqueta_por"], "regla")

    def test_login_de_admin_declarado_es_fp(self):
        # mismo servicio expuesto, pero origen legítimo declarado -> FP, no VP
        admin = json.loads(cargar_texto("alerta_admin_fp.json").strip())
        r = etiquetar.etiquetar(self._reg(admin), self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "FP")

    def test_familia_fuera_del_caso_de_uso_es_no_soportada(self):
        reg = self._reg(self.ssh)
        reg["familia"] = "plataforma"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "no_soportada")

    def test_nodo_gris_sin_resolucion_es_pendiente(self):
        reg = self._reg(self.ssh)
        reg["activo"] = "nodo-fantasma"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "PENDIENTE")

    def test_nodo_gris_con_resolucion_humana(self):
        reg = self._reg(self.ssh)
        reg["activo"] = "nodo-fantasma"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {reg["id_alerta"]: "FP"})
        self.assertEqual(r["etiqueta"], "FP")
        self.assertEqual(r["etiqueta_por"], "humano")
