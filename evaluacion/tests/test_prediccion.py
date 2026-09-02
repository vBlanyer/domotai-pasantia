import unittest
from evaluacion import prediccion

class TestMapeo(unittest.TestCase):
    def test_es_amenaza(self):
        self.assertTrue(prediccion.es_amenaza("vp_intento_acceso"))
        self.assertTrue(prediccion.es_amenaza("vp_acceso_consumado"))
        self.assertFalse(prediccion.es_amenaza("fp_exposicion_inexistente"))
        self.assertFalse(prediccion.es_amenaza("no_soportada"))

class TestPredecirTodas(unittest.TestCase):
    def _procesar_falso(self, *a, **k):
        return {"clase":"vp_intento_acceso","prioridad":3,"confianza":0.5,
                "accion_final":"BLOQUEAR_IP","impacto":"localizado","requiere_humano":False}

    def test_predecir_todas_mapea_y_cronometra(self):
        filas = [{"id_alerta":"1","activo":"objetivo-vuln","servicio":"ssh",
                  "familia":"acceso_credenciales","timestamp":"t"}]
        res = prediccion.predecir_todas(filas, {}, {}, "prueba", None,
                                        _procesar=self._procesar_falso)
        self.assertEqual(len(res), 1)
        r = res[0]
        self.assertTrue(r["amenaza"])
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertIsInstance(r["ms"], float)
        self.assertGreaterEqual(r["ms"], 0.0)
