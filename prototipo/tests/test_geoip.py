import gzip, os, tempfile, unittest
from unittest import mock
from prototipo.motor import geoip, actores

FILAS = """8.8.8.0,8.8.8.255,US
1.0.0.0,1.0.0.255,AU
80.58.0.0,80.58.255.255,ES
193.0.0.0,193.0.7.255,NL
5.45.0.0,5.45.255.255,ZZ
2001:4860::,2001:4860:ffff:ffff:ffff:ffff:ffff:ffff,US
mal,formada
"""


def base_temporal(test, contenido=FILAS, nombre="dbip-country-lite-2026-11.csv.gz"):
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, nombre)
    abrir = gzip.open if nombre.endswith(".gz") else open
    with abrir(ruta, "wt", encoding="utf-8") as f:
        f.write(contenido)
    test.addCleanup(geoip.reiniciar)
    return ruta


class TestBase(unittest.TestCase):
    def test_busca_por_rango_ipv4_e_ipv6(self):
        b = geoip.leer(base_temporal(self))
        self.assertEqual(b.buscar("8.8.8.8"), "US")
        self.assertEqual(b.buscar("80.58.12.1"), "ES")
        self.assertEqual(b.buscar("193.0.7.255"), "NL")          # extremo final, incluido
        self.assertIsNone(b.buscar("193.0.8.0"))                   # justo fuera
        self.assertIsNone(b.buscar("9.9.9.9"))                     # en ningún rango
        self.assertEqual(b.buscar("2001:4860:4860::8888"), "US")

    def test_zz_y_lineas_rotas_se_ignoran(self):
        b = geoip.leer(base_temporal(self))
        self.assertIsNone(b.buscar("5.45.1.1"))                    # ZZ = sin asignar
        self.assertEqual(b.rangos, 5)

    def test_csv_sin_comprimir_tambien_vale(self):
        b = geoip.leer(base_temporal(self, nombre="paises.csv"))
        self.assertEqual(b.buscar("8.8.8.8"), "US")
        self.assertEqual(b.fuente, "csv")

    def test_la_fuente_dbip_se_reconoce_por_el_nombre(self):
        self.assertEqual(geoip.leer(base_temporal(self)).fuente, "dbip")

    def test_un_fichero_sin_rangos_validos_es_un_error(self):
        with self.assertRaises(ValueError):
            geoip.leer(base_temporal(self, contenido="hola,mundo\n"))


class TestConfiguracion(unittest.TestCase):
    def test_sin_TRIAJE_GEOIP_no_hay_base_ni_pais(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_GEOIP", None)
            geoip.reiniciar()
            self.addCleanup(geoip.reiniciar)
            self.assertIsNone(geoip.base())
            self.assertFalse(geoip.estado()["configurada"])
            self.assertIsNone(actores.geolocalizar("8.8.8.8"))
            self.assertFalse(actores.enriquecer_origen("8.8.8.8", {})["geo_base"])

    def test_con_TRIAJE_GEOIP_geolocaliza_con_nombre_y_coordenadas(self):
        with mock.patch.dict(os.environ, {"TRIAJE_GEOIP": base_temporal(self)}):
            geoip.reiniciar()
            g = actores.geolocalizar("8.8.8.8")
            self.assertEqual(g["codigo"], "US")
            self.assertEqual(g["pais"], "Estados Unidos")
            self.assertAlmostEqual(g["lat"], 37.1)
            self.assertEqual(g["fuente"], "dbip")
            self.assertTrue(actores.enriquecer_origen("8.8.8.8", {})["geo_base"])
            self.assertIsNone(actores.geolocalizar("10.0.0.5"))         # privada: nunca

    def test_una_base_ilegible_no_tumba_nada_y_se_dice(self):
        with mock.patch.dict(os.environ, {"TRIAJE_GEOIP": "/no/existe.csv.gz"}):
            geoip.reiniciar()
            self.addCleanup(geoip.reiniciar)
            self.assertIsNone(actores.geolocalizar("8.8.8.8"))
            e = geoip.estado()
            self.assertFalse(e["configurada"])
            self.assertIn("/no/existe.csv.gz", e["error"])

    def test_codigo_sin_tabla_de_paises_sale_con_su_codigo_y_sin_punto(self):
        self.assertEqual(geoip.pais("QQ"), {"pais": "QQ", "codigo": "QQ", "lat": None, "lon": None})



FILAS_ASN = '''8.8.8.0,8.8.8.255,15169,"Google LLC"
1.1.1.0,1.1.1.255,13335,"Cloudflare, Inc."
9.9.9.0,9.9.9.255,19281,
2001:4860::,2001:4860:ffff:ffff:ffff:ffff:ffff:ffff,15169,"Google LLC"
1.2.3.0,1.2.3.255,US
'''


class TestBaseAsn(unittest.TestCase):
    def test_numero_y_organizacion_con_comas(self):
        b = geoip.leer(base_temporal(self, FILAS_ASN, "dbip-asn-lite-2026-11.csv.gz"), tipo="asn")
        self.assertEqual(b.buscar("8.8.8.8"), ("AS15169", "Google LLC"))
        self.assertEqual(b.buscar("1.1.1.1"), ("AS13335", "Cloudflare, Inc."))
        self.assertEqual(b.buscar("9.9.9.9"), ("AS19281", "AS19281"))       # sin organización
        self.assertEqual(b.buscar("2001:4860:4860::8888"), ("AS15169", "Google LLC"))
        self.assertIsNone(b.buscar("1.2.3.4"))                             # fila de país: no vale
        self.assertEqual(b.rangos, 4)

    def test_una_base_de_paises_no_sirve_como_asn(self):
        with self.assertRaises(ValueError) as cm:
            geoip.leer(base_temporal(self, FILAS), tipo="asn")
        self.assertIn("AS", str(cm.exception))

    def test_asn_de_con_TRIAJE_ASN_y_sin_ella(self):
        ruta = base_temporal(self, FILAS_ASN, "dbip-asn-lite-2026-11.csv.gz")
        with mock.patch.dict(os.environ, {"TRIAJE_ASN": ruta}):
            geoip.reiniciar()
            self.assertEqual(actores.asn_de("8.8.8.8"), {"asn": "AS15169", "org": "Google LLC", "fuente": "dbip"})
            self.assertIsNone(actores.asn_de("10.0.0.5"))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_ASN", None)
            geoip.reiniciar()
            self.assertIsNone(actores.asn_de("8.8.8.8"))
            self.assertFalse(geoip.estado("asn")["configurada"])


if __name__ == "__main__":
    unittest.main()
