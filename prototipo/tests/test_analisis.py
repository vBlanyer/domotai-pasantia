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

class TestClasificar(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")

    def test_servicio_expuesto_es_vp_intento_confianza_alta(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 1.0)

    def test_servicio_no_expuesto_es_fp_exposicion_inexistente(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": False}, "criticidad": "media"})
        self.assertEqual(r["clase"], "fp_exposicion_inexistente")

    def test_postura_gris_es_vp_intento_confianza_baja(self):
        r = analisis.clasificar(self.alerta, {"postura": None, "criticidad": "media"})
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 0.5)

    def test_familia_plataforma_es_no_soportada(self):
        a = dict(self.alerta); a["familia"] = "plataforma"
        r = analisis.clasificar(a, {"postura": None, "criticidad": "media"})
        self.assertEqual(r["clase"], "no_soportada")

    def test_prioridad_es_entero_1_a_4(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertIn(r["prioridad"], (1, 2, 3, 4))

class TestJustificar(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")

    def test_cita_campos_reales(self):
        txt = analisis.justificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"}, "vp_intento_acceso")
        self.assertIn("5760", txt)            # regla_id
        self.assertIn("192.168.1.10", txt)     # origen_ip
        self.assertIn("objetivo-vuln", txt)    # activo
        self.assertIn("ssh", txt)              # servicio

    def test_menciona_confirmacion_del_auditor(self):
        txt = analisis.justificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"}, "vp_intento_acceso")
        self.assertIn("confirma", txt.lower())
