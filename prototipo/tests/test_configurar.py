import os, shutil, tempfile, unittest
from prototipo.herramientas import configurar, entorno

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLANTILLA_ENV = os.path.join(RAIZ, "deploy", "triaje.env.ejemplo")
PLANTILLA_PERFIL = os.path.join(RAIZ, "deploy", "perfil.ejemplo.yml")
PLANTILLA_POLITICA = os.path.join(RAIZ, "deploy", "politica.ejemplo.yml")


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
                                     plantilla_perfil=PLANTILLA_PERFIL, plantilla_politica=PLANTILLA_POLITICA, salud=lambda p: {"ok": True},
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
        rc = self._correr(Guion(self.perfil, "p", "", "", "1", self.alerts, "", ""), perfil_existe=False)
        self.assertTrue(os.path.isfile(self.perfil))
        self.assertNotIn(["systemctl", "restart", "mdr-triaje"], self.sistema.ordenes)
        self.assertTrue(any("Edítala" in t for t in self.dicho))
        self.assertEqual(rc, 0)

    def test_con_perfil_nuevo_instala_la_politica_con_los_administradores_y_socios(self):
        import yaml
        from prototipo.motor import politica_empresa as pe
        self._correr(Guion(self.perfil, "p", "10.99.0.10, 10.99.0.11", "203.0.113.7, nope, 198.51.100.0/24",
                           "1", self.alerts, "", ""), perfil_existe=False)
        ruta = os.path.join(self.d, "politica.yml")
        self.assertEqual(entorno.leer(self.env)["TRIAJE_POLITICA"], ruta)
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
        self.assertIn("# ", texto)                                  # conserva los comentarios de la plantilla
        conf = yaml.safe_load(texto)["confianza"]
        self.assertEqual(conf["administradores"], ["10.99.0.10", "10.99.0.11"])
        self.assertEqual(conf["socios_criticos"], ["203.0.113.7", "198.51.100.0/24"])
        self.assertTrue(any("nope" in t for t in self.dicho))       # lo mal escrito se avisa y se omite
        with open(self.perfil, encoding="utf-8") as f:
            self.assertEqual(pe.validar_politica(yaml.safe_load(texto), yaml.safe_load(f), {}), [])

    def test_sin_perfil_escribe_el_minimo_y_arranca(self):
        import yaml
        from prototipo.motor import perfil as perfilm
        self._correr(Guion(self.perfil, "m", "10.99.0.10", "10.20.0.0/24, nope, 172.16.10.0/24", "1", self.alerts, "", ""),
                     perfil_existe=False)
        with open(self.perfil, encoding="utf-8") as f:
            self.assertEqual(yaml.safe_load(f), perfilm.perfil_minimo("10.99.0.10", ["10.20.0.0/24", "172.16.10.0/24"]))
        self.assertTrue(any("nope" in t for t in self.dicho))
        self.assertIn(["systemctl", "restart", "mdr-triaje"], self.sistema.ordenes)
        self.assertNotIn("TRIAJE_POLITICA", entorno.leer(self.env))   # la plantilla de política nombra equipos que no hay

    def test_perfil_minimo_sin_ip_valida_no_escribe_ni_arranca(self):
        self._correr(Guion(self.perfil, "m", "10.99.0", "10.20.0.0/24", "1", self.alerts, "", ""), perfil_existe=False)
        self.assertFalse(os.path.exists(self.perfil))
        self.assertNotIn(["systemctl", "restart", "mdr-triaje"], self.sistema.ordenes)

    def test_con_perfil_existente_no_toca_la_politica(self):
        self._correr(Guion(self.perfil, "1", self.alerts, "", ""))
        self.assertNotIn("TRIAJE_POLITICA", entorno.leer(self.env))
        self.assertFalse(os.path.exists(os.path.join(self.d, "politica.yml")))

    def test_perfil_nuevo_no_pisa_una_politica_que_ya_existe(self):
        ruta = os.path.join(self.d, "politica.yml")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("politica: {version: 7}\n")
        self._correr(Guion(self.perfil, "p", "", "", "1", self.alerts, "", ""), perfil_existe=False)
        with open(ruta, encoding="utf-8") as f:
            self.assertEqual(f.read(), "politica: {version: 7}\n")
        self.assertEqual(entorno.leer(self.env)["TRIAJE_POLITICA"], ruta)

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
