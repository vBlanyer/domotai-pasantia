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
