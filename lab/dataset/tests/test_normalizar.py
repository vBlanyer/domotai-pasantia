import os, tempfile, unittest
from lab.dataset import normalizar

FX = os.path.join(os.path.dirname(__file__), "fixtures")

class TestNormalizarFichero(unittest.TestCase):
    def test_lee_alertas_y_normaliza(self):
        # un fichero con la alerta VP y una línea basura que debe ignorarse
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(open(os.path.join(FX, "alerta_ssh_vp.json"), encoding="utf-8").read().strip() + "\n")
            f.write("línea corrupta no-json\n")
            ruta = f.name
        regs = normalizar.normalizar_fichero(ruta, "camp-x")
        os.unlink(ruta)
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["campaña"], "camp-x")
        self.assertEqual(regs[0]["activo"], "objetivo-vuln")
