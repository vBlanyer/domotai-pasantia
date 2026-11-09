import os, shutil, tempfile, unittest
from prototipo.herramientas import configurar, entorno

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLANTILLA_ENV = os.path.join(RAIZ, "deploy", "triaje.env.ejemplo")
PLANTILLA_PERFIL = os.path.join(RAIZ, "deploy", "perfil.ejemplo.yml")


class Guion:
    """Respuestas por orden a las preguntas del asistente ('' = aceptar el valor por defecto)."""
    def __init__(self, *respuestas):
        self.respuestas, self.preguntas = list(respuestas), []

    def __call__(self, texto, defecto=""):
        self.preguntas.append(texto)
        r = self.respuestas.pop(0) if self.respuestas else ""
        return r or defecto


class Sistema:
    def __init__(self):
        self.ordenes = []

    def __call__(self, args, **kw):
        self.ordenes.append(list(args))
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()


class TestConfigurar(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.env = os.path.join(self.d, "triaje.env")
        shutil.copy(PLANTILLA_ENV, self.env)
        self.perfil = os.path.join(self.d, "perfil.yml")
        self.alerts = os.path.join(self.d, "alerts.json")
        open(self.alerts, "w").close()
        self.dicho = []

    def _correr(self, guion, sistema=None, perfil_existe=True):
        if perfil_existe:
            shutil.copy(PLANTILLA_PERFIL, self.perfil)
        self.sistema = sistema or Sistema()
        return configurar.configurar(self.env, preguntar=guion, decir=self.dicho.append, ejecutar=self.sistema,
                                     plantilla_perfil=PLANTILLA_PERFIL, salud=lambda p: {"ok": True},
                                     instalar_base=lambda *a: {"rangos": 1, "fuente": "dbip"})

    def test_alertas_por_fichero_con_hmac_nuevo_y_arranque(self):
        rc = self._correr(Guion(self.perfil, "1", self.alerts, "", ""))
        self.assertEqual(rc, 0)
        v = entorno.leer(self.env)
        self.assertEqual(v["TRIAJE_PERFIL"], self.perfil)
        self.assertEqual(v["TRIAJE_ALERTS"], self.alerts)
        self.assertNotIn("TRIAJE_ESCUCHAR", v)
        self.assertEqual(len(v["TRIAJE_TRAZA_CLAVE"]), 64)
        self.assertEqual(v["TRIAJE_SSH_MODO"], "directo")
        self.assertIn(["systemctl", "enable", "mdr-triaje"], self.sistema.ordenes)
        self.assertIn(["systemctl", "restart", "mdr-triaje"], self.sistema.ordenes)
        self.assertTrue(any(v["TRIAJE_TRAZA_CLAVE"] in t for t in self.dicho))     # se muestra una vez

    def test_alertas_por_red_con_tls_y_ip_mal_escrita_se_repregunta(self):
        self._correr(Guion(self.perfil, "2", "6514", "10.0.0.300", "10.0.0.5,10.0.0.6",
                           "/etc/mdr/tls/mdr.crt", "/etc/mdr/tls/mdr.key", "", "", ""))
        v = entorno.leer(self.env)
        self.assertEqual(v["TRIAJE_ESCUCHAR"], "0.0.0.0:6514")
        self.assertEqual(v["TRIAJE_PERMITIR"], "10.0.0.5,10.0.0.6")
        self.assertEqual(v["TRIAJE_TLS_CERT"], "/etc/mdr/tls/mdr.crt")
        self.assertEqual(v["TRIAJE_TLS_CLAVE"], "/etc/mdr/tls/mdr.key")
        self.assertNotIn("TRIAJE_TLS_CA", v)
        self.assertTrue(any("10.0.0.300" in t for t in self.dicho))

    def test_la_clave_de_la_traza_no_se_cambia_nunca(self):
        entorno.escribir(self.env, {"TRIAJE_TRAZA_CLAVE": "ab" * 32})
        self._correr(Guion(self.perfil, "1", self.alerts, "", ""))
        self.assertEqual(entorno.leer(self.env)["TRIAJE_TRAZA_CLAVE"], "ab" * 32)

    def test_sin_perfil_copia_la_plantilla_y_no_arranca(self):
        rc = self._correr(Guion(self.perfil, "s", "1", self.alerts, "", ""), perfil_existe=False)
        self.assertTrue(os.path.isfile(self.perfil))
        self.assertNotIn(["systemctl", "restart", "mdr-triaje"], self.sistema.ordenes)
        self.assertTrue(any("Edítala" in t for t in self.dicho))
        self.assertEqual(rc, 0)

    def test_las_bases_se_instalan_si_se_da_el_fichero(self):
        instaladas = []
        shutil.copy(PLANTILLA_PERFIL, self.perfil)
        configurar.configurar(self.env, preguntar=Guion(self.perfil, "1", self.alerts, "/tmp/paises.csv.gz", "/tmp/asn.csv.gz"),
                              decir=self.dicho.append, ejecutar=Sistema(), plantilla_perfil=PLANTILLA_PERFIL,
                              salud=lambda p: {"ok": True},
                              instalar_base=lambda origen, destino, tipo: instaladas.append((origen, tipo)) or {"rangos": 1, "fuente": "dbip"})
        self.assertEqual(instaladas, [("/tmp/paises.csv.gz", "pais"), ("/tmp/asn.csv.gz", "asn")])

    def test_es_repetible_y_respeta_lo_que_no_pregunta(self):
        entorno.escribir(self.env, {"TRIAJE_CONSOLA_OPERADORES": '{"t":"ana"}', "TRIAJE_FALLO_RAPIDO": "1"})
        self._correr(Guion(self.perfil, "1", self.alerts, "", ""))
        self._correr(Guion("", "", "", "", ""), perfil_existe=False)              # Enter a todo
        v = entorno.leer(self.env)
        self.assertEqual(v["TRIAJE_CONSOLA_OPERADORES"], '{"t":"ana"}')
        self.assertEqual(v["TRIAJE_FALLO_RAPIDO"], "1")
        self.assertEqual(v["TRIAJE_ALERTS"], self.alerts)


if __name__ == "__main__":
    unittest.main()
