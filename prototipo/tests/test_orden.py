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


PERFIL_TOPO = {
    "activos": {"objetivo-vuln": {"ip": "192.168.1.30"}, "borde": {"ip": "192.168.1.1"}},
    "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                  "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
}

class TestAislarNodo(unittest.TestCase):
    """6ª familia (FIM): AISLAR_NODO es una cuarentena REAL en el borde. Corta el reenvío del host en
    su cortafuegos perimetral (como BLOQUEAR_IP_FIREWALL), NO en el propio host —un host hoja no se
    aísla con una regla FORWARD sobre sí mismo (M3)—."""

    def test_se_ejecuta_en_el_cortafuegos_y_apunta_a_la_ip_del_host(self):
        d = {"id_decision": "d9", "activo": "objetivo-vuln", "accion_final": "AISLAR_NODO"}
        o = orden.construir(d, {"familia": "integridad_fichero"}, PERFIL_TOPO)
        self.assertEqual(o["accion_id"], "AISLAR_NODO")
        self.assertEqual(o["nodo_objetivo"], "objetivo-vuln")       # el host en cuarentena (lo que ve el operador)
        self.assertEqual(o["nodo_ip"], "192.168.1.1")               # dónde se ejecuta: el cortafuegos de borde
        self.assertEqual(o["params"], {"ip_nodo": "192.168.1.30"})  # a quién corta el reenvío: la IP del host

    def test_la_ip_del_host_sale_del_inventario_no_de_la_alerta(self):
        # M1: el host se resuelve del inventario (coherente con nodo_ip), nunca de agent.ip de la alerta.
        d = {"id_decision": "d9", "activo": "objetivo-vuln", "accion_final": "AISLAR_NODO"}
        o = orden.construir(d, {"activo_ip": "203.0.113.9"}, PERFIL_TOPO)   # IP hostil en la alerta: se ignora
        self.assertEqual(o["params"], {"ip_nodo": "192.168.1.30"})

    def test_sin_cortafuegos_de_borde_no_hay_orden(self):
        # Fail-closed: un host sin ruta a un firewall_perimetral no se puede aislar -> sin orden (el
        # filtro del perfil ya lo veta; esto es el cinturón del constructor).
        d = {"id_decision": "d9", "activo": "puesto", "accion_final": "AISLAR_NODO"}
        self.assertIsNone(orden.construir(d, {}, {"activos": {"puesto": {"ip": "10.0.0.5"}}}))

    def test_sin_perfil_no_hay_orden(self):
        d = {"id_decision": "d9", "activo": "objetivo-vuln", "accion_final": "AISLAR_NODO"}
        self.assertIsNone(orden.construir(d, {"familia": "integridad_fichero"}))
