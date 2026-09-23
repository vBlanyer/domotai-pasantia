import http.client
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from prototipo import tablero, traza


class TestEstadoYLector(unittest.TestCase):
    def test_registrar_pendiente_y_resolver_devuelve_la_respuesta(self):
        estado = tablero.EstadoTablero()
        lector = tablero.LectorWeb(estado)
        salida = {}
        hilo = threading.Thread(target=lambda: salida.setdefault("r", lector("Elige [1-3]: ")))
        hilo.start()
        pid = None
        for _ in range(200):                       # esperar a que el lector registre la pendiente
            p = estado.pendientes()
            if p:
                pid = p[0]["id"]; break
            time.sleep(0.005)
        self.assertIsNotNone(pid)
        self.assertTrue(estado.resolver(pid, "1"))
        hilo.join(timeout=2)
        self.assertEqual(salida["r"], "1")
        self.assertEqual(estado.pendientes(), [])  # se quita al resolverse

    def test_clasifica_escalada_y_menu_como_lector(self):
        estado = tablero.EstadoTablero()
        estado.registrar_pendiente(*("escalada", "¿aprobar? [s/N] "))
        # el tipo lo pone LectorWeb; aqui comprobamos la regla directamente
        self.assertEqual(tablero.LectorWeb(estado)._tipo("¿aprobar? [s/N] "), "escalada")
        self.assertEqual(tablero.LectorWeb(estado)._tipo("Elige [1-3]: "), "menu")

    def test_resolver_id_desconocido_es_falso(self):
        self.assertFalse(tablero.EstadoTablero().resolver("999", "1"))

    def test_timeout_devuelve_respuesta_segura_vacia(self):
        estado = tablero.EstadoTablero()
        r = tablero.LectorWeb(estado, timeout=0.05)("Elige [1-3]: ")
        self.assertEqual(r, "")

    def test_anotar_linea_reinicia_en_cada_incidente(self):
        estado = tablero.EstadoTablero()
        estado.anotar_linea("⚠ Incidente A"); estado.anotar_linea("  detalle")
        pid, _ = estado.registrar_pendiente("menu", "x")
        self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ Incidente A", "  detalle"])
        estado.anotar_linea("⚠ Incidente B")   # nueva marca -> reinicia
        pid2, _ = estado.registrar_pendiente("menu", "y")
        self.assertEqual([p["lineas"] for p in estado.pendientes() if p["id"] == pid2][0],
                         ["⚠ Incidente B"])

    def test_escribir_web_imprime_y_acumula(self):
        estado = tablero.EstadoTablero()
        vistas = []
        esc = tablero.escribir_web(estado, escribir=vistas.append)
        esc("⚠ Incidente"); esc("linea 2")
        self.assertEqual(vistas, ["⚠ Incidente", "linea 2"])
        pid, _ = estado.registrar_pendiente("menu", "x")
        self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ Incidente", "linea 2"])


class TestLectoresDeDatos(unittest.TestCase):
    def _traza_tmp(self, registros):
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_lista_trazas_conserva_actividad_suprimida(self):
        ruta = self._traza_tmp([{"id_decision": "s5~sup", "tipo": "actividad_suprimida",
                                 "referencia": "s5", "alertas_suprimidas": 3}])
        r = tablero.lista_trazas(ruta)[0]
        self.assertEqual(r["tipo"], "actividad_suprimida")
        self.assertEqual(r["alertas_suprimidas"], 3)

    def test_estado_salud_convierte_y_decora_dependencias(self):
        muestra = {"t": "2026-09-22T10:00:00Z", "estados": {"core-db": "ok", "middleware": "caido"}}
        r = tablero.estado_salud(muestra, {"middleware": ["core-db"]})
        self.assertEqual(r["caidos"], 1)
        self.assertEqual(r["total"], 2)
        mid = [s for s in r["servicios"] if s["nombre"] == "middleware"][0]
        self.assertEqual(mid["estado"], "caido")
        self.assertEqual(mid["depende_de"], ["core-db"])

    def test_estado_salud_sin_muestra(self):
        self.assertEqual(tablero.estado_salud(None), {"sin_datos": True})

    def test_leer_salud_de_fichero_toma_la_ultima_linea(self):
        ruta = self._traza_tmp([{"t": "1", "estados": {}}, {"t": "2", "estados": {"a": "ok"}}])
        self.assertEqual(tablero.leer_salud(ruta=ruta)["t"], "2")

    def test_leer_salud_por_docker_exec(self):
        linea = json.dumps({"t": "9", "estados": {"a": "ok"}})
        def ejec(args, **kw):
            self.assertEqual(args[:3], ["docker", "exec", "cont"])
            return subprocess.CompletedProcess(args, 0, linea + "\n", "")
        r = tablero.leer_salud(contenedor="cont", fichero_en_contenedor="/x", ejecutar=ejec)
        self.assertEqual(r["t"], "9")

    def test_leer_salud_fichero_ausente_es_none(self):
        self.assertIsNone(tablero.leer_salud(ruta="/no/existe.jsonl"))

    def test_lista_y_detalle_de_trazas(self):
        ruta = self._traza_tmp([
            {"id_decision": "s1", "timestamp": "t1", "activo": "web", "clase": "vp_intento_acceso",
             "confianza": 1.0, "accion_final": "BLOQUEAR_IP", "requiere_humano": False},
            {"id_decision": "s2", "timestamp": "t2", "activo": "core-db", "clase": "no_soportada"}])
        lst = tablero.lista_trazas(ruta)
        self.assertEqual([d["id_decision"] for d in lst], ["s1", "s2"])
        self.assertEqual(tablero.lista_trazas(ruta, n=1)[0]["id_decision"], "s2")
        self.assertEqual(tablero.traza_detalle(ruta, "s1")["accion_final"], "BLOQUEAR_IP")
        self.assertIsNone(tablero.traza_detalle(ruta, "zzz"))

    def test_lista_trazas_fichero_ausente_es_vacia(self):
        self.assertEqual(tablero.lista_trazas("/no/existe.jsonl"), [])

    def test_resumen_traza_expone_justificador_mitre_rag_y_motivo(self):
        ruta = self._traza_tmp([{
            "id_decision": "s1", "timestamp": "t1", "activo": "web", "clase": "vp_intento_acceso",
            "confianza": 1.0, "accion_final": "BLOQUEAR_IP", "requiere_humano": False,
            "impacto": "localizado", "version_justificador": "plantilla-0",
            "justificacion_estructurada": {"tecnica_mitre": ["T1110.001", "T1021.004"]},
            "pasajes_usados": [], "consulta_rag": "",
            "impacto_determinado": {"nivel": "localizado", "motivo": "bloquea a 1.2.3.4 · 0 servicios detenidos"}}])
        r = tablero.lista_trazas(ruta)[0]
        self.assertEqual(r["version_justificador"], "plantilla-0")
        self.assertEqual(r["tecnica_mitre"], ["T1110.001", "T1021.004"])
        self.assertFalse(r["con_rag"])                                  # pasajes_usados vacío
        self.assertEqual(r["impacto"], "localizado")                   # antes leía el campo equivocado (None)
        self.assertEqual(r["motivo"], "bloquea a 1.2.3.4 · 0 servicios detenidos")

    def test_resumen_traza_marca_con_rag_cuando_hay_pasajes(self):
        ruta = self._traza_tmp([{"id_decision": "s2", "pasajes_usados": ["mitre-T1110"],
                                 "impacto_determinado": {"nivel": "localizado"}}])
        self.assertTrue(tablero.lista_trazas(ruta)[0]["con_rag"])

    def test_hidratar_pasajes_resuelve_ids_contra_el_corpus(self):
        corpus = {"mitre-T1110": {"id": "mitre-T1110", "titulo": "T1110", "texto": "fuerza bruta"},
                  "mapeo-x": {"id": "mapeo-x", "titulo": "Mapeo", "texto": "acceso credenciales"}}
        reg = {"id_decision": "s1", "pasajes_usados": ["mitre-T1110", "ausente", "mapeo-x"]}
        r = tablero._hidratar_pasajes(reg, corpus)
        self.assertEqual([p["id"] for p in r["pasajes"]], ["mitre-T1110", "mapeo-x"])  # 'ausente' se omite
        self.assertEqual(r["pasajes"][0]["texto"], "fuerza bruta")
        self.assertEqual(r["pasajes_usados"], ["mitre-T1110", "ausente", "mapeo-x"])   # los IDs se conservan

    def test_hidratar_pasajes_sin_pasajes_es_lista_vacia(self):
        self.assertEqual(tablero._hidratar_pasajes({}, {})["pasajes"], [])

    def test_verificar_traza_cadena_integra_y_rota(self):
        r1 = traza.encadenar({"id_decision": "s1", "x": 1}, traza.GENESIS)
        r2 = traza.encadenar({"id_decision": "s2", "x": 2}, r1["hash"])
        buena = self._traza_tmp([r1, r2])
        self.assertTrue(tablero.verificar_traza(buena)["ok"])
        r2_malo = dict(r2, x=999)                      # contenido alterado, hash ya no cuadra
        rota = self._traza_tmp([r1, r2_malo])
        v = tablero.verificar_traza(rota)
        self.assertFalse(v["ok"])
        self.assertEqual(v["roto_en"], 1)


class TestServidor(unittest.TestCase):
    def _servidor(self, estado=None, ruta_traza="/no/existe.jsonl", salud=None,
                  dependencias=None, salud_ejecutar=subprocess.run, estaticos=None):
        estaticos = estaticos or tempfile.mkdtemp()
        with open(os.path.join(estaticos, "index.html"), "w", encoding="utf-8") as f:
            f.write("<html>tablero</html>")
        srv = tablero.crear_servidor(estado or tablero.EstadoTablero(), ruta_traza, salud=salud,
                                     dependencias=dependencias, estaticos=estaticos, puerto=0,
                                     salud_ejecutar=salud_ejecutar)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv, srv.server_address[1]

    def _get(self, puerto, ruta):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta); r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, cuerpo

    def _post(self, puerto, ruta, obj):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("POST", ruta, json.dumps(obj), {"Content-Type": "application/json"})
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def test_liga_solo_a_localhost(self):
        srv, _ = self._servidor()
        self.assertEqual(srv.server_address[0], "127.0.0.1")

    def test_raiz_sirve_index(self):
        _, puerto = self._servidor()
        estado, cuerpo = self._get(puerto, "/")
        self.assertEqual(estado, 200)
        self.assertIn(b"tablero", cuerpo)

    def test_pendientes_vacio_y_aprobar_resuelve(self):
        estado = tablero.EstadoTablero()
        _, puerto = self._servidor(estado=estado)
        self.assertEqual(json.loads(self._get(puerto, "/api/pendientes")[1]), [])
        salida = {}
        hilo = threading.Thread(target=lambda: salida.setdefault("r", tablero.LectorWeb(estado)("¿aprobar? [s/N] ")))
        hilo.start()
        pid = None
        for _ in range(200):
            p = json.loads(self._get(puerto, "/api/pendientes")[1])
            if p:
                pid = p[0]["id"]; self.assertEqual(p[0]["tipo"], "escalada"); break
            time.sleep(0.005)
        self.assertIsNotNone(pid)
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": pid, "respuesta": "s"}), (200, {"ok": True}))
        hilo.join(timeout=2)
        self.assertEqual(salida["r"], "s")
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": pid, "respuesta": "s"})[0], 409)

    def test_salud_desde_ejecutor_falso(self):
        def ejec(args, **kw):
            return subprocess.CompletedProcess(args, 0, json.dumps({"t": "1", "estados": {"a": "ok"}}) + "\n", "")
        _, puerto = self._servidor(salud={"contenedor": "c", "fichero_en_contenedor": "/x"}, salud_ejecutar=ejec)
        cuerpo = json.loads(self._get(puerto, "/api/salud")[1])
        self.assertEqual(cuerpo["total"], 1)

    def test_trazas_y_verificar(self):
        r1 = traza.encadenar({"id_decision": "s1"}, traza.GENESIS)
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        f.write(json.dumps(r1) + "\n"); f.close(); self.addCleanup(os.unlink, f.name)
        _, puerto = self._servidor(ruta_traza=f.name)
        self.assertEqual(json.loads(self._get(puerto, "/api/trazas")[1])[0]["id_decision"], "s1")
        self.assertEqual(self._get(puerto, "/api/traza/s1")[0], 200)
        self.assertEqual(self._get(puerto, "/api/traza/zzz")[0], 404)
        self.assertTrue(json.loads(self._get(puerto, "/api/verificar")[1])["ok"])


class TestEstaticosReales(unittest.TestCase):
    def test_sirve_estaticos_de_un_directorio(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write("<html>Tablero MDR</html>")
        srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0, estaticos=d)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=3)
        c.request("GET", "/"); r = c.getresponse(); html = r.read(); c.close()
        self.assertEqual(r.status, 200)
        self.assertIn(b"Tablero", html)


class TestServirBuild(unittest.TestCase):
    def _srv(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "assets"))
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write("<html>Tablero MDR</html>")
        with open(os.path.join(d, "assets", "app.js"), "w", encoding="utf-8") as f:
            f.write("console.log(1)")
        srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0, estaticos=d)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv.server_address[1]

    def _get(self, puerto, ruta):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta); r = c.getresponse(); r.read(); c.close()
        return r.status, r.getheader("Content-Type")

    def test_sirve_index_y_un_asset_en_subdir(self):
        puerto = self._srv()
        self.assertEqual(self._get(puerto, "/")[0], 200)
        est, ct = self._get(puerto, "/assets/app.js")
        self.assertEqual(est, 200)
        self.assertIn("javascript", ct or "")

    def test_rechaza_travesia_de_rutas(self):
        puerto = self._srv()
        self.assertEqual(self._get(puerto, "/../../../etc/passwd")[0], 404)


class TestCORS(unittest.TestCase):
    def _srv(self, estaticos=None):
        srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0,
                                     estaticos=estaticos or tempfile.mkdtemp())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv.server_address[1]

    def test_get_lleva_cabecera_cors(self):
        puerto = self._srv()
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", "/api/pendientes"); r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")

    def test_options_preflight_devuelve_204_con_cors(self):
        puerto = self._srv()
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("OPTIONS", "/api/aprobar"); r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 204)
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", r.getheader("Access-Control-Allow-Methods") or "")

    def test_dist_ausente_da_404_claro(self):
        puerto = self._srv(estaticos="/directorio/que/no/existe")
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", "/"); r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 404)


if __name__ == "__main__":
    unittest.main()
