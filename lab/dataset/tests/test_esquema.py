import json, os, unittest
from lab.dataset import esquema

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read().strip())

class TestDerivaciones(unittest.TestCase):
    def setUp(self):
        self.ssh = cargar("alerta_ssh_vp.json")

    def test_resolver_activo_usa_hostname(self):
        self.assertEqual(esquema.resolver_activo(self.ssh), "objetivo-vuln")

    def test_resolver_activo_ignora_agent_id(self):
        # agent.id es 000 e inútil; el activo NO debe salir de ahí
        self.assertNotEqual(esquema.resolver_activo(self.ssh), "000")

    def test_resolver_activo_sin_hostname_cae_a_location(self):
        self.assertEqual(esquema.resolver_activo({"location": "172.20.20.2"}), "172.20.20.2")

    def test_servicio_ssh(self):
        self.assertEqual(esquema.servicio_de(self.ssh), "ssh")

    def test_familia_fuerza_bruta_es_acceso_credenciales(self):
        self.assertEqual(esquema.familia_de(self.ssh["rule"]), "acceso_credenciales")

    def test_familia_desconocida_es_otra(self):
        self.assertEqual(esquema.familia_de({"groups": ["algo_raro"]}), "otra")

    def test_familia_sca_es_plataforma(self):
        # M1: el ruido de autoauditoría real lleva el grupo "sca" (Security
        # Configuration Assessment), no solo rootcheck/cis/ossec.
        self.assertEqual(esquema.familia_de({"groups": ["sca"]}), "plataforma")

class TestNormalizarAlerta(unittest.TestCase):
    def setUp(self):
        self.ssh = cargar("alerta_ssh_vp.json")
        self.reg = esquema.normalizar_alerta(self.ssh, "2026-08-31-fuerzabruta")

    def test_campos_de_identidad(self):
        self.assertEqual(self.reg["campaña"], "2026-08-31-fuerzabruta")
        self.assertEqual(self.reg["fuente"], "wazuh")
        self.assertEqual(self.reg["id_alerta"], self.ssh["id"])

    def test_baseline_conservado(self):
        self.assertEqual(self.reg["nivel_wazuh"], self.ssh["rule"]["level"])
        self.assertEqual(self.reg["regla_id"], self.ssh["rule"]["id"])

    def test_evento_crudo_intacto(self):
        self.assertEqual(self.reg["evento_crudo"], self.ssh["full_log"])

    def test_activo_y_servicio(self):
        self.assertEqual(self.reg["activo"], "objetivo-vuln")
        self.assertEqual(self.reg["servicio"], "ssh")

    def test_mitre_es_lista(self):
        self.assertIsInstance(self.reg["mitre"], list)
