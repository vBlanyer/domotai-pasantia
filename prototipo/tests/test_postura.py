import unittest
from prototipo import postura

H = {"nodos": {"objetivo-vuln": [{"servicio": "ssh", "estado": "open"},
                                 {"servicio": "telnet", "estado": "open"}]}}


class TestPostura(unittest.TestCase):
    def test_expuesto_cuando_el_servicio_esta_abierto(self):
        p = postura.postura_de(H, "objetivo-vuln", "ssh")
        self.assertTrue(p["expuesto"])
        self.assertEqual(p["servicios_abiertos"], ["ssh", "telnet"])

    def test_no_expuesto_cuando_el_servicio_no_esta_abierto(self):
        p = postura.postura_de(H, "objetivo-vuln", "ftp")
        self.assertFalse(p["expuesto"])

    def test_servicio_desconocido_es_gris(self):     # RNF-07: no inferir
        self.assertIsNone(postura.postura_de(H, "objetivo-vuln", "desconocido"))
        self.assertIsNone(postura.postura_de(H, "objetivo-vuln", ""))

    def test_nodo_no_escaneado_es_gris(self):        # nodo ausente -> None, no FP
        self.assertIsNone(postura.postura_de(H, "fantasma", "ssh"))


class TestOtrosExpuestos(unittest.TestCase):
    def test_lista_los_otros_servicios_abiertos(self):
        p = postura.postura_de(H, "objetivo-vuln", "ssh")
        self.assertEqual(postura.otros_servicios_expuestos(p, "ssh"), ["telnet"])

    def test_vacio_si_no_hay_postura_o_no_expuesto(self):
        self.assertEqual(postura.otros_servicios_expuestos(None, "ssh"), [])
        p = postura.postura_de(H, "objetivo-vuln", "ftp")   # no expuesto
        self.assertEqual(postura.otros_servicios_expuestos(p, "ftp"), [])

    def test_resumen_capa_a_pocos_con_y_N_mas(self):
        p = {"expuesto": True, "servicios_abiertos": ["ssh", "a", "b", "c", "d", "e"]}
        r = postura.resumen_otros_expuestos(p, "ssh", tope=4)   # 5 otros -> 4 + "y 1 más"
        self.assertEqual(r, "a, b, c, d y 1 más")

    def test_resumen_vacio_sin_otros(self):
        self.assertEqual(postura.resumen_otros_expuestos({"expuesto": True, "servicios_abiertos": ["ssh"]}, "ssh"), "")


if __name__ == "__main__":
    unittest.main()
