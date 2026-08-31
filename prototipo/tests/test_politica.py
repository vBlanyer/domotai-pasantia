import json, os, unittest
from prototipo import politica

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def alerta():
    with open(os.path.join(FX, "alerta_vp.json"), encoding="utf-8") as f:
        return json.loads(f.read().strip())

class TestProponer(unittest.TestCase):
    def test_vp_intento_propone_bloquear_ip_del_origen(self):
        acc, params = politica.proponer("vp_intento_acceso", alerta())
        self.assertEqual(acc, "BLOQUEAR_IP")
        self.assertEqual(params["ip"], "192.168.1.10")

    def test_no_soportada_no_propone_accion(self):
        acc, params = politica.proponer("no_soportada", alerta())
        self.assertIsNone(acc)

    def test_fp_exposicion_inexistente_no_propone(self):
        acc, _ = politica.proponer("fp_exposicion_inexistente", alerta())
        self.assertIsNone(acc)

    def test_nunca_propone_remediacion_de_alto_impacto(self):
        # ninguna clase mapea a REINICIAR_NODO ni RESTAURAR_CONFIG (principio de mínimo impacto)
        acciones = {politica.proponer(c, alerta())[0] for c in politica.ACCION_POR_CLASE}
        self.assertNotIn("REINICIAR_NODO", acciones)
        self.assertNotIn("RESTAURAR_CONFIG", acciones)
