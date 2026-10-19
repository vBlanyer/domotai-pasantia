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

    def test_integridad_fichero_recomienda_aislar_el_host(self):
        # 6ª familia (FIM): el asesor recomienda AISLAR el host (coherente con la acción AISLAR_NODO),
        # no "observar" (M2: un rótulo "observar/vigilar" contradecía la acción de cuarentena).
        r = correspondencia.recomendar("integridad_fichero", None, "vp_integridad", REG)
        self.assertEqual(r["respuesta"], "aislar_host")
        self.assertEqual(r["accion_sugerida"], "AISLAR_NODO")

    def test_denegacion_servicio_recomienda_limitar_banda(self):
        # 7ª familia (DoS): el asesor recomienda acotar la banda (contención gradual), coherente con la
        # acción LIMITAR_BANDA.
        r = correspondencia.recomendar("denegacion_servicio", None, "vp_denegacion_servicio", REG)
        self.assertEqual(r["respuesta"], "limitar_banda")
        self.assertEqual(r["accion_sugerida"], "LIMITAR_BANDA")

    def test_acceso_consumado_recomienda_cortar_la_sesion(self):
        # 8ª familia: el asesor recomienda cortar la conexión viva (coherente con MATAR_CONEXION).
        r = correspondencia.recomendar("acceso_consumado", None, "vp_acceso_consumado", REG)
        self.assertEqual(r["respuesta"], "cortar_sesion")
        self.assertEqual(r["accion_sugerida"], "MATAR_CONEXION")

    def test_exfiltracion_recomienda_bloquear_el_destino(self):
        # 9ª familia (exfiltración/C2): el asesor recomienda bloquear el destino malicioso (egreso),
        # coherente con la acción BLOQUEAR_DESTINO.
        r = correspondencia.recomendar("exfiltracion", None, "vp_exfiltracion", REG)
        self.assertEqual(r["respuesta"], "bloquear_destino")
        self.assertEqual(r["accion_sugerida"], "BLOQUEAR_DESTINO")

    def test_malware_recomienda_aislar_el_host(self):
        # 10ª familia (malware): el asesor recomienda aislar el host (coherente con AISLAR_NODO).
        r = correspondencia.recomendar("malware", None, "vp_malware", REG)
        self.assertEqual(r["respuesta"], "aislar_host")
        self.assertEqual(r["accion_sugerida"], "AISLAR_NODO")

    def test_registro_cachea(self):
        self.assertIs(correspondencia.registro(), correspondencia.registro())


if __name__ == "__main__":
    unittest.main()
