import unittest
from lab.banco import casos, pruebas


class TestCatalogo(unittest.TestCase):
    def test_cada_caso_tiene_id_titulo_y_nivel_valido(self):
        vistos = set()
        for c in casos.CASOS:
            self.assertTrue(c["id"] and c["titulo"], c)
            self.assertIn(c["nivel"], casos.NIVELES, c["id"])
            self.assertNotIn(c["id"], vistos, f"id duplicado: {c['id']}")
            vistos.add(c["id"])

    def test_los_casos_vivos_se_pueden_deshacer(self):
        for c in casos.CASOS:
            if c["nivel"] == "vivo":
                self.assertIn("deshacer", c, c["id"])

    def test_los_casos_vivos_solo_esperan_lo_que_se_comprueba(self):
        # Una clave de `esperado` que evaluar() no mira se da por buena en silencio.
        for c in casos.CASOS:
            if c["nivel"] == "vivo":
                self.assertLessEqual(set(c["esperado"]), set(pruebas.CLAVES_VIVO), c["id"])

    def test_todo_caso_tiene_esperado(self):
        for c in casos.CASOS:
            self.assertIn("esperado", c, c["id"])


if __name__ == "__main__":
    unittest.main()
