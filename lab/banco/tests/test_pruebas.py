import unittest
from lab.banco import pruebas as rg


class TestReglasExtra(unittest.TestCase):
    def test_ignora_politicas_y_la_regla_de_aislamiento_de_eth0(self):
        salida = ("-P INPUT ACCEPT\n-P FORWARD ACCEPT\n-P OUTPUT ACCEPT\n"
                  "-A INPUT -i eth0 -p tcp -j DROP\n-A INPUT -s 10.40.0.10/32 -j DROP\n")
        self.assertEqual(rg.reglas_extra(salida), ["-A INPUT -s 10.40.0.10/32 -j DROP"])

    def test_estado_base_sin_reglas(self):
        self.assertEqual(rg.reglas_extra("-P INPUT ACCEPT\n-A INPUT -i eth0 -p tcp -j DROP\n"), [])


class TestCaidos(unittest.TestCase):
    def test_conjunto_de_caidos(self):
        m = {"t": "x", "estados": {"core-db": "ok", "middleware": "caido", "atm": "caido"}}
        self.assertEqual(rg.caidos(m), {"middleware", "atm"})

    def test_sin_muestra_es_none(self):
        self.assertIsNone(rg.caidos(None))


class TestLector(unittest.TestCase):
    def test_contesta_menu_y_escalada_por_separado(self):
        leer = rg.Lector(menu="1", escalada="s")
        self.assertEqual(leer("Elige [1-3]: "), "1")
        self.assertEqual(leer("¿aprobar la ejecución? [s/N] "), "s")
        self.assertEqual([p for p, _ in leer.preguntas], ["menu", "escalada"])

    def test_pregunta_no_prevista_se_rechaza_y_se_anota(self):
        leer = rg.Lector()
        self.assertEqual(leer("Elige [1-3]: "), "")          # vacio = rechazar, lo seguro
        self.assertEqual(leer.preguntas, [("menu", "")])


class TestFuente(unittest.TestCase):
    def test_filtra_por_ip_del_atacante_y_para(self):
        lineas = ['{"data":{"srcip":"198.51.100.10"}}', '{"data":{"srcip":"10.0.0.9"}}', None,
                  '{"data":{"srcip":"198.51.100.10"}}']
        vistas = []
        for l in rg.fuente_filtrada(iter(lineas), "198.51.100.10", parar=lambda: len(vistas) >= 2):
            vistas.append(l)
        self.assertEqual(vistas, ['{"data":{"srcip":"198.51.100.10"}}', None])


REG_K1 = {"requiere_humano": True, "accion_final": "BLOQUEAR_IP", "veredicto_humano": "aprobar",
          "impacto_determinado": {"activos_afectados_en_cascada": []}, "escalada": None}


class TestEvaluar(unittest.TestCase):
    def test_k1_reproduce_el_fallo_conocido(self):
        esperado = {"requiere_humano": True, "veredicto": "aprobar", "prediccion_cascada": [],
                    "regla": ("core-db", "-A INPUT -s 10.40.0.10/32 -j DROP"),
                    "caen": {"middleware", "web-banking", "api-movil", "atm"}, "preguntas": 1}
        fallos = rg.evaluar(esperado, REG_K1, {"core-db": ["-A INPUT -s 10.40.0.10/32 -j DROP"]},
                            {"middleware", "web-banking", "api-movil", "atm"}, [("menu", "1")])
        self.assertEqual(fallos, [])

    def test_detecta_cada_diferencia(self):
        esperado = {"requiere_humano": False, "accion_final": "BLOQUEAR_IP", "preguntas": 0,
                    "regla": ("web-banking", "-A INPUT -s 198.51.100.10/32 -j DROP"), "caen": set()}
        fallos = rg.evaluar(esperado, REG_K1, {"web-banking": []}, {"atm"}, [("menu", "")])
        texto = " | ".join(fallos)
        self.assertIn("requiere_humano", texto)
        self.assertIn("preguntas", texto)
        self.assertIn("regla", texto)
        self.assertIn("atm", texto)

    def test_escalada(self):
        reg = dict(REG_K1, escalada={"escalado": True, "dispositivo_ejecutor": "fw-core"})
        esperado = {"escalado": True, "dispositivo_ejecutor": "fw-core"}
        self.assertEqual(rg.evaluar(esperado, reg, {}, set(), []), [])
        self.assertTrue(rg.evaluar({"dispositivo_ejecutor": "fw-edge"}, reg, {}, set(), []))

    def test_sin_registro_es_un_fallo(self):
        self.assertEqual(rg.evaluar({"requiere_humano": True}, None, {}, set(), []),
                         ["el prototipo no produjo ninguna decision (sin alerta de Wazuh o sin incidente)"])


class TestFalloEsperado(unittest.TestCase):
    def test_fallo_esperado_presente_es_ok(self):
        # el prototipo NO predice la cascada (fallo K1): con fallo_esperado, eso es OK
        r = rg.veredicto_caso({"fallo_esperado": "K1: no predice la cascada"}, ["prediccion_cascada: ..."])
        self.assertEqual(r, ("OK", ["fallo conocido reproducido: K1: no predice la cascada"]))

    def test_fallo_esperado_ausente_es_fallo(self):
        r = rg.veredicto_caso({"fallo_esperado": "K1: no predice la cascada"}, [])
        self.assertEqual(r[0], "FALLO")
        self.assertIn("ya no ocurre", r[1][0])

    def test_sin_fallo_esperado_los_fallos_son_fallo(self):
        self.assertEqual(rg.veredicto_caso({}, ["x"]), ("FALLO", ["x"]))
        self.assertEqual(rg.veredicto_caso({}, []), ("OK", []))


if __name__ == "__main__":
    unittest.main()
