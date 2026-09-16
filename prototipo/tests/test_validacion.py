import unittest
from prototipo import validacion

DECISION = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 0.5,
            "justificacion": "Alerta 5760 desde 192.168.1.10 ...", "accion_propuesta": "BLOQUEAR_IP",
            "accion_final": "BLOQUEAR_IP", "impacto": "localizado", "resultado_filtro": "veta"}
ALERTA = {"activo": "objetivo-vuln", "origen_ip": "192.168.1.10", "servicio": "ssh"}


class _Leer:
    """Lector de prueba: devuelve las respuestas en orden, ignorando el prompt (los dos menús —el de
    veredicto y el de clase— piden ambos 'Elige [1-N]', así que no se distinguen por el texto)."""
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)

    def __call__(self, prompt=""):
        return self.respuestas.pop(0)


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

    # --- primer prompt (veredicto) por número: 1) aprobar 2) rechazar 3) reclasificar ---
    def test_pedir_aprobar_por_numero(self):
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer("1"), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "aprobar")
        self.assertIsNone(v["clase_nueva"])

    def test_pedir_rechazar_por_numero(self):
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer("2"), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "rechazar")

    def test_primer_prompt_invalido_repregunta(self):
        # un número fuera de rango no se cuela: repregunta; luego 1 -> aprobar
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer("9", "1"), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "aprobar")

    def test_primer_prompt_en_blanco_es_rechazar(self):
        # Enter en blanco en el veredicto -> rechazar seguro (por defecto conservador)
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer(""), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "rechazar")
        self.assertIsNone(v["clase_nueva"])

    # --- submenú de clase (reclasificar = 3) ---
    def test_pedir_reclasificar_captura_la_clase_por_numero(self):
        # RF-08: 3) reclasificar y luego 1) la primera clase distinta de la actual (fp_actividad_legitima).
        # Menú cerrado: sin typos ni clases inexistentes en el feedback (RF-12).
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer("3", "1"), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "reclasificar")
        self.assertEqual(v["clase_nueva"], "fp_actividad_legitima")

    def test_menu_excluye_la_clase_actual_del_incidente(self):
        # Reclasificar es cambiar la clase, no repetirla: la actual no aparece en el submenú.
        salida = []
        validacion.pedir(DECISION, ALERTA, leer=_Leer("3", "1"), escribir=salida.append)
        menu = next(s for s in salida if s.startswith("Nueva clase:"))
        self.assertNotIn("vp_intento_acceso", menu)          # la clase actual del incidente
        for c in ("fp_actividad_legitima", "fp_exposicion_inexistente", "no_soportada"):
            self.assertIn(c, menu)

    def test_reclasificar_entrada_invalida_repregunta(self):
        # 3) reclasificar; en el submenú, 5 y 'dos' no se cuelan -> repregunta; luego 2.
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer("3", "5", "dos", "2"), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "reclasificar")
        self.assertEqual(v["clase_nueva"], "fp_exposicion_inexistente")   # la 2) del submenú

    def test_reclasificar_en_blanco_cancela_a_rechazar(self):
        # Enter en blanco en el submenú de clase = el analista se echa atrás -> rechazar, sin corregir.
        v = validacion.pedir(DECISION, ALERTA, leer=_Leer("3", ""), escribir=lambda _: None)
        self.assertEqual(v["veredicto"], "rechazar")
        self.assertIsNone(v["clase_nueva"])
