"""API de la vista «Conectividad»: resumen (GET), prueba, guardado (solo si la prueba pasa) y clave del
host. Sin red ni docker: el modo, el `correr` y el ejecutor se inyectan en el servidor."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from prototipo.accion import conectividad as cx
from prototipo.servicio import tablero

PERFIL = {"ip_gestion": "10.0.30.3",
          "activos": {"fw-core": {"ip": "10.0.0.1"}, "db-core": {"ip": "10.0.20.10"}, "monitor": {"ip": "10.0.30.3"}},
          "red": {"zonas": {"Borde": ["fw-core"], "Servidores": ["db-core"], "Gestion": ["monitor"]}}}
from prototipo.tests.test_conectividad import K1, F1, K2, F2, K3, F3
PUB = K1 + " conector-triaje"
KNOWN = f"10.0.0.1 {K2}\n10.0.20.10 {K3}\n"            # fw-core -> F2, db-core -> F3 (la vieja)
NUEVA_DB = K1                                              # lo que presenta db-core ahora -> F1


class _Falso:
    """Lo que el servidor ejecutaría: ficheros de claves (correr) y ssh a los equipos (ejecutor)."""
    def __init__(self):
        self.ssh = {}            # ip -> [(rc, salida), ...] por orden
        self.vistos = []         # (ip, usuario, puerto, cmd)
        self.escrito = None

    def correr(self, args, entrada=None):
        if args[:1] == ["cat"] and args[1].endswith(".pub"):
            return 0, PUB + "\n"
        if args[0] == "ssh-keyscan":
            return 0, f"10.0.20.10 {NUEVA_DB}\n"
        if args[:1] == ["cat"]:
            return 0, KNOWN
        if args[:1] == ["tee"]:
            self.escrito = entrada
            return 0, entrada
        return 1, "?"

    def ejecutor_con(self, modo, usuario=None, puerto=None):
        def ej(ip, cmd):
            self.vistos.append((ip, usuario, puerto, cmd))
            cola = self.ssh.setdefault(ip, [(0, "ok"), (1, "denegado")])
            return cola.pop(0) if len(cola) > 1 else cola[0]
        return ej


class TestConectividadWeb(unittest.TestCase):
    def _srv(self, operadores=None, modo="clave"):
        d = tempfile.mkdtemp()
        self.ruta, self.au = os.path.join(d, "conectividad.yml"), os.path.join(d, "conectividad-auditoria.jsonl")
        self.f = _Falso()
        srv = tablero.crear_servidor(tablero.EstadoTablero(), os.path.join(d, "t.jsonl"), puerto=0,
                                     estaticos=tempfile.mkdtemp(), perfil=json.loads(json.dumps(PERFIL)),
                                     operadores=operadores, ruta_conectividad=self.ruta,
                                     ruta_auditoria_conectividad=self.au)
        srv.conectividad_modo = lambda: modo
        srv.conectividad_correr = lambda m: self.f.correr
        srv.conectividad_ejecutor = self.f.ejecutor_con
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv

    def _req(self, srv, metodo, ruta, obj=None, token=None):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        c.request(metodo, ruta, json.dumps(obj) if obj is not None else None, h)
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def _eq(self, est, nombre):
        return next(e for e in est["equipos"] if e["nombre"] == nombre)

    def test_resumen(self):
        srv = self._srv({"tok": "ana"})
        st, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual(st, 200)
        self.assertEqual(est["modo"], "clave")
        self.assertEqual(est["clave"], {"huella": F1, "tipo": "ED25519", "publica": PUB})
        self.assertNotIn("PRIVATE", json.dumps(est))
        fw = self._eq(est, "fw-core")
        self.assertEqual((fw["ip"], fw["puerto"], fw["usuario"], fw["huella_fijada"], fw["protegido"]), ("10.0.0.1", 22, "triaje", F2, False))
        self.assertTrue(self._eq(est, "monitor")["protegido"])                  # canal de gestión del MDR
        self.assertTrue(est["editable"])

    def test_sin_operador_es_solo_lectura_y_no_guarda(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_CONECTIVIDAD_ABIERTA", None)
            srv = self._srv()
            self.assertFalse(self._req(srv, "GET", "/api/conectividad")[1]["editable"])
            self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222})[0], 403)
            self.assertEqual(self._req(srv, "POST", "/api/conectividad/clave-host", {"equipo": "db-core", "huella": F1})[0], 403)
        self.assertFalse(os.path.exists(self.ruta))

    def test_probar_no_guarda_y_recuerda_el_resultado(self):
        srv = self._srv({"tok": "ana"})
        st, r = self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "fw-core", "puerto": 2222}, token="tok")
        self.assertEqual((st, r["estado"], r["ok"]), (200, "verificada", True))
        self.assertEqual(self.f.vistos[0][:3], ("10.0.0.1", "triaje", 2222))    # probó con el candidato
        self.assertFalse(os.path.exists(self.ruta))
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual(self._eq(est, "fw-core")["ultima_prueba"]["estado"], "verificada")

    def test_guardar_solo_si_la_prueba_pasa(self):
        srv = self._srv({"tok": "ana"})
        self.f.ssh["10.0.0.1"] = [(255, "Permission denied (publickey).")]
        st, r = self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222, "usuario": "ops"}, token="tok")
        self.assertEqual((st, r["guardado"], r["prueba"]["estado"]), (409, False, "sin_aprovisionar"))
        self.assertFalse(os.path.exists(self.ruta))
        self.f.ssh["10.0.0.1"] = [(0, "ok"), (1, "denegado")]
        st, r = self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222, "usuario": "ops"}, token="tok")
        self.assertEqual((st, r["guardado"]), (200, True))
        self.assertEqual(cx.cargar(self.ruta)["equipos"], {"10.0.0.1": {"nombre": "fw-core", "puerto": 2222, "usuario": "ops"}})
        with open(self.au) as f:
            aud = [json.loads(l) for l in f]
        self.assertEqual((aud[-1]["operador"], aud[-1]["clave"]), ("ana", "fw-core"))
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        fw = self._eq(est, "fw-core")
        self.assertEqual((fw["puerto"], fw["usuario"], fw["ajustado"]), (2222, "ops", True))
        self.assertEqual(est["cambios"][0]["clave"], "fw-core")

    def test_validacion(self):
        srv = self._srv({"tok": "ana"})
        for cuerpo in ({"equipo": "no-existe", "puerto": 22}, {"equipo": "fw-core", "puerto": 99999},
                       {"equipo": "fw-core", "usuario": "root;id"}, {"equipo": "monitor", "puerto": 2222}):
            self.assertEqual(self._req(srv, "POST", "/api/conectividad", cuerpo, token="tok")[0], 400, cuerpo)
        self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"usuario_defecto": "a b"}, token="tok")[0], 400)

    def test_usuario_por_defecto(self):
        srv = self._srv({"tok": "ana"})
        self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"usuario_defecto": "mdr"}, token="tok")[0], 200)
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual((est["usuario_defecto"], self._eq(est, "fw-core")["usuario"]), ("mdr", "mdr"))

    def test_modo_laboratorio_no_admite_edicion(self):
        srv = self._srv({"tok": "ana"}, modo="password")
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertFalse(est["editable"])
        self.assertIsNone(est["clave"])
        self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222}, token="tok")[0], 409)

    def test_clave_del_host(self):
        srv = self._srv({"tok": "ana"})
        st, r = self._req(srv, "POST", "/api/conectividad/leer-clave-host", {"equipo": "db-core"}, token="tok")
        self.assertEqual((st, r["fijada"], r["presentada"], r["coincide"]), (200, F3, F1, False))
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/clave-host", {"equipo": "db-core", "huella": F2}, token="tok")[0], 409)
        self.assertIsNone(self.f.escrito)
        st, r = self._req(srv, "POST", "/api/conectividad/clave-host", {"equipo": "db-core", "huella": F1}, token="tok")
        self.assertEqual((st, r["huella"]), (200, F1))
        self.assertEqual(self.f.escrito, f"10.0.0.1 {K2}\n10.0.20.10 {NUEVA_DB}\n")
        with open(self.au) as f:
            self.assertEqual(json.loads(f.read().splitlines()[-1])["dimension"], "clave_host")


if __name__ == "__main__":
    unittest.main()
