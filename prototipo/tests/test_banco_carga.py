import unittest

from prototipo import banco_carga


class TestBancoCarga(unittest.TestCase):
    """#12: el benchmark de carga mide el throughput del motor (ejecutor simulado, sin SSH)."""
    def test_medir_devuelve_metricas_coherentes(self):
        r = banco_carga.medir(n=50)
        self.assertEqual(r["alertas"], 50)
        self.assertGreater(r["segundos"], 0)
        self.assertGreater(r["decisiones_por_seg"], 0)
        self.assertGreaterEqual(r["incidentes"], 1)
        self.assertGreater(r["ms_por_alerta"], 0)


if __name__ == "__main__":
    unittest.main()
