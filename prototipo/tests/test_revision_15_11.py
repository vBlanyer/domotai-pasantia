"""Arreglos rápidos de la revisión del 15/11 (observaciones-revision-15-11.md #14, #15, #22)."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from prototipo.servicio import stream, tablero


class _Srv(unittest.TestCase):
    def _srv(self):
        d = tempfile.mkdtemp()
        srv = tablero.crear_servidor(tablero.EstadoTablero(), os.path.join(d, "t.jsonl"), puerto=0,
                                     estaticos=tempfile.mkdtemp(), perfil={"ip_gestion": "10.0.0.1"})
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv

    def _req(self, srv, metodo, ruta, cuerpo=None):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        c.request(metodo, ruta, cuerpo, {"Content-Type": "application/json"})
        r = c.getresponse(); r.read(); c.close()
        return r


class TestCabeceras(_Srv):
    def test_cabeceras_anti_clickjacking(self):
        srv = self._srv()
        for metodo, ruta, cuerpo in (("GET", "/api/pausa", None), ("GET", "/", None), ("GET", "/api/nada", None),
                                     ("POST", "/api/pausa", json.dumps({"pausar": False})), ("OPTIONS", "/api/pausa", None)):
            with self.subTest(ruta=ruta, metodo=metodo):
                r = self._req(srv, metodo, ruta, cuerpo)
                self.assertEqual(r.getheader("X-Frame-Options"), "DENY")
                self.assertEqual(r.getheader("Content-Security-Policy"), "frame-ancestors 'none'")


class TestCuerpoNoObjeto(_Srv):
    def test_post_cuerpo_no_objeto(self):
        srv = self._srv()
        for ruta in ("/api/pausa", "/api/aprobar", "/api/caso", "/api/watchlist", "/api/revertir-todo"):
            for cuerpo in ("[]", '"x"', "3", "{no es json"):
                with self.subTest(ruta=ruta, cuerpo=cuerpo):
                    self.assertEqual(self._req(srv, "POST", ruta, cuerpo).status, 400)


class TestAvisoConsolaAbierta(unittest.TestCase):
    CFG = {"perfil": "p.yml", "ruta": "-", "con_llm": False, "sin_lab": True, "ventana": 5, "web": True}

    def test_banner_avisa_consola_abierta(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for v in ("TRIAJE_CONSOLA_TOKEN", "TRIAJE_CONSOLA_OPERADORES"):
                os.environ.pop(v, None)
            self.assertTrue(any("consola SIN autenticación" in l for l in stream._lineas_inicio(self.CFG)))
            self.assertIn("consola SIN autenticación", stream.banner(self.CFG))
        with mock.patch.dict(os.environ, {"TRIAJE_CONSOLA_OPERADORES": '{"t": "ana"}'}):
            self.assertFalse(any("consola SIN autenticación" in l for l in stream._lineas_inicio(self.CFG)))
        sin_web = {**self.CFG, "web": False}
        self.assertFalse(any("consola" in l for l in stream._lineas_inicio(sin_web)))


if __name__ == "__main__":
    unittest.main()
