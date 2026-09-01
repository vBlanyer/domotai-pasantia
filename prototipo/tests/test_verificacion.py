import os, unittest
from prototipo import verificacion, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
ORDEN = {"accion_id": "BLOQUEAR_IP", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}

class TestVerificacion(unittest.TestCase):
    def test_verificado_cuando_la_regla_esta(self):
        r = verificacion.confirmar(ORDEN, CAT, lambda ip, cmd: (0, "DROP ... 192.168.1.10"))
        self.assertTrue(r["verificado"])
        self.assertIn("192.168.1.10", r["evidencia"])

    def test_no_verificado_cuando_no_esta(self):
        r = verificacion.confirmar(ORDEN, CAT, lambda ip, cmd: (1, ""))
        self.assertFalse(r["verificado"])

    def test_params_con_inyeccion_no_ejecuta(self):
        llamado = []
        def ej(ip, cmd): llamado.append(cmd); return (0, "")
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "1.2.3.4; rm -rf /"}
        r = verificacion.confirmar(orden_mala, CAT, ej)
        self.assertFalse(r["verificado"])
        self.assertEqual(llamado, [])   # el ejecutor NUNCA se llamó
