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
