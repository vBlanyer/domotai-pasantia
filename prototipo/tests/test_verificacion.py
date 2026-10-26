import os, unittest
from prototipo.accion import verificacion, catalogo

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

    def test_transitoria_verificado_cuando_la_conexion_murio(self):
        # MATAR_CONEXION es transitoria: la verificación `ss -tunap | grep ip` con rc!=0 (grep NO
        # encuentra la IP) = la conexión MURIÓ = acción aplicada. Invertido frente a una regla persistente.
        o = {"accion_id": "MATAR_CONEXION", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}
        r = verificacion.confirmar(o, CAT, lambda ip, cmd: (1, ""))   # grep no encuentra -> conexión muerta
        self.assertTrue(r["verificado"])

    def test_transitoria_no_verificado_si_la_conexion_sigue_viva(self):
        o = {"accion_id": "MATAR_CONEXION", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}
        r = verificacion.confirmar(o, CAT, lambda ip, cmd: (0, "ESTAB ... 192.168.1.10"))   # sigue viva
        self.assertFalse(r["verificado"])   # NO se cortó

    def test_params_con_inyeccion_no_ejecuta(self):
        llamado = []
        def ej(ip, cmd): llamado.append(cmd); return (0, "")
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "1.2.3.4; rm -rf /"}
        r = verificacion.confirmar(orden_mala, CAT, ej)
        self.assertFalse(r["verificado"])
        self.assertEqual(llamado, [])   # el ejecutor NUNCA se llamó

    def test_nodo_ip_con_inyeccion_no_ejecuta(self):
        llamado = []
        def ej(ip, cmd): llamado.append(cmd); return (0, "")
        orden_mala = {**ORDEN, "nodo_ip": "192.168.1.30; id"}
        r = verificacion.confirmar(orden_mala, CAT, ej)
        self.assertFalse(r["verificado"])
        self.assertEqual(llamado, [])
