import json
import threading
import unittest
import urllib.error
import urllib.request
from lab.banco import servicio


def _arrancar(nombre, dependencias, registro):
    srv = servicio.crear_servidor(nombre, 0, dependencias, registro.append)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"127.0.0.1:{srv.server_address[1]}"


def _salud(destino):
    try:
        with urllib.request.urlopen(f"http://{destino}/salud", timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        finally:
            e.close()


class TestSaludTransitiva(unittest.TestCase):
    def setUp(self):
        self.registro, self.servidores = [], []

    def tearDown(self):
        for s in self.servidores:
            s.shutdown(); s.server_close()

    def _nuevo(self, nombre, deps=()):
        srv, destino = _arrancar(nombre, list(deps), self.registro)
        self.servidores.append(srv)
        return srv, destino

    def test_sin_dependencias_esta_sano(self):
        _, a = self._nuevo("core-db")
        self.assertEqual(_salud(a), (200, {"servicio": "core-db", "estado": "ok", "falla": []}))

    def test_la_caida_se_propaga_en_cadena(self):
        db, a = self._nuevo("core-db")
        _, b = self._nuevo("middleware", [a])
        _, c = self._nuevo("web-banking", [b])
        self.assertEqual(_salud(c)[0], 200)
        db.shutdown(); db.server_close(); self.servidores.remove(db)
        codigo, cuerpo = _salud(c)
        self.assertEqual(codigo, 503)
        self.assertEqual(cuerpo["falla"], [b])          # web-banking ve caer a middleware
        self.assertEqual(_salud(b)[1]["falla"], [a])   # y middleware, a core-db

    def test_salud_no_se_registra_y_lo_demas_si(self):
        _, a = self._nuevo("web-banking")
        _salud(a)
        urllib.request.urlopen(f"http://{a}/login", timeout=3).read()
        self.assertEqual(len(self.registro), 1)
        self.assertIn('"GET /login HTTP/1.1" 200', self.registro[0])


class TestFunciones(unittest.TestCase):
    def test_comprobar_dependencias_con_fallo_de_red(self):
        def abrir(url, timeout):
            raise OSError("sin ruta")
        self.assertEqual(servicio.comprobar_dependencias(["10.0.0.9:1"], abrir=abrir), ["10.0.0.9:1"])

    def test_linea_de_acceso_formato_combined(self):
        l = servicio.linea_acceso("198.51.100.10", "GET", "/x?id=1", 200, 42, "curl/8", 0)
        self.assertEqual(l, '198.51.100.10 - - [01/Jan/1970:00:00:00 +0000] "GET /x?id=1 HTTP/1.1" 200 42 "-" "curl/8"')


if __name__ == "__main__":
    unittest.main()
