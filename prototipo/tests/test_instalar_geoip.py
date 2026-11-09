import gzip, os, tempfile, unittest
from prototipo.herramientas import instalar_geoip as ig


def fichero(d, nombre, contenido):
    ruta = os.path.join(d, nombre)
    with (gzip.open if nombre.endswith(".gz") else open)(ruta, "wt", encoding="utf-8") as f:
        f.write(contenido)
    return ruta


class TestInstalarGeoip(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_valida_y_copia_al_destino(self):
        origen = fichero(self.d, "dbip-country-lite-2026-11.csv.gz", "8.8.8.0,8.8.8.255,US\n1.0.0.0,1.0.0.255,AU\n")
        destino = os.path.join(self.d, "estado", "dbip-country-lite.csv.gz")
        os.makedirs(os.path.dirname(destino))
        r = ig.instalar(origen, destino)
        self.assertEqual(r["rangos"], 2)
        self.assertEqual(r["fuente"], "dbip")
        self.assertTrue(os.path.exists(destino))
        self.assertEqual(sorted(os.listdir(os.path.dirname(destino))), ["dbip-country-lite.csv.gz"])   # sin restos

    def test_un_fichero_invalido_no_toca_la_base_instalada(self):
        destino = fichero(self.d, "geoip.csv", "8.8.8.0,8.8.8.255,US\n")
        malo = fichero(self.d, "malo.csv", "esto no es una base\n")
        with self.assertRaises(SystemExit):
            ig.instalar(malo, destino)
        with open(destino) as f:
            self.assertEqual(f.read(), "8.8.8.0,8.8.8.255,US\n")

    def test_una_base_de_dbip_conserva_dbip_en_el_nombre_por_su_atribucion(self):
        # La consola reconoce DB-IP por el nombre y muestra su atribución (CC BY 4.0): sin él, no.
        origen = fichero(self.d, "dbip-country-lite-2026-11.csv.gz", "8.8.8.0,8.8.8.255,US\n")
        with self.assertRaises(SystemExit):
            ig.instalar(origen, os.path.join(self.d, "geoip.csv.gz"))

    def test_asn_se_valida_como_asn(self):
        destino = os.path.join(self.d, "dbip-asn-lite.csv.gz")
        bueno = fichero(self.d, "dbip-asn-lite-2026-11.csv.gz", '8.8.8.0,8.8.8.255,15169,"Google LLC"\n')
        self.assertEqual(ig.instalar(bueno, destino, "asn")["rangos"], 1)
        de_paises = fichero(self.d, "dbip-country-lite-2026-11.csv.gz", "8.8.8.0,8.8.8.255,US\n")
        with self.assertRaises(SystemExit):                 # una base de países no vale como ASN
            ig.instalar(de_paises, destino, "asn")

    def test_el_formato_del_destino_debe_coincidir(self):
        # Un .csv.gz instalado como .csv (o al revés) no se podría leer al arrancar.
        origen = fichero(self.d, "base.csv", "8.8.8.0,8.8.8.255,US\n")
        with self.assertRaises(SystemExit):
            ig.instalar(origen, os.path.join(self.d, "geoip.csv.gz"))


if __name__ == "__main__":
    unittest.main()
