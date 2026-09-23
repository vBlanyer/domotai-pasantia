import subprocess
import unittest
from lab.banco import demo


class TestDemo(unittest.TestCase):
    def _fake(self):
        llamadas = []
        def ejecutar(args, **kw):
            llamadas.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")
        return llamadas, ejecutar

    def test_casos_vivos_son_los_atacables(self):
        ids = [c["id"] for c in demo.casos_vivos()]
        self.assertEqual(ids, ["CASCADA", "D1", "A1", "K1", "E1"])
        self.assertTrue(all(c.get("ataque") or c.get("preparar") for c in demo.casos_vivos()))

    def test_menu_numera_los_casos(self):
        m = demo.menu(demo.casos_vivos())
        self.assertIn("1. CASCADA", m)
        self.assertIn("5. E1", m)

    def test_lanzar_ejecuta_preparar_y_luego_ataque_en_orden(self):
        llamadas, ejecutar = self._fake()
        caso = {"preparar": [("web-banking", "echo prep")], "ataque": ("internet", "echo atk")}
        demo.lanzar(caso, ejecutar=ejecutar)
        self.assertEqual(llamadas[0], ["docker", "exec", "clab-banco-web-banking", "sh", "-c", "echo prep"])
        self.assertEqual(llamadas[1], ["docker", "exec", "clab-banco-internet", "sh", "-c", "echo atk"])

    def test_deshacer_maneja_rearrancar_y_comandos(self):
        llamadas, ejecutar = self._fake()
        caso = {"deshacer": [("core-db", "REARRANCAR"), ("web-banking", "echo undo")]}
        demo.deshacer(caso, ejecutar=ejecutar)
        self.assertIn("-d", llamadas[0])                       # el rearranque va en segundo plano
        self.assertEqual(llamadas[1][-1], "echo undo")


if __name__ == "__main__":
    unittest.main()
