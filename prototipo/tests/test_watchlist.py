import os, tempfile, unittest
from prototipo.servicio import watchlist


class TestWatchlist(unittest.TestCase):
    def _ruta(self):
        return os.path.join(tempfile.mkdtemp(), "watchlist.json")

    def test_fichero_ausente_es_lista_vacia(self):
        self.assertEqual(watchlist.cargar("/no/existe.json"), [])

    def test_agregar_valida_y_persiste(self):
        r = self._ruta()
        watchlist.agregar(r, "198.51.100.10", nota="C2 conocido", operador="ana", ts="t1")
        e = watchlist.cargar(r)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["indicador"], "198.51.100.10")
        self.assertEqual(e[0]["nota"], "C2 conocido")
        self.assertEqual(e[0]["operador"], "ana")

    def test_acepta_cidr_y_rechaza_basura(self):
        r = self._ruta()
        watchlist.agregar(r, "203.0.113.0/24")
        self.assertEqual(watchlist.cargar(r)[0]["indicador"], "203.0.113.0/24")
        with self.assertRaises(ValueError):
            watchlist.agregar(r, "no-es-ip")

    def test_no_duplica(self):
        r = self._ruta()
        watchlist.agregar(r, "198.51.100.10")
        watchlist.agregar(r, "198.51.100.10")
        self.assertEqual(len(watchlist.cargar(r)), 1)

    def test_quitar(self):
        r = self._ruta()
        watchlist.agregar(r, "198.51.100.10")
        watchlist.agregar(r, "198.51.100.11")
        watchlist.quitar(r, "198.51.100.10")
        e = watchlist.cargar(r)
        self.assertEqual([x["indicador"] for x in e], ["198.51.100.11"])


if __name__ == "__main__":
    unittest.main()
