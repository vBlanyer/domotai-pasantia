import http.client
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
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

    def test_cola_encola_ordena_por_severidad_y_deduplica(self):
        e = tablero.EstadoTablero()
        a = e.encolar_decision({"clave": ("1.1.1.1", "acceso_credenciales"), "severidad": 4, "activo": "core-db"})
        b = e.encolar_decision({"clave": ("2.2.2.2", "acceso_credenciales"), "severidad": 7, "activo": "hsm"})
        a2 = e.encolar_decision({"clave": ("1.1.1.1", "acceso_credenciales"), "severidad": 4, "activo": "core-db"})
        self.assertEqual(a2, a)                                   # misma clave -> no duplica
        cola = e.decisiones_pendientes()
        self.assertEqual([p["id"] for p in cola], [b, a])        # severidad 7 antes que 4
        self.assertEqual(next(p["suprimidas"] for p in cola if p["id"] == a), 1)

    def test_sacar_decision_la_quita_de_la_cola(self):
        e = tablero.EstadoTablero()
        a = e.encolar_decision({"clave": None, "severidad": 1, "activo": "x"})
        self.assertEqual(e.sacar_decision(a)["activo"], "x")
        self.assertEqual(e.decisiones_pendientes(), [])
        self.assertIsNone(e.sacar_decision(a))                   # ya no está

    def test_encolar_siembra_el_paso_en_cero(self):
        # El paso identifica qué menú vio el analista: una respuesta a un menú ya superado se rechaza.
        e = tablero.EstadoTablero()
        e.encolar_decision({"clave": None, "severidad": 1, "activo": "x"})
        self.assertEqual(e.decisiones_pendientes()[0]["paso"], 0)

    def test_resolver_decision_pasa_el_paso_al_resolutor(self):
        e = tablero.EstadoTablero()
        vistos = []
        e.fijar_resolutor(lambda pid, resp, paso=None: vistos.append((pid, resp, paso)) or True)
        self.assertTrue(e.resolver_decision("1", "2", paso=3))
        self.assertTrue(e.resolver_decision("1", "2"))            # sin paso -> None (rutas viejas)
        self.assertEqual(vistos, [("1", "2", 3), ("1", "2", None)])

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

    def test_estado_equipos_inventario_desde_perfil_con_categoria_y_estado(self):
        activos = {
            "web-banking": {"ip": "10.10.0.10", "funcion": "banca en linea", "criticidad": "alta",
                            "servicios_prestados": [443], "depende_de": ["middleware"]},
            "mdr-siem": {"ip": "10.100.0.10", "funcion": "consola SOC/MDR (plano de gestion)",
                         "criticidad": "critica", "servicios_prestados": []},
            "taquilla": {"ip": "10.200.0.10", "funcion": "puesto de taquilla", "criticidad": "media",
                         "servicios_prestados": []},
        }
        topologia = {"fw-core": {"rol": "firewall_perimetral", "ip": "10.0.0.1", "gateway": "fw-edge"}}
        salud = {"servicios": [{"nombre": "web-banking", "estado": "ok", "depende_de": []}]}
        eq = tablero.estado_equipos(activos, topologia, salud)
        por = {e["nombre"]: e for e in eq}
        self.assertEqual(len(eq), 4)                              # 3 activos + 1 cortafuegos del topologia
        self.assertEqual(por["web-banking"]["categoria"], "servidor")
        self.assertEqual(por["web-banking"]["estado"], "ok")      # cruzado con salud
        self.assertEqual(por["web-banking"]["criticidad"], "alta")
        self.assertEqual(por["mdr-siem"]["categoria"], "gestion")
        self.assertEqual(por["taquilla"]["categoria"], "endpoint")   # sin servicios prestados
        self.assertEqual(por["fw-core"]["categoria"], "cortafuegos")  # sale del topologia
        self.assertEqual(por["fw-core"]["ip"], "10.0.0.1")
        self.assertIsNone(por["fw-core"]["estado"])                  # no monitoreado por salud

    def test_estado_equipos_tolera_salud_sin_datos_o_none(self):
        activos = {"a": {"ip": "1.1.1.1", "funcion": "x", "criticidad": "alta", "servicios_prestados": [80]}}
        for salud in ({"sin_datos": True}, None):
            eq = tablero.estado_equipos(activos, {}, salud)
            self.assertIsNone(eq[0]["estado"])
            self.assertEqual(eq[0]["categoria"], "servidor")

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

    def test_metricas_calcula_los_indicadores_del_periodo(self):
        regs = [
            {"tipo": "actividad_suprimida", "alertas_suprimidas": 5},
            {"clase": "vp_intento_acceso", "requiere_humano": False, "activo": "web-banking",
             "timestamp": "2026-09-24T10:00:00Z",
             "justificacion_estructurada": {"tecnica_mitre": ["T1110.001", "T1021.004"]}},
            {"clase": "vp_intento_acceso", "requiere_humano": True, "veredicto_humano": "aprobar",
             "activo": "core-db", "timestamp": "2026-09-24T11:00:00Z", "recibido_en": 100.0, "resuelto_en": 112.0,
             "justificacion_estructurada": {"tecnica_mitre": ["T1110.001"]}},
            {"clase": "fp_actividad_legitima", "requiere_humano": True, "veredicto_humano": "rechazar",
             "activo": "web-banking", "timestamp": "2026-09-23T09:00:00Z"},
        ]
        m = tablero.metricas(regs)
        self.assertEqual(m["total"], 3)                 # sin la suprimida
        self.assertEqual(m["fp"], 1)
        self.assertEqual(m["tasa_fp"], round(1 / 3, 3))
        self.assertEqual(m["auto"], 1)                  # 1 de 3 sin humano
        self.assertEqual(m["suprimidas"], 5)
        self.assertEqual(m["veredictos"], {"aprobar": 1, "rechazar": 1})
        self.assertEqual(m["mttr_seg"], 12.0)           # (112-100) de la única con marcas
        self.assertEqual(m["por_clase"]["vp_intento_acceso"], 2)
        self.assertEqual({a["nombre"]: a["n"] for a in m["top_activos"]}["web-banking"], 2)
        self.assertEqual({t["tecnica"]: t["n"] for t in m["mitre"]}["T1110.001"], 2)
        self.assertEqual([d["n"] for d in m["por_dia"]], [1, 2])   # 23 (1) antes que 24 (2)

    def test_metricas_no_cuentan_los_errores_ni_las_reversiones_como_decisiones(self):
        m = tablero.metricas([{"id_decision": "s1", "clase": "vp_intento_acceso", "requiere_humano": False},
                              {"id_decision": "s2", "tipo": "error", "error": "boom"},
                              {"tipo": "reversion", "id_decision_revertida": "s1", "exito": True}])
        self.assertEqual((m["total"], m["por_clase"]), (1, {"vp_intento_acceso": 1}))

    def test_leer_salud_con_docker_colgado_es_none_y_con_plazo(self):
        visto = {}
        def colgado(args, **kw):
            visto.update(kw); raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        self.assertIsNone(tablero.leer_salud(contenedor="c", fichero_en_contenedor="/x", ejecutar=colgado))
        self.assertTrue(visto.get("timeout"))

    def test_metricas_no_cuentan_la_actividad_propia_del_mdr_como_decision(self):
        m = tablero.metricas([{"id_decision": "s1", "clase": "vp_intento_acceso", "requiere_humano": False},
                              {"id_decision": "p1", "tipo": "actividad_propia", "activo": "web-banking"}])
        self.assertEqual(m["total"], 1)
        self.assertEqual(m["por_clase"], {"vp_intento_acceso": 1})

    def test_metricas_sin_decisiones_no_divide_por_cero(self):
        m = tablero.metricas([])
        self.assertEqual((m["total"], m["tasa_fp"], m["pct_auto"], m["mttr_seg"]), (0, 0.0, 0.0, None))

    def test_resumen_traza_expone_justificador_mitre_rag_y_motivo(self):
        ruta = self._traza_tmp([{
            "id_decision": "s1", "timestamp": "t1", "activo": "web", "clase": "vp_intento_acceso",
            "confianza": 1.0, "accion_final": "BLOQUEAR_IP", "requiere_humano": False,
            "impacto": "localizado", "version_justificador": "plantilla-0",
            "justificacion_estructurada": {"tecnica_mitre": ["T1110.001", "T1021.004"],
                                           "evidencia": {"origen_ip": "198.51.100.10"}},
            "pasajes_usados": [], "consulta_rag": "",
            "impacto_determinado": {"nivel": "localizado", "motivo": "bloquea a 1.2.3.4 · 0 servicios detenidos"}}])
        r = tablero.lista_trazas(ruta)[0]
        self.assertEqual(r["version_justificador"], "plantilla-0")
        self.assertEqual(r["origen_ip"], "198.51.100.10")
        self.assertEqual(r["tecnica_mitre"], ["T1110.001", "T1021.004"])
        self.assertFalse(r["con_rag"])                                  # pasajes_usados vacío
        self.assertEqual(r["impacto"], "localizado")                   # antes leía el campo equivocado (None)
        self.assertEqual(r["motivo"], "bloquea a 1.2.3.4 · 0 servicios detenidos")

    def test_resumen_traza_expone_la_cascada_para_avisar_en_la_fila(self):
        ruta = self._traza_tmp([{"id_decision": "s1", "impacto_determinado": {
            "nivel": "localizado", "activos_afectados_en_cascada": ["api-movil", "middleware", "web-banking"]}}])
        self.assertEqual(tablero.lista_trazas(ruta)[0]["cascada"], ["api-movil", "middleware", "web-banking"])

    def test_resumen_traza_cascada_vacia_por_defecto(self):
        ruta = self._traza_tmp([{"id_decision": "s2", "impacto_determinado": {"nivel": "localizado"}}])
        self.assertEqual(tablero.lista_trazas(ruta)[0]["cascada"], [])

    def test_resumen_traza_expone_la_reversion_y_el_error(self):
        rev = tablero._resumen_traza({"tipo": "reversion", "id_decision_revertida": "s3", "indice_revertido": 4,
                                      "exito": True, "accion_id": "BLOQUEAR_IP", "nodo": "web-banking"})
        self.assertEqual((rev["id_decision_revertida"], rev["indice_revertido"], rev["exito"], rev["nodo"]),
                         ("s3", 4, True, "web-banking"))
        err = tablero._resumen_traza({"tipo": "error", "id_decision": "s5", "error": "OSError: docker"})
        self.assertEqual(err["error"], "OSError: docker")

    def test_resumen_traza_expone_la_cadena_de_hashes(self):
        ruta = self._traza_tmp([{"id_decision": "s1", "hash": "abc123", "hash_previo": "0" * 64,
                                 "impacto_determinado": {}}])
        r = tablero.lista_trazas(ruta)[0]
        self.assertEqual(r["hash"], "abc123")
        self.assertEqual(r["hash_previo"], "0" * 64)

    def test_traza_detalle_por_indice_distingue_ids_repetidos(self):
        # Relanzar el daemon sobre la misma traza repite los id_decision: la fila sabe su índice y el
        # detalle debe ser el de ESE registro, no el del último con el mismo id.
        ruta = self._traza_tmp([{"id_decision": "s1", "justificacion": "antigua"},
                                {"id_decision": "s1", "justificacion": "nueva"}])
        self.assertEqual(tablero.traza_detalle(ruta, "s1", indice=0)["justificacion"], "antigua")
        self.assertEqual(tablero.traza_detalle(ruta, "s1")["justificacion"], "nueva")         # sin índice: la última
        self.assertEqual(tablero.traza_detalle(ruta, "s1", indice=9)["justificacion"], "nueva")   # fuera de rango
        self.assertEqual(tablero.traza_detalle(ruta, "s2", indice=0), None)                   # índice de otro id

    def test_lista_trazas_anota_el_indice_global_en_la_cadena(self):
        # Con la cota, la ventana empieza a mitad de la traza: el índice global identifica cada
        # registro (los id_decision se repiten) y casa con el roto_en de /api/verificar.
        ruta = self._traza_tmp([{"id_decision": "s1"}, {"id_decision": "s1"}, {"id_decision": "s2"}])
        self.assertEqual([r["indice"] for r in tablero.lista_trazas(ruta)], [0, 1, 2])
        self.assertEqual([r["indice"] for r in tablero.lista_trazas(ruta, n=2)], [1, 2])
        self.assertEqual([r["indice"] for r in tablero.lista_trazas(ruta, n=9)], [0, 1, 2])

    def test_resumen_traza_expone_prioridad_veredicto_y_filtro(self):
        # Lo que el analista necesita en la fila: gravedad, qué decidió el humano (y a qué clase
        # corrigió) y si la acción propuesta se vetó o degradó antes de ser la final.
        ruta = self._traza_tmp([{
            "id_decision": "s1", "prioridad": 7, "veredicto_humano": "reclasificar",
            "clase_reclasificada": "fp_actividad_legitima", "resultado_filtro": "degrada",
            "accion_propuesta": "AISLAR_NODO", "accion_final": "BLOQUEAR_IP", "impacto_determinado": {}}])
        r = tablero.lista_trazas(ruta)[0]
        self.assertEqual(r["prioridad"], 7)
        self.assertEqual(r["veredicto_humano"], "reclasificar")
        self.assertEqual(r["clase_reclasificada"], "fp_actividad_legitima")
        self.assertEqual(r["resultado_filtro"], "degrada")
        self.assertEqual(r["accion_propuesta"], "AISLAR_NODO")

    def test_resumen_traza_sin_los_campos_nuevos_los_deja_en_none(self):
        # Registros antiguos o de supresión no los traen: el resumen no debe romper.
        r = tablero.lista_trazas(self._traza_tmp([{"id_decision": "s1~sup", "tipo": "actividad_suprimida"}]))[0]
        for campo in ("prioridad", "veredicto_humano", "clase_reclasificada", "resultado_filtro",
                      "accion_propuesta"):
            self.assertIn(campo, r)
            self.assertIsNone(r[campo])

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

    def test_aprobar_async_propaga_el_paso_del_cuerpo(self):
        estado = tablero.EstadoTablero()
        vistos = []
        estado.fijar_resolutor(lambda pid, resp, paso=None: vistos.append((pid, resp, paso)) or True)
        srv = tablero.crear_servidor(estado, "/no/existe.jsonl", puerto=0, estaticos=tempfile.mkdtemp(),
                                     async_web=True)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        puerto = srv.server_address[1]
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": "1", "respuesta": "1", "paso": 2})[0], 200)
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": "1", "respuesta": "1"})[0], 200)
        self.assertEqual(vistos, [("1", "1", 2), ("1", "1", None)])

    def _traza_n(self, n):
        regs, previo = [], traza.GENESIS
        for i in range(1, n + 1):
            r = traza.encadenar({"id_decision": f"s{i}"}, previo)
            regs.append(r); previo = r["hash"]
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        f.write("".join(json.dumps(r) + "\n" for r in regs)); f.close(); self.addCleanup(os.unlink, f.name)
        return f.name

    def test_detalle_http_acepta_el_indice(self):
        regs = [traza.encadenar({"id_decision": "s1", "justificacion": "antigua"}, traza.GENESIS)]
        regs.append(traza.encadenar({"id_decision": "s1", "justificacion": "nueva"}, regs[0]["hash"]))
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        f.write("".join(json.dumps(r) + "\n" for r in regs)); f.close(); self.addCleanup(os.unlink, f.name)
        _, puerto = self._servidor(ruta_traza=f.name)
        self.assertEqual(json.loads(self._get(puerto, "/api/traza/s1?indice=0")[1])["justificacion"], "antigua")
        self.assertEqual(json.loads(self._get(puerto, "/api/traza/s1")[1])["justificacion"], "nueva")

    def test_trazas_se_acotan_a_los_ultimos_por_defecto(self):
        # El visor sondea /api/trazas cada 2 s: sin cota, cada tick relee y envía la traza entera.
        _, puerto = self._servidor(ruta_traza=self._traza_n(3))
        with mock.patch.object(tablero, "LIMITE_TRAZAS", 2):
            ids = [r["id_decision"] for r in json.loads(self._get(puerto, "/api/trazas")[1])]
        self.assertEqual(ids, ["s2", "s3"])

    def test_trazas_aceptan_limite_en_la_consulta(self):
        _, puerto = self._servidor(ruta_traza=self._traza_n(3))
        ids = lambda q: [r["id_decision"] for r in json.loads(self._get(puerto, "/api/trazas" + q)[1])]
        self.assertEqual(ids("?limite=1"), ["s3"])
        self.assertEqual(ids("?limite=abc"), ["s1", "s2", "s3"])   # inválido -> la cota por defecto
        self.assertEqual(ids("?limite=0"), ["s1", "s2", "s3"])

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

    def test_api_red(self):
        srv, puerto = self._servidor()
        srv.perfil = TestVistaRed.PERFIL
        estado, cuerpo = self._get(puerto, "/api/red")
        self.assertEqual(estado, 200)
        r = json.loads(cuerpo)
        self.assertEqual({n["nombre"] for n in r["nodos"]}, {"web-banking", "middleware", "taquilla", "fw-core"})


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




class TestVistaRed(unittest.TestCase):
    PERFIL = {"activos": {"web-banking": {"ip": "10.10.0.10", "depende_de": ["middleware"]},
                          "middleware": {"ip": "10.40.0.10"},
                          "taquilla": {"ip": "10.200.0.10"}},
              "topologia": {"web-banking": {"rol": "host_victima", "ip": "10.10.0.10", "gateway": "fw-core"},
                            "fw-core": {"rol": "firewall_perimetral", "ip": "10.0.0.1"}}}

    def _dec(self, **kw):
        return {"tipo": "decision", "id_decision": "s1", "activo": "web-banking", "clase": "vp_intento_acceso",
                "timestamp": "2026-09-30T10:00:00Z", "contexto": {"origen_ip": "198.51.100.10"}, **kw}

    def test_contencion_de(self):
        self.assertEqual(tablero.contencion_de(self._dec(
            orden={"nodo_objetivo": "web-banking"}, ejecucion={"exito": True}, verificacion={"verificado": True})),
            ("contenida", "web-banking"))
        self.assertEqual(tablero.contencion_de(self._dec(
            orden={"nodo_objetivo": "web-banking"}, ejecucion={"exito": False}, verificacion={"verificado": False},
            escalada={"resultado": "mitigado", "dispositivo_ejecutor": "fw-core"})), ("contenida", "fw-core"))
        self.assertEqual(tablero.contencion_de(self._dec(orden=None, ruta="cola-appsec")), ("enrutada", "cola-appsec"))
        self.assertEqual(tablero.contencion_de(self._dec(orden=None, veredicto_humano="rechazar")), ("retenida", None))
        self.assertEqual(tablero.contencion_de(self._dec(orden=None)), ("sin_accion", None))

    def test_relaciones_objetivo_origen_y_contuvo_aqui(self):
        ips = tablero.ips_de(self.PERFIL)
        reg = self._dec(contexto={"origen_ip": "::ffff:10.200.0.10"}, orden={"nodo_objetivo": "web-banking"},
                        ejecucion={"exito": False}, verificacion={"verificado": False},
                        escalada={"resultado": "mitigado", "dispositivo_ejecutor": "fw-core"})
        self.assertEqual(tablero.relaciones(reg, ips),
                         {"web-banking": ["objetivo"], "taquilla": ["origen"], "fw-core": ["contuvo_aqui"]})
        propio = self._dec(orden={"nodo_objetivo": "web-banking"}, ejecucion={"exito": True},
                           verificacion={"verificado": True})
        self.assertEqual(tablero.relaciones(propio, ips)["web-banking"], ["objetivo", "contuvo_aqui"])

    def test_relaciones_ignora_lo_que_no_es_decision_y_registros_antiguos(self):
        ips = tablero.ips_de(self.PERFIL)
        for tipo in ("actividad_suprimida", "actividad_propia", "error", "reversion"):
            self.assertEqual(tablero.relaciones({"tipo": tipo, "activo": "web-banking"}, ips), {})
        antiguo = {"id_decision": "s1", "activo": "web-banking",
                   "justificacion_estructurada": {"evidencia": {"origen_ip": "10.200.0.10"}}}
        self.assertEqual(tablero.relaciones(antiguo, ips), {"web-banking": ["objetivo"], "taquilla": ["origen"]})
        self.assertEqual(tablero.relaciones({"activo": "web-banking", "contexto": {"origen_ip": None}}, ips),
                         {"web-banking": ["objetivo"]})

    def test_estado_red_precedencia(self):
        pend = [{"alerta": {"activo": "web-banking", "origen_ip": "10.200.0.10"}}]
        regs = [self._dec(orden=None)]                                   # atacado sin contener
        e = {n["nombre"]: n["actividad"]["estado"] for n in tablero.estado_red(self.PERFIL, regs, [], None)["nodos"]}
        self.assertEqual(e["web-banking"], "atacado")
        e = {n["nombre"]: n for n in tablero.estado_red(self.PERFIL, regs, pend, None)["nodos"]}
        self.assertEqual(e["web-banking"]["actividad"]["estado"], "pendiente")
        self.assertEqual(e["taquilla"]["actividad"]["pendientes"], 1)          # también como origen
        salud = {"servicios": [{"nombre": "web-banking", "estado": "caido"}]}
        e = {n["nombre"]: n["actividad"]["estado"] for n in tablero.estado_red(self.PERFIL, regs, pend, salud)["nodos"]}
        self.assertEqual(e["web-banking"], "caido")
        contenida = [self._dec(orden={"nodo_objetivo": "web-banking"}, ejecucion={"exito": True},
                               verificacion={"verificado": True})]
        e = {n["nombre"]: n["actividad"]["estado"] for n in tablero.estado_red(self.PERFIL, contenida, [], None)["nodos"]}
        self.assertEqual((e["web-banking"], e["middleware"]), ("contenido", "sin_actividad"))
        rechazada = [self._dec(orden=None, veredicto_humano="rechazar")]
        e = {n["nombre"]: n["actividad"]["estado"] for n in tablero.estado_red(self.PERFIL, rechazada, [], None)["nodos"]}
        self.assertEqual(e["web-banking"], "sin_actividad")

    def test_estado_red_equipo_solo_de_origen_no_es_contenido(self):
        reg = self._dec(contexto={"origen_ip": "10.200.0.10"}, orden={"nodo_objetivo": "web-banking"},
                        ejecucion={"exito": True}, verificacion={"verificado": True})
        e = {n["nombre"]: n["actividad"] for n in tablero.estado_red(self.PERFIL, [reg], [], None)["nodos"]}
        self.assertEqual(e["web-banking"]["estado"], "contenido")
        self.assertEqual((e["taquilla"]["estado"], e["taquilla"]["origen"]), ("sin_actividad", 1))

    def test_estado_red_forma_y_pendientes_sin_alerta(self):
        r = tablero.estado_red(self.PERFIL, [{"tipo": "error"}], [{"id": "1", "tipo": "escalada"}], None)
        self.assertEqual(r["enlaces"], [["web-banking", "fw-core"]])
        self.assertEqual(r["dependencias"], [["web-banking", "middleware"]])
        self.assertEqual(r["zonas"], [{"nombre": "Red", "nodos": ["middleware", "taquilla", "web-banking"]}])
        nodo = [n for n in r["nodos"] if n["nombre"] == "web-banking"][0]
        self.assertEqual(nodo["actividad"]["objetivo"], 0)

    def test_resumen_traza_expone_relaciones_y_contencion(self):
        reg = self._dec(orden={"nodo_objetivo": "web-banking"}, ejecucion={"exito": True}, verificacion={"verificado": True})
        r = tablero._resumen_traza(reg, tablero.ips_de(self.PERFIL))
        self.assertEqual(r["relaciones"], {"web-banking": ["objetivo", "contuvo_aqui"]})
        self.assertEqual((r["contencion"], r["dispositivo"]), ("contenida", "web-banking"))

    def test_la_vista_de_pendientes_expone_activo_y_origen(self):
        v = tablero._vista_pendiente({"id": "1", "alerta": {"activo": "web-banking", "origen_ip": "10.200.0.10"},
                                      "decision": {}, "clave": ("x",)})
        self.assertEqual((v["activo"], v["origen_ip"]), ("web-banking", "10.200.0.10"))
        self.assertNotIn("alerta", v)


if __name__ == "__main__":
    unittest.main()
