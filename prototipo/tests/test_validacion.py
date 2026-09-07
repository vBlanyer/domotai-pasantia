import unittest
from prototipo import validacion

DECISION = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 0.5,
            "justificacion": "Alerta 5760 desde 192.168.1.10 ...", "accion_propuesta": "BLOQUEAR_IP",
            "accion_final": "BLOQUEAR_IP", "impacto": "localizado", "resultado_filtro": "veta"}
ALERTA = {"activo": "objetivo-vuln", "origen_ip": "192.168.1.10", "servicio": "ssh"}

class TestValidacion(unittest.TestCase):
    def test_mostrar_incluye_lo_esencial(self):
        txt = validacion.mostrar(DECISION, ALERTA)
        for frag in ("vp_intento_acceso", "0.5", "BLOQUEAR_IP", "192.168.1.10", "objetivo-vuln"):
            self.assertIn(frag, txt)

    def test_mostrar_incluye_la_tecnica_mitre_estructurada(self):
        dec = dict(DECISION)
        dec["justificacion_estructurada"] = {"tecnica_mitre": ["T1110.001"], "accion_sugerida": "BLOQUEAR_IP"}
        txt = validacion.mostrar(dec, ALERTA)
        self.assertIn("Técnica MITRE", txt)
        self.assertIn("T1110.001", txt)
        self.assertIn("Acción sugerida", txt)

    def test_pedir_aprobar(self):
        v = validacion.pedir(DECISION, ALERTA, leer=lambda _: "aprobar", escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "aprobar")
        self.assertIsNone(v["clase_nueva"])

    def test_pedir_rechazar(self):
        v = validacion.pedir(DECISION, ALERTA, leer=lambda _: "r", escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "rechazar")

    def test_respuesta_desconocida_es_rechazar(self):
        v = validacion.pedir(DECISION, ALERTA, leer=lambda _: "xyz", escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "rechazar")

    def test_pedir_reclasificar_captura_la_clase_nueva(self):
        # RF-08: el analista reclasifica y aporta la clase corregida (feedback, RF-12)
        leer = lambda p: "reclasificar" if "aprobar" in p else "fp_actividad_legitima"
        v = validacion.pedir(DECISION, ALERTA, leer=leer, escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "reclasificar")
        self.assertEqual(v["clase_nueva"], "fp_actividad_legitima")
