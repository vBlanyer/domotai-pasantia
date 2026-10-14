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

    def test_vp_reconocimiento_bloquea_la_ip_igual_que_un_intento(self):
        # Recomendación #2: el reconocimiento tiene clase propia pero la MISMA acción que
        # vp_intento_acceso (bloquear la IP origen) -> la automatización no cambia.
        acc, params = politica.proponer("vp_reconocimiento", alerta())
        self.assertEqual(acc, "BLOQUEAR_IP")
        self.assertEqual(params["ip"], "192.168.1.10")

    def test_vp_integridad_aisla_el_nodo_afectado(self):
        # FIM: la respuesta no es IP ni cuenta, sino AISLAR el host comprometido (nunca_automatica ->
        # siempre validación humana). El nodo a aislar es el activo afectado (su activo_ip).
        a = alerta(); a["activo_ip"] = "10.50.0.10"
        acc, params = politica.proponer("vp_integridad", a)
        self.assertEqual(acc, "AISLAR_NODO")
        self.assertEqual(params, {"ip_nodo": "10.50.0.10"})

    def test_vp_abuso_cuenta_propone_bloquear_la_cuenta(self):
        a = alerta(); a["usuario"] = "backdoor"
        acc, params = politica.proponer("vp_abuso_cuenta", a)
        self.assertEqual(acc, "FORZAR_CAMBIO_PASS")
        self.assertEqual(params, {"usuario": "backdoor"})     # la cuenta, no la IP

    def test_no_soportada_no_propone_accion(self):
        acc, params = politica.proponer("no_soportada", alerta())
        self.assertIsNone(acc)

    def test_fp_exposicion_inexistente_no_propone(self):
        acc, _ = politica.proponer("fp_exposicion_inexistente", alerta())
        self.assertIsNone(acc)

    def test_amenaza_enrutada_no_propone_accion(self):
        from prototipo import politica
        accion, params = politica.proponer("amenaza_enrutada", {"origen_ip": "1.2.3.4"})
        self.assertIsNone(accion)
        self.assertEqual(params, {})

    def test_nunca_propone_remediacion_de_alto_impacto(self):
        # ninguna clase mapea a REINICIAR_NODO ni RESTAURAR_CONFIG (principio de mínimo impacto)
        acciones = {politica.proponer(c, alerta())[0] for c in politica.ACCION_POR_CLASE}
        self.assertNotIn("REINICIAR_NODO", acciones)
        self.assertNotIn("RESTAURAR_CONFIG", acciones)
