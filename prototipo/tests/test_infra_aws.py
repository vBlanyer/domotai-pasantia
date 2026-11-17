"""infra/aws: lo común a las dos variantes y el descubrimiento de sus pruebas. Cada variante (mdr/,
laboratorio/) es autosuficiente y trae sus pruebas en infra/aws/<variante>/pruebas/; aquí se cargan las
que existan, así que borrar una variante no rompe la suite (plan-aws-dos-carpetas.md)."""
import glob
import os
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(RAIZ, "infra", "aws")


def carpetas_de_pruebas(infra=INFRA):
    """Las carpetas infra/aws/<variante>/pruebas que existen."""
    return sorted(d for d in glob.glob(os.path.join(infra, "*", "pruebas")) if os.path.isdir(d))


def load_tests(loader, pruebas, patron):
    for d in carpetas_de_pruebas():
        pruebas.addTests(loader.discover(d, pattern="test_*.py", top_level_dir=d))
    return pruebas


class TestComun(unittest.TestCase):
    def test_descubre_las_pruebas_de_cada_variante(self):
        nombres = [os.path.basename(os.path.dirname(d)) for d in carpetas_de_pruebas()]
        self.assertIn("mdr", nombres)
        cargadas = unittest.TestSuite()
        load_tests(unittest.defaultTestLoader, cargadas, None)
        ids = [t.id() for s in cargadas for g in s for t in g]
        self.assertTrue(any(i.startswith("test_mdr.") for i in ids), ids[:5])


if __name__ == "__main__":
    unittest.main()
