"""Perfil mínimo (plan del asistente de red, tarea 2): con él arranca una instalación nueva, sin equipos,
para describir la red desde la consola con el asistente."""
import io, os, tempfile, unittest
from contextlib import redirect_stdout

from prototipo.herramientas import perfil_minimo as cli
from prototipo.motor import perfil


class TestPerfilMinimo(unittest.TestCase):
    def test_perfil_minimo_valida_sin_avisos(self):
        self.assertEqual(perfil.validar(perfil.perfil_minimo("10.99.0.10", ["10.20.0.0/24"])), [])

    def test_perfil_minimo_rechaza_entradas_malas(self):
        for ip, redes in (("10.99.0", ["10.20.0.0/24"]), ("10.99.0.10", []), ("10.99.0.10", ["nope"])):
            with self.subTest(ip=ip, redes=redes), self.assertRaises(ValueError):
                perfil.perfil_minimo(ip, redes)

    def test_el_mdr_esta_en_gestion(self):
        p = perfil.perfil_minimo("10.99.0.10", ["10.20.0.0/24", "172.16.10.0/24"])
        self.assertEqual(p["red"]["zonas"]["Gestión"], ["mdr"])
        self.assertEqual(p["activos"]["mdr"]["ip"], "10.99.0.10")
        self.assertEqual(p["ip_gestion"], "10.99.0.10")
        self.assertEqual(p["redes_internas"], ["10.20.0.0/24", "172.16.10.0/24"])
        self.assertEqual(p["continuidad"], {"reversibilidad_obligatoria": True, "no_cortar_gestion": True})

    def test_cli_escribe_y_no_pisa(self):
        d = tempfile.mkdtemp()
        salida = os.path.join(d, "perfil.yml")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--gestion", "10.99.0.10", "--rango", "10.20.0.0/24", "--salida", salida]), 0)
        with open(salida, encoding="utf-8") as f:
            antes = f.read()
        self.assertIn("10.99.0.10", antes)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["--gestion", "10.99.0.11", "--rango", "10.20.0.0/24", "--salida", salida]), 1)
        self.assertIn("ya existe", out.getvalue())
        with open(salida, encoding="utf-8") as f:
            self.assertEqual(f.read(), antes)


if __name__ == "__main__":
    unittest.main()
