import os, stat, tempfile, unittest
from prototipo.herramientas import entorno

PLANTILLA = """# Cabecera
# --- Fuente ---
TRIAJE_ALERTS=/var/ossec/logs/alerts/alerts.json
TRIAJE_PERFIL=/etc/mdr/perfil.yml
#TRIAJE_ESCUCHAR=0.0.0.0:6514
#TRIAJE_PERMITIR=10.0.0.5
#TRIAJE_TRAZA_CLAVE=
#TRIAJE_CONSOLA_OPERADORES='{"<token>":"ana"}'
"""


def texto(ruta):
    with open(ruta) as f:
        return f.read()


class TestEntorno(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.ruta = os.path.join(self.d, "triaje.env")
        with open(self.ruta, "w") as f:
            f.write(PLANTILLA)

    def test_lee_solo_lo_activo_y_quita_comillas(self):
        with open(self.ruta, "a") as f:
            f.write("TRIAJE_CONSOLA_OPERADORES='{\"t1\":\"ana\"}'\n")
        v = entorno.leer(self.ruta)
        self.assertEqual(v["TRIAJE_PERFIL"], "/etc/mdr/perfil.yml")
        self.assertNotIn("TRIAJE_ESCUCHAR", v)                      # comentada: no cuenta
        self.assertEqual(v["TRIAJE_CONSOLA_OPERADORES"], '{"t1":"ana"}')

    def test_escribir_cambia_en_su_sitio_descomenta_y_conserva_comentarios(self):
        entorno.escribir(self.ruta, {"TRIAJE_PERFIL": "/etc/mdr/otro.yml", "TRIAJE_ESCUCHAR": "0.0.0.0:6514",
                                     "TRIAJE_NUEVA": "x"})
        t = texto(self.ruta)
        self.assertIn("# Cabecera\n# --- Fuente ---\n", t)
        self.assertIn("TRIAJE_PERFIL=/etc/mdr/otro.yml\n", t)
        self.assertIn("TRIAJE_ESCUCHAR=0.0.0.0:6514\n#TRIAJE_PERMITIR", t)   # donde estaba la plantilla
        self.assertTrue(t.endswith("TRIAJE_NUEVA=x\n"))
        self.assertEqual(stat.S_IMODE(os.stat(self.ruta).st_mode), 0o600)

    def test_quitar_una_variable_la_deja_comentada(self):
        entorno.escribir(self.ruta, {"TRIAJE_ALERTS": None})
        self.assertNotIn("TRIAJE_ALERTS", entorno.leer(self.ruta))
        self.assertIn("#TRIAJE_ALERTS=", texto(self.ruta))

    def test_json_entre_comillas_simples_y_vuelta_exacta(self):
        entorno.escribir(self.ruta, {"TRIAJE_CONSOLA_OPERADORES": '{"abc":"ana","def":"leo"}'})
        self.assertIn("""TRIAJE_CONSOLA_OPERADORES='{"abc":"ana","def":"leo"}'""", texto(self.ruta))
        self.assertEqual(entorno.leer(self.ruta)["TRIAJE_CONSOLA_OPERADORES"], '{"abc":"ana","def":"leo"}')

    def test_nunca_escribe_un_valor_que_systemd_leeria_mal(self):
        for malo in ("a'b", "con\nsalto", "x # comentario"):
            with self.assertRaises(ValueError):
                entorno.escribir(self.ruta, {"TRIAJE_PERFIL": malo})
        self.assertEqual(texto(self.ruta), PLANTILLA)                      # intacto

    def test_operadores(self):
        self.assertEqual(entorno.operadores({}), {})
        self.assertEqual(entorno.operadores({"TRIAJE_CONSOLA_OPERADORES": '{"t":"ana"}'}), {"t": "ana"})
        with self.assertRaises(ValueError):
            entorno.operadores({"TRIAJE_CONSOLA_OPERADORES": "{roto"})


if __name__ == "__main__":
    unittest.main()
