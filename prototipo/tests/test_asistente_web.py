"""API del asistente de red (plan, tarea 5): fail-closed como Conectividad, el escaneo en segundo plano y
auditado en la traza, el borrador persistente y una propuesta que nunca escribe nada."""
import http.client
import json
import os
import tempfile
import threading
import time
import unittest

import yaml

from prototipo.accion import catalogo as catm
from prototipo.motor import perfil as perfilm
from prototipo.servicio import tablero
from prototipo.tests.test_descubrimiento import _correr_falso

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = catm.cargar_catalogo(os.path.join(RAIZ, "catalogo.yml"))
PERFIL = perfilm.perfil_minimo("10.99.0.10", ["172.16.10.0/24", "10.20.0.0/24", "10.0.0.0/24", "10.99.0.0/24"])
PETICION = {"rangos": PERFIL["redes_internas"], "externo": "198.51.100.10", "ritmo": "suave", "puertos": "comunes",
            "autorizado": True}


class _Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def _srv(self, correr=None, operadores=None):
        srv = tablero.crear_servidor(tablero.EstadoTablero(), os.path.join(self.d, "trazas-x.jsonl"), puerto=0,
                                     estaticos=tempfile.mkdtemp(), perfil=json.loads(json.dumps(PERFIL)), catalogo=CAT,
                                     operadores={"tok": "ana"} if operadores is None else operadores)
        srv.asistente_correr = correr or _correr_falso()
        self.en_traza = []
        srv.estado.fijar_auditor(self.en_traza.append)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv

    def _req(self, srv, metodo, ruta, obj=None, token="tok"):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        c.request(metodo, ruta, json.dumps(obj) if obj is not None else None, h)
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def _esperar(self, srv, plazo=10):
        fin = time.time() + plazo
        while time.time() < fin:
            st, est = self._req(srv, "GET", "/api/asistente")
            if not est["escaneando"]:
                return est
            time.sleep(0.05)
        self.fail("el escaneo no terminó")


class TestAsistenteWeb(_Base):
    def test_sin_operador_403(self):
        srv = self._srv()                                           # con mapa: sin token, el muro de la consola
        st, _ = self._req(srv, "POST", "/api/asistente/escanear", PETICION, token=None)
        self.assertEqual(st, 401)
        abierta = self._srv(operadores={})                          # sin mapa ni opt-in: el nombre del cuerpo no basta
        st, _ = self._req(abierta, "POST", "/api/asistente/escanear", {**PETICION, "operador": "ana"}, token=None)
        self.assertEqual(st, 403)
        st, _ = self._req(abierta, "POST", "/api/asistente/borrador", {"cambios": {}, "operador": "ana"}, token=None)
        self.assertEqual(st, 403)

    def test_escanear_rechaza_entradas_hostiles(self):
        llamadas = []
        srv = self._srv(correr=_correr_falso(llamadas))
        for cambio in ({"rangos": ["10.0.0.0/24 --script=x"]}, {"rangos": ["8.8.8.0/24"]}, {"puertos": "22;rm"},
                       {"externo": "-oX"}):
            st, r = self._req(srv, "POST", "/api/asistente/escanear", {**PETICION, **cambio})
            self.assertEqual(st, 400, cambio)
        self.assertEqual(llamadas, [])

    def test_sin_autorizacion_400(self):
        srv = self._srv()
        st, r = self._req(srv, "POST", "/api/asistente/escanear", {**PETICION, "autorizado": False})
        self.assertEqual(st, 400)
        self.assertIn("autoriz", r["error"])

    def test_escanear_y_ver_el_borrador(self):
        srv = self._srv()
        st, r = self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        self.assertEqual((st, r["escaneando"]), (202, True))
        est = self._esperar(srv)
        self.assertIsNone(est["error"])
        self.assertEqual(len(est["descubrimiento"]["equipos"]), 12)
        self.assertEqual(est["descubrimiento"]["operador"], "ana")
        self.assertIn("10.0.0.2", est["borrador"]["equipos"])
        self.assertEqual(est["por_defecto"], {"gestion": "10.99.0.10", "rangos": PERFIL["redes_internas"]})

    def test_segundo_escaneo_simultaneo_409(self):
        suelta = threading.Event()
        base = _correr_falso()

        def lento(args):
            suelta.wait(5)
            return base(args)
        srv = self._srv(correr=lento)
        self.assertEqual(self._req(srv, "POST", "/api/asistente/escanear", PETICION)[0], 202)
        self.assertEqual(self._req(srv, "POST", "/api/asistente/escanear", PETICION)[0], 409)
        suelta.set()
        self._esperar(srv)

    def test_fallo_de_nmap_conserva_el_descubrimiento_anterior(self):
        estado = {"falla": False}
        base = _correr_falso()
        srv = self._srv(correr=lambda args: (1, "QUITTING!") if estado["falla"] else base(args))
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        primero = self._esperar(srv)
        estado["falla"] = True
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        segundo = self._esperar(srv)
        self.assertIn("QUITTING", segundo["error"])
        self.assertEqual(segundo["descubrimiento"]["fecha"], primero["descubrimiento"]["fecha"])
        self.assertEqual(segundo["borrador"], primero["borrador"])

    def test_borrador_persiste_tras_reiniciar(self):
        srv = self._srv()
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        self._esperar(srv)
        st, b = self._req(srv, "POST", "/api/asistente/borrador", {"cambios": {"10.0.0.2": {"nombre": "fw-interno"}}})
        self.assertEqual((st, b["borrador"]["equipos"]["10.0.0.2"]["nombre"], b["rechazados"]), (200, "fw-interno", []))
        st, r = self._req(srv, "POST", "/api/asistente/borrador", {"cambios": {"10.0.0.2": {"papel": "dios"}}})
        self.assertEqual((st, [x["campo"] for x in r["rechazados"]]), (200, ["papel"]))
        self.assertEqual(r["borrador"]["equipos"]["10.0.0.2"]["papel"], "cortafuegos")
        otro = self._srv()
        _, est = self._req(otro, "GET", "/api/asistente")
        self.assertEqual(est["borrador"]["equipos"]["10.0.0.2"]["nombre"], "fw-interno")
        ruta = os.path.join(self.d, "asistente-borrador.json")
        self.assertEqual(oct(os.stat(ruta).st_mode & 0o777), "0o600")

    def test_propuesta_no_escribe_nada(self):
        srv = self._srv()
        st, _ = self._req(srv, "GET", "/api/asistente/propuesta")
        self.assertEqual(st, 404)
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        self._esperar(srv)
        antes = sorted(os.listdir(self.d))
        st, p = self._req(srv, "GET", "/api/asistente/propuesta")
        self.assertEqual(st, 200)
        self.assertEqual(sorted(os.listdir(self.d)), antes)
        self.assertEqual(srv.perfil, PERFIL)                                 # el servicio sigue con su perfil
        self.assertEqual(yaml.safe_load(p["perfil_yaml"])["ip_gestion"], "10.99.0.10")
        self.assertIn("nodos", json.loads(p["postura_json"]))
        self.assertIn("confianza", yaml.safe_load(p["politica_yaml"]))
        self.assertTrue(p["validacion"]["errores"])                          # aún sin nombres
        self.assertIn("nodos", p["red"])

    def test_el_escaneo_queda_en_la_traza(self):
        srv = self._srv()
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        self._esperar(srv)
        self._req(srv, "POST", "/api/asistente/borrador", {"cambios": {"10.0.0.2": {"nombre": "fw-interno"}}})
        acciones = [(r["tipo"], r["operador"], r["accion"]) for r in self.en_traza]
        self.assertEqual(acciones, [("auditoria_asistente", "ana", "escaneo"), ("auditoria_asistente", "ana", "escaneo_fin"),
                                    ("auditoria_asistente", "ana", "borrador")])
        self.assertEqual(self.en_traza[0]["detalle"]["rangos"], PERFIL["redes_internas"])
        self.assertTrue(self.en_traza[0]["id_decision"].startswith("asistente~"))
        self.assertIn("auditoria_asistente", tablero._NO_DECISIONES)
        json.dumps(self.en_traza)                                            # la traza lo puede escribir

    def test_nombres_del_siem_vienen_de_la_traza(self):
        with open(os.path.join(self.d, "trazas-x.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"id_decision": "d1", "activo": "srv-web01", "clase": "no_soportada"}) + "\n")
        srv = self._srv()
        _, est = self._req(srv, "GET", "/api/asistente")
        self.assertEqual(est["nombres_siem"], ["srv-web01"])

    def test_nombres_del_siem_incluyen_las_decisiones_pendientes(self):
        """Ensayo en vivo: la primera alerta de un equipo queda pendiente del analista y aún no está en la
        traza; su nombre ya es útil para el asistente."""
        srv = self._srv()
        srv.async_web = True
        srv.estado.encolar_decision({"clave": ("198.51.100.10", "acceso_credenciales"), "severidad": 4, "activo": "srv-web01"})
        _, est = self._req(srv, "GET", "/api/asistente")
        self.assertEqual(est["nombres_siem"], ["srv-web01"])

    def test_un_escaneo_de_mdr_descubrir_se_revisa_en_la_consola(self):
        """`sudo mdr descubrir --salida <junto a la traza>/asistente-descubrimiento.json` (servicio sin
        privilegios): la consola lo toma, propone su borrador y deja revisarlo y exportarlo."""
        import shutil
        shutil.copy(os.path.join(os.path.dirname(__file__), "fixtures", "nmap", "descubrimiento.json"),
                    os.path.join(self.d, "asistente-descubrimiento.json"))
        srv = self._srv()
        _, est = self._req(srv, "GET", "/api/asistente")
        self.assertIn("10.0.0.2", est["borrador"]["equipos"])
        st, b = self._req(srv, "POST", "/api/asistente/borrador", {"cambios": {"10.0.0.2": {"nombre": "fw-interno"}}})
        self.assertEqual((st, b["borrador"]["equipos"]["10.0.0.2"]["nombre"]), (200, "fw-interno"))
        self.assertEqual(self._req(srv, "GET", "/api/asistente/propuesta")[0], 200)

    def test_un_escaneo_importado_queda_en_la_traza_una_vez(self):
        import shutil
        destino = os.path.join(self.d, "asistente-descubrimiento.json")
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "nmap", "descubrimiento.json"), encoding="utf-8") as f:
            desc = {**json.load(f), "origen": "cli", "operador": "root-tecnico"}
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(desc, f)
        srv = self._srv()
        self._req(srv, "GET", "/api/asistente")
        self._req(srv, "GET", "/api/asistente")
        importados = [r for r in self.en_traza if r["accion"] == "escaneo_importado"]
        self.assertEqual(len(importados), 1)
        self.assertEqual((importados[0]["operador"], importados[0]["detalle"]["rangos"]), ("root-tecnico", desc["rangos"]))
        self.assertEqual(oct(os.stat(destino).st_mode & 0o777), "0o600")

    def test_propuesta_con_gestion_rota_no_da_500(self):
        with open(os.path.join(self.d, "asistente-descubrimiento.json"), "w", encoding="utf-8") as f:
            json.dump({"version": 1, "fecha": "t", "gestion": "foo", "rangos": ["10.20.0.0/24"], "equipos": [],
                       "salida": None, "traceroute": False}, f)
        st, r = self._req(self._srv(), "GET", "/api/asistente/propuesta")
        self.assertEqual(st, 409)

    def test_laboratorio_abierto_sin_mapa(self):
        from unittest import mock
        srv = self._srv(operadores={})
        with mock.patch.dict(os.environ, {"TRIAJE_ASISTENTE_ABIERTO": "1"}):
            st, _ = self._req(srv, "POST", "/api/asistente/escanear", {**PETICION, "operador": "lab"}, token=None)
        self.assertEqual(st, 202)
        self._esperar(srv)


if __name__ == "__main__":
    unittest.main()


class TestRevision23_11(_Base):
    """Errores de la prueba completa del 23/11 (asistente de red)."""

    def _escaneado(self, **kw):
        srv = self._srv(**kw)
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        self._esperar(srv)
        return srv

    def test_un_lote_con_un_campo_malo_guarda_los_buenos(self):
        srv = self._escaneado()
        st, r = self._req(srv, "POST", "/api/asistente/borrador",
                          {"cambios": {"10.99.0.1": {"nombre": "fw core ñ"}, "10.0.0.2": {"nombre": "fw-interno"}}})
        self.assertEqual(st, 200)
        self.assertEqual(r["borrador"]["equipos"]["10.0.0.2"]["nombre"], "fw-interno")
        self.assertEqual([(x["ip"], x["campo"]) for x in r["rechazados"]], [("10.99.0.1", "nombre")])
        _, est = self._req(srv, "GET", "/api/asistente")
        self.assertEqual(est["borrador"]["equipos"]["10.0.0.2"]["nombre"], "fw-interno")

    def test_cambios_mal_formados_400(self):
        srv = self._escaneado()
        st, _ = self._req(srv, "POST", "/api/asistente/borrador", {"cambios": ["x"]})
        self.assertEqual(st, 400)

    def test_un_descubrimiento_que_el_servicio_no_puede_leer_se_dice(self):
        # «sudo mdr descubrir» sin el arreglo dejaba el fichero de root en 0600: la consola lo ignoraba en silencio.
        srv = self._escaneado()
        ruta = os.path.join(self.d, "asistente-descubrimiento.json")
        os.chmod(ruta, 0)
        self.addCleanup(os.chmod, ruta, 0o600)
        if os.access(ruta, os.R_OK):
            self.skipTest("como root se puede leer igual")
        st, est = self._req(srv, "GET", "/api/asistente")
        self.assertEqual(st, 200)
        self.assertIn("no se puede leer", est["aviso_lectura"])
        st, p = self._req(srv, "GET", "/api/asistente/propuesta")
        self.assertEqual(st, 409)
        self.assertIn("no se puede leer", p["error"])

    def test_ficheros_danados_no_dan_500(self):
        srv = self._escaneado()
        rb = os.path.join(self.d, "asistente-borrador.json")
        rd = os.path.join(self.d, "asistente-descubrimiento.json")
        for basura in ([], {"basado_en": "x"}, {"equipos": {"10.0.0.2": {"nombre": "x"}}}):
            with open(rb, "w", encoding="utf-8") as f:
                json.dump(basura, f)
            st, est = self._req(srv, "GET", "/api/asistente")
            self.assertEqual(st, 200, basura)
            self.assertIn("10.0.0.2", est["borrador"]["equipos"])       # se rehace desde el descubrimiento
            self.assertEqual(self._req(srv, "GET", "/api/asistente/propuesta")[0], 200, basura)
            self.assertEqual(self._req(srv, "POST", "/api/asistente/borrador",
                                       {"cambios": {"10.0.0.2": {"nombre": "fw-interno"}}})[0], 200, basura)
        with open(rd, "w", encoding="utf-8") as f:
            json.dump({"equipos": [{"puertos": []}]}, f)
        st, est = self._req(srv, "GET", "/api/asistente")
        self.assertEqual(st, 200)
        self.assertIsNone(est["descubrimiento"])
        self.assertIn("dañado", est["aviso_lectura"])
        self.assertEqual(self._req(srv, "GET", "/api/asistente/propuesta")[0], 409)

    def test_reescanear_conserva_lo_escrito(self):
        srv = self._escaneado()
        self._req(srv, "POST", "/api/asistente/borrador", {"cambios": {"10.0.0.2": {"nombre": "fw-interno", "criticidad": "alta"}}})
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        est = self._esperar(srv)
        e = est["borrador"]["equipos"]["10.0.0.2"]
        self.assertEqual((e["nombre"], e["criticidad"]), ("fw-interno", "alta"))

    def test_lo_editado_durante_el_escaneo_tambien_se_conserva(self):
        suelta = threading.Event()
        base = _correr_falso()
        lento = {"si": False}

        def correr(args):
            if lento["si"]:
                suelta.wait(5)
            return base(args)
        srv = self._escaneado(correr=correr)
        lento["si"] = True
        self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        st, _ = self._req(srv, "POST", "/api/asistente/borrador", {"cambios": {"10.0.0.2": {"nombre": "fw-interno"}}})
        self.assertEqual(st, 200)
        suelta.set()
        est = self._esperar(srv)
        self.assertEqual(est["borrador"]["equipos"]["10.0.0.2"]["nombre"], "fw-interno")

    def test_si_no_se_puede_anotar_en_la_traza_no_se_escanea_ni_se_queda_colgado(self):
        llamadas = []
        srv = self._srv(correr=_correr_falso(llamadas))

        def falla(_reg):
            raise OSError("disco lleno")
        srv.estado.fijar_auditor(falla)
        st, r = self._req(srv, "POST", "/api/asistente/escanear", PETICION)
        self.assertEqual(st, 500)
        self.assertIn("traza", r["error"])
        self.assertEqual(llamadas, [])
        _, est = self._req(srv, "GET", "/api/asistente")
        self.assertFalse(est["escaneando"])


class TestRutasEnElResumen(_Base):
    def test_el_resumen_dice_donde_instalar(self):
        srv = self._srv()
        srv.rutas_instalacion = {"perfil": "run/banco-nuevo/perfil.yml", "postura": "run/banco-nuevo/postura.json",
                                 "politica": "run/banco-nuevo/politica.yml"}
        _, est = self._req(srv, "GET", "/api/asistente")
        self.assertEqual(est["instalacion"]["perfil"], "run/banco-nuevo/perfil.yml")
