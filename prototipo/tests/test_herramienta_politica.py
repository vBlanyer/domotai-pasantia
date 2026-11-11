"""Órdenes de mdr para politica.yml: validar, explicar y migrar (tarea 3 del plan)."""
import io, os, tempfile, unittest, yaml
from contextlib import redirect_stdout

from prototipo.herramientas import politica as hp

PERFIL = {"activos": {"web01": {"ip": "192.0.2.10"}}, "ip_gestion": "10.99.0.10",
          "origenes_legitimos": ["10.99.0.10"], "continuidad": {"umbral_confianza": 0.9, "impacto_localizado": "automatica_si_confianza",
                                                                "reversibilidad_obligatoria": True, "no_cortar_gestion": True}}


def _fichero(d, nombre, contenido):
    ruta = os.path.join(d, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        yaml.safe_dump(contenido, f, allow_unicode=True)
    return ruta


class TestOrdenes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.perfil = _fichero(self.d, "perfil.yml", PERFIL)

    def _correr(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = hp.main(list(args))
        return rc, buf.getvalue()

    def test_validar_una_politica_correcta(self):
        pol = _fichero(self.d, "politica.yml", {"respuesta_automatica": {"por_defecto": "con_analista"}})
        rc, out = self._correr("validar", pol, "--perfil", _fichero(self.d, "p2.yml", {"activos": {}}))
        self.assertEqual(rc, 0)
        self.assertIn("válida", out)

    def test_validar_un_fichero_ilegible_falla_sin_traceback(self):
        ruta = os.path.join(self.d, "politica.yml")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("confianza: [sin cerrar\n")
        rc, out = self._correr("validar", ruta, "--perfil", self.perfil)
        self.assertEqual(rc, 1)
        self.assertIn("no se puede leer", out)

    def test_validar_una_politica_incorrecta_falla(self):
        pol = _fichero(self.d, "politica.yml", {"respuesta_automatica": {"por_defecto": "siempre"}})
        rc, out = self._correr("validar", pol, "--perfil", self.perfil)
        self.assertEqual(rc, 1)
        self.assertIn("por_defecto", out)

    def test_explicar_sin_fichero_explica_el_perfil(self):
        rc, out = self._correr("explicar", "--perfil", self.perfil)
        self.assertEqual(rc, 0)
        self.assertIn("10.99.0.10", out)

    def test_migrar_saca_la_politica_del_perfil_con_copia(self):
        salida = os.path.join(self.d, "politica.yml")
        rc, out = self._correr("migrar", "--perfil", self.perfil, "--salida", salida)
        self.assertEqual(rc, 0)
        with open(salida, encoding="utf-8") as f:
            pol = yaml.safe_load(f)
        with open(self.perfil, encoding="utf-8") as f:
            perfil = yaml.safe_load(f)
        self.assertEqual(pol["confianza"]["administradores"], ["10.99.0.10"])
        self.assertNotIn("origenes_legitimos", perfil)
        self.assertTrue(os.path.exists(self.perfil + ".antes-de-migrar"))
        self.assertEqual(pol["politica"]["version"], 1)

    def test_migrar_no_toca_nada_si_el_resultado_no_seria_valido(self):
        perfil = _fichero(self.d, "p-cidr.yml", {**PERFIL, "origenes_legitimos": ["10.99.0.0/24"]})
        with open(perfil, encoding="utf-8") as f:
            antes = f.read()
        salida = os.path.join(self.d, "nueva.yml")
        rc, out = self._correr("migrar", "--perfil", perfil, "--salida", salida)
        self.assertEqual(rc, 1)
        self.assertIn("10.99.0.0/24", out)
        self.assertFalse(os.path.exists(salida))
        self.assertFalse(os.path.exists(perfil + ".antes-de-migrar"))
        with open(perfil, encoding="utf-8") as f:
            self.assertEqual(f.read(), antes)

    def test_migrar_no_pisa_una_copia_anterior(self):
        with open(self.perfil + ".antes-de-migrar", "w", encoding="utf-8") as f:
            f.write("copia de la primera migración\n")
        rc, out = self._correr("migrar", "--perfil", self.perfil, "--salida", os.path.join(self.d, "nueva.yml"))
        self.assertEqual(rc, 1)
        with open(self.perfil + ".antes-de-migrar", encoding="utf-8") as f:
            self.assertEqual(f.read(), "copia de la primera migración\n")

    def test_migrar_avisa_de_fijar_triaje_politica(self):
        rc, out = self._correr("migrar", "--perfil", self.perfil, "--salida", os.path.join(self.d, "nueva.yml"))
        self.assertEqual(rc, 0)
        self.assertIn("IMPORTANTE", out)
        self.assertIn("TRIAJE_POLITICA=" + os.path.join(self.d, "nueva.yml"), out)

    def test_migrar_no_pisa_una_politica_existente(self):
        salida = _fichero(self.d, "politica.yml", {"politica": {"version": 4}})
        rc, out = self._correr("migrar", "--perfil", self.perfil, "--salida", salida)
        self.assertEqual(rc, 1)
        self.assertIn("ya existe", out)


class TestEstado(unittest.TestCase):
    def test_sin_politica(self):
        c = hp.linea_estado({}, None)
        self.assertEqual(c["nivel"], "ok")
        self.assertIn("en el perfil", c["texto"])

    def test_con_politica_y_cambios_de_consola(self):
        d = tempfile.mkdtemp()
        pol = _fichero(d, "politica.yml", {"politica": {"version": 3, "aprobada_por": "Seguridad"}})
        _fichero(d, "politica-operativa.yml", {"overrides_por_activo": {"web01": {"automatizacion": "humano_siempre"}}})
        c = hp.linea_estado({"TRIAJE_POLITICA": pol, "TRIAJE_SALIDA": os.path.join(d, "trazas-cliente.jsonl")}, {"activos": {"web01": {}}})
        self.assertEqual(c["nivel"], "aviso")
        self.assertIn("versión 3", c["texto"])
        self.assertIn("1 cambio", c["texto"])


class TestEstadoTrasAprobar(unittest.TestCase):
    def test_los_cambios_ya_pasados_al_fichero_no_cuentan(self):
        """I2b: tras aprobar e instalar la propuesta, el overlay coincide con la política: sin aviso."""
        d = tempfile.mkdtemp()
        pol = _fichero(d, "politica.yml", {"politica": {"version": 4, "aprobada_por": "Seguridad"},
                                           "respuesta_automatica": {"por_equipo": {"web01": "con_analista"}}})
        _fichero(d, "politica-operativa.yml", {"overrides_por_activo": {"web01": {"automatizacion": "humano_siempre"}}})
        c = hp.linea_estado({"TRIAJE_POLITICA": pol, "TRIAJE_SALIDA": os.path.join(d, "trazas-cliente.jsonl")},
                            {"activos": {"web01": {}}})
        self.assertEqual(c["nivel"], "ok", c)


class TestEstadoRobusto(unittest.TestCase):
    def test_una_politica_mal_formada_no_tumba_mdr_estado(self):
        d = tempfile.mkdtemp()
        ruta = os.path.join(d, "politica.yml")
        for texto in ("confianza: [1]\n", "politica: [1]\n", "\xff\xfe".encode("latin-1").decode("latin-1")):
            with open(ruta, "w", encoding="latin-1") as f:
                f.write(texto)
            with self.subTest(texto=texto):
                c = hp.linea_estado({"TRIAJE_POLITICA": ruta}, {"activos": {"web01": {}}})
                self.assertEqual(c["nivel"], "fallo")
