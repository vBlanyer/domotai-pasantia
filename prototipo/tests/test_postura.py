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


if __name__ == "__main__":
    unittest.main()
