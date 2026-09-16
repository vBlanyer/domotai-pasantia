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

    def test_pedir_reclasificar_captura_la_clase_por_numero(self):
        # RF-08: el analista reclasifica eligiendo de un menú cerrado (no texto libre): sin typos,
        # sólo clases válidas (feedback RF-12). El 1) es la primera clase distinta de la actual.
        leer = _Leer("reclasificar", ["1"])
        v = validacion.pedir(DECISION, ALERTA, leer=leer, escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "reclasificar")
        self.assertEqual(v["clase_nueva"], "fp_actividad_legitima")

    def test_menu_excluye_la_clase_actual_del_incidente(self):
        # Reclasificar es cambiar la clase, no repetirla: la actual no aparece en el menú.
        salida = []
        validacion.pedir(DECISION, ALERTA, leer=_Leer("reclasificar", ["1"]), escribir=salida.append)
        menu = next(s for s in salida if s.startswith("Nueva clase:"))
        self.assertNotIn("vp_intento_acceso", menu)          # la clase actual del incidente
        for c in ("fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada"):
            self.assertIn(c, menu)

    def test_reclasificar_entrada_invalida_repregunta(self):
        # Un número fuera de rango o basura no se cuela (era imposible con el texto libre): repregunta.
        leer = _Leer("reclasificar", ["5", "dos", "2"])
        v = validacion.pedir(DECISION, ALERTA, leer=leer, escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "reclasificar")
        self.assertEqual(v["clase_nueva"], "fp_exposicion_inexistente")   # la 2) del menú

    def test_reclasificar_en_blanco_cancela_a_rechazar(self):
        # Enter en blanco en el menú = el analista se echa atrás -> rechazar seguro, sin corregir clase.
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer("reclasificar", [""]), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "rechazar")
        self.assertIsNone(v["clase_nueva"])


class _Leer:
    """Lector de prueba: una respuesta fija al primer prompt (aprobar/rechazar/reclasificar) y una
    cola de respuestas para el menú de clases ('Elige [1-N]')."""
    def __init__(self, primera, elige):
        self.primera, self.elige = primera, list(elige)

    def __call__(self, prompt):
        if "aprobar" in prompt:
            return self.primera
        return self.elige.pop(0)
