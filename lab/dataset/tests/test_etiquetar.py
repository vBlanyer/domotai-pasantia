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

    def test_servicio_desconocido_es_gris_aunque_el_nodo_se_conozca(self):
        # I1: la alerta no identifica el servicio atacado -> gris, no FP.
        self.assertIsNone(etiquetar.postura_de(self.h, "objetivo-vuln", "desconocido"))

    def test_servicio_vacio_es_gris(self):
        self.assertIsNone(etiquetar.postura_de(self.h, "objetivo-vuln", ""))

    def test_nodo_escaneado_sin_servicios_sigue_siendo_fp_legitimo(self):
        # I2: distinguir "escaneado, sin servicios" (FP legítimo) de "nodo
        # ausente" (gris). No debe confundirse una cosa con la otra.
        p = etiquetar.postura_de(self.h, "puesto", "ssh")
        self.assertFalse(p["expuesto"])

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

    def test_servicio_desconocido_con_nodo_conocido_es_pendiente_no_fp(self):
        # I1: familia soportada + servicio desconocido + nodo conocido ->
        # PENDIENTE (gris), nunca FP por defecto.
        reg = self._reg(self.ssh)
        reg["servicio"] = "desconocido"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {})
        self.assertEqual(r["etiqueta"], "PENDIENTE")

    def test_servicio_desconocido_con_resolucion_humana(self):
        reg = self._reg(self.ssh)
        reg["servicio"] = "desconocido"
        r = etiquetar.etiquetar(reg, self.h, self.ficha, {reg["id_alerta"]: "VP"})
        self.assertEqual(r["etiqueta"], "VP")
        self.assertEqual(r["etiqueta_por"], "humano")


class TestVerdadDeclarada(unittest.TestCase):
    HALL = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
    FICHA = {"auditor": {"ips": ["172.20.20.4"]}, "legitimos": {"ips": ["192.168.1.1"]},
             "verdad": [{"origen": "192.168.1.1", "desde": "2026-09-11T10:00:00", "hasta": "2026-09-11T10:05:00",
                         "etiqueta": "VP", "motivo": "fuerza bruta lanzada desde la IP del admin"}]}

    def _reg(self, origen, ts):
        return {"id_alerta": "x", "origen_ip": origen, "timestamp": ts, "familia": "acceso_credenciales",
                "activo": "objetivo-vuln", "servicio": "ssh"}

    def test_la_verdad_declarada_manda_sobre_el_origen_legitimo(self):
        r = etiquetar.etiquetar(self._reg("192.168.1.1", "2026-09-11T10:02:00+0000"), self.HALL, self.FICHA, {})
        self.assertEqual(r["etiqueta"], "VP"); self.assertEqual(r["etiqueta_por"], "campaña")

    def test_fuera_de_la_ventana_rigen_las_reglas(self):
        r = etiquetar.etiquetar(self._reg("192.168.1.1", "2026-09-11T11:00:00+0000"), self.HALL, self.FICHA, {})
        self.assertEqual(r["etiqueta"], "FP"); self.assertEqual(r["etiqueta_por"], "regla")

    def test_el_auditor_sigue_siendo_propio_aunque_haya_verdad(self):
        ficha = dict(self.FICHA, verdad=[dict(self.FICHA["verdad"][0], origen="172.20.20.4")])
        r = etiquetar.etiquetar(self._reg("172.20.20.4", "2026-09-11T10:02:00+0000"), self.HALL, ficha, {})
        self.assertEqual(r["etiqueta"], "PROPIA")

    def test_fuera_del_caso_de_uso_no_se_declara(self):
        reg = dict(self._reg("192.168.1.1", "2026-09-11T10:02:00+0000"), familia="plataforma")
        r = etiquetar.etiquetar(reg, self.HALL, self.FICHA, {})
        self.assertEqual(r["etiqueta"], "no_soportada")

