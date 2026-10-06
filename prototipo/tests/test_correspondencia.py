import unittest
from prototipo import correspondencia

REG = correspondencia.cargar()


class TestRecomendar(unittest.TestCase):
    def test_familia_contener_origen(self):
        r = correspondencia.recomendar("acceso_credenciales", "ssh", "vp_intento_acceso", REG)
        self.assertEqual(r["respuesta"], "contener_origen")
        self.assertEqual(r["accion_sugerida"], "BLOQUEAR_IP")
        self.assertEqual(r["servicio"], "ssh")

    def test_servicio_afina_la_familia(self):
        r = correspondencia.recomendar("acceso_credenciales", "rdp", "vp_intento_acceso", REG)
        self.assertEqual(r["respuesta"], "endurecer_servicio")
        self.assertEqual(r["accion_sugerida"], "CERRAR_SERVICIO")

    def test_enrutar_lleva_ruta(self):
        r = correspondencia.recomendar("explotacion_conocida", "http", "amenaza_enrutada", REG)
        self.assertEqual(r["respuesta"], "enrutar")
        self.assertEqual(r["ruta"], "appsec")
        self.assertIsNone(r["accion_sugerida"])

    def test_sin_recomendacion_en_fp_y_no_soportada(self):
        self.assertIsNone(correspondencia.recomendar("acceso_credenciales", "ssh", "fp_actividad_legitima", REG))
        self.assertIsNone(correspondencia.recomendar("acceso_credenciales", "ssh", "fp_exposicion_inexistente", REG))
        self.assertIsNone(correspondencia.recomendar("desconocida", "ssh", "no_soportada", REG))

    def test_familia_fuera_del_registro_sin_amenaza_es_none(self):
        self.assertIsNone(correspondencia.recomendar("plataforma", "ssh", "no_soportada", REG))

    def test_familia_sin_entrada_pero_clase_amenaza_devuelve_none(self):
        # familia no listada en por_familia, clase con amenaza -> sin respuesta -> None
        self.assertIsNone(correspondencia.recomendar("familia_inexistente", "xyz", "vp_intento_acceso", REG))

    def test_sin_servicio_usa_solo_familia(self):
        r = correspondencia.recomendar("servicio_expuesto", None, "vp_intento_acceso", REG)
        self.assertEqual(r["respuesta"], "endurecer_servicio")

    def test_registro_cachea(self):
        self.assertIs(correspondencia.registro(), correspondencia.registro())


if __name__ == "__main__":
    unittest.main()
