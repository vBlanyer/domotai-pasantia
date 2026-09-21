import unittest
from prototipo import orden

DECISION_VP = {
    "id_decision": "d1", "activo": "objetivo-vuln", "accion_final": "BLOQUEAR_IP",
    "impacto": "localizado", "justificacion": "...", "requiere_humano": False,
}
ALERTA = {"origen_ip": "192.168.1.10", "servicio": "ssh"}

class TestConstruir(unittest.TestCase):
    def test_orden_de_bloquear_ip(self):
        o = orden.construir(DECISION_VP, ALERTA)
        self.assertEqual(o["accion_id"], "BLOQUEAR_IP")
        self.assertEqual(o["nodo_objetivo"], "objetivo-vuln")
        self.assertEqual(o["nodo_ip"], "192.168.1.30")
        self.assertEqual(o["params"], {"ip": "192.168.1.10"})
        self.assertEqual(o["decision_id"], "d1")

    def test_sin_accion_devuelve_none(self):
        d = dict(DECISION_VP); d["accion_final"] = None
        self.assertIsNone(orden.construir(d, ALERTA))

    def test_la_ip_del_nodo_sale_del_perfil(self):
        d = dict(DECISION_VP, activo="web-banking")
        self.assertEqual(orden.construir(d, ALERTA, {"activos": {"web-banking": {"ip": "10.10.0.10"}}})["nodo_ip"],
                         "10.10.0.10")

    def test_sin_ip_en_el_perfil_cae_al_mapa_heredado(self):
        self.assertEqual(orden.construir(DECISION_VP, ALERTA, {"activos": {}})["nodo_ip"], "192.168.1.30")
