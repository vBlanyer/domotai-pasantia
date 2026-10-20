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

    def test_registrar_pendiente_con_lineas_propias_no_usa_el_buffer_compartido(self):
        # Con agentes concurrentes, cada tarjeta trae su propio contexto, no el buffer global.
        estado = tablero.EstadoTablero()
        estado.anotar_linea("⚠ Incidente compartido")
        buf = ["⚠ Incidente del agente A", "  paso 1"]
        pid, _ = estado.registrar_pendiente("menu", "x", lineas=buf)
        p = [q for q in estado.pendientes() if q["id"] == pid][0]
        self.assertEqual(p["lineas"], ["⚠ Incidente del agente A", "  paso 1"])
        buf.append("  paso 2")                                  # la tarjeta guarda una copia
        self.assertEqual([q for q in estado.pendientes() if q["id"] == pid][0]["lineas"],
                         ["⚠ Incidente del agente A", "  paso 1"])

    def test_lector_web_con_buffer_propio_registra_esas_lineas(self):
        estado = tablero.EstadoTablero()
        buf = ["⚠ A", "paso"]
        lector = tablero.LectorWeb(estado, lineas=buf)
        hilo = threading.Thread(target=lambda: lector("Elige [1-3]: "))
        hilo.start()
        pid = None
        for _ in range(200):
            p = estado.pendientes()
            if p:
                pid = p[0]["id"]; break
            time.sleep(0.005)
        self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ A", "paso"])
        estado.resolver(pid, "1"); hilo.join(timeout=2)

    def test_resolver_decision_pasa_el_operador_al_resolutor(self):
        estado = tablero.EstadoTablero()
        cap = {}
        estado.fijar_resolutor(lambda pid, respuesta, paso=None, operador=None:
                               (cap.update(operador=operador, resp=respuesta), True)[1])
        self.assertTrue(estado.resolver_decision("1", "s", paso=0, operador="ana"))
        self.assertEqual(cap["operador"], "ana")

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

    def test_encolar_sella_la_hora_y_se_serializa_al_visor(self):
        # SLA del analista: `encolado_en` (hora de pared ISO) se sella al encolar y llega a la web
        # (no está en _INTERNO_PENDIENTE). Es la base del «lleva esperando X»; vive en la cola en
        # memoria, no en la traza. Se valida que es ISO parseable, no un valor exacto.
        from datetime import datetime
        e = tablero.EstadoTablero()
        e.encolar_decision({"clave": None, "severidad": 1, "activo": "x", "alerta": {"activo": "x", "origen_ip": "1.2.3.4"}})
        p = e.decisiones_pendientes()[0]
        datetime.fromisoformat(p["encolado_en"])                 # no lanza -> ISO válido
        vista = tablero._vista_pendiente(p)
        self.assertIn("encolado_en", vista)                      # se serializa al visor
        self.assertNotIn("alerta", vista)                        # el contexto interno no

    def test_resolver_decision_pasa_el_paso_al_resolutor(self):
        e = tablero.EstadoTablero()
        vistos = []
        e.fijar_resolutor(lambda pid, resp, paso=None, operador=None: vistos.append((pid, resp, paso, operador)) or True)
        self.assertTrue(e.resolver_decision("1", "2", paso=3, operador="ana"))
        self.assertTrue(e.resolver_decision("1", "2"))            # sin paso ni operador -> None (rutas viejas)
        self.assertEqual(vistos, [("1", "2", 3, "ana"), ("1", "2", None, None)])

    def test_actualizar_caso_pasa_al_actualizador_y_propaga_el_operador(self):
        # Ciclo de caso: el estado/nota/asignado se delegan al actualizador del daemon (añade a la
        # cadena); el operador (del token) viaja para el no repudio.
        e = tablero.EstadoTablero()
        vistos = []
        e.fijar_actualizador(lambda idd, **kw: vistos.append((idd, kw)) or True)
        self.assertTrue(e.actualizar_caso("d1", estado="resuelto", nota="ok", operador="ana"))
        self.assertEqual(vistos[0][0], "d1")
        self.assertEqual(vistos[0][1], {"estado": "resuelto", "asignado": None, "nota": "ok", "operador": "ana"})

    def test_actualizar_caso_sin_actualizador_es_falso(self):
        # Ruta bloqueante (sin daemon web): no hay dónde anotar -> False, sin reventar.
        self.assertFalse(tablero.EstadoTablero().actualizar_caso("d1", estado="resuelto"))

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

    def test_lista_trazas_arrastra_los_campos_de_caso_y_se_pliegan(self):
        # Integración (hueco de la revisión Opus): el registro `actualizacion_caso` debe llegar al
        # visor por /api/trazas con sus campos (si _resumen_traza los descarta, el panel de caso
        # muestra siempre 'nuevo' vacío). Se comprueba que lista_trazas los conserva Y que
        # casos.estado_de_casos los pliega al estado correcto.
        from prototipo import casos
        ruta = self._traza_tmp([
            {"id_decision": "s1", "timestamp": "t1", "activo": "web", "clase": "vp_intento_acceso"},
            casos.construir_actualizacion("s1", estado="en_revision", asignado="ana", ts="t2"),
            casos.construir_actualizacion("s1", nota="parece C2 real", operador="ana", ts="t3"),
            casos.construir_actualizacion("s1", estado="resuelto", ts="t4")])
        lst = tablero.lista_trazas(ruta)
        caso = casos.estado_de_casos(lst)["s1"]            # el mismo pliegue que hace el visor
        self.assertEqual(caso["estado"], "resuelto")
        self.assertEqual(caso["asignado"], "ana")
        self.assertEqual([n["texto"] for n in caso["notas"]], ["parece C2 real"])

    def test_traza_detalle_fallback_ignora_las_actualizaciones_de_caso(self):
        # MEDIO de la revisión: sin índice, el fallback debe devolver la DECISIÓN (con su contenido),
        # no un `actualizacion_caso` que comparte el id_decision y no trae justificacion/ejecucion.
        from prototipo import casos
        ruta = self._traza_tmp([
            {"id_decision": "s1", "timestamp": "t1", "activo": "web", "accion_final": "BLOQUEAR_IP"},
            casos.construir_actualizacion("s1", estado="resuelto", ts="t2")])
        d = tablero.traza_detalle(ruta, "s1")              # sin indice -> fallback
        self.assertEqual(d["accion_final"], "BLOQUEAR_IP")  # la decisión, no la actualización de caso
        self.assertNotEqual(d.get("tipo"), "actualizacion_caso")

    def test_lista_trazas_fichero_ausente_es_vacia(self):
        self.assertEqual(tablero.lista_trazas("/no/existe.jsonl"), [])

    def test_metricas_calcula_los_indicadores_del_periodo(self):
        regs = [
            {"tipo": "actividad_suprimida", "alertas_suprimidas": 5},
            {"clase": "vp_intento_acceso", "requiere_humano": False, "activo": "web-banking",
             "timestamp": "2026-09-24T10:00:00Z", "contexto": {"familia": "acceso_credenciales"}},
            {"clase": "vp_intento_acceso", "requiere_humano": True, "veredicto_humano": "aprobar",
             "activo": "core-db", "timestamp": "2026-09-24T11:00:00Z", "recibido_en": 100.0, "resuelto_en": 112.0,
             "contexto": {"familia": "acceso_credenciales"}},
            {"clase": "fp_actividad_legitima", "requiere_humano": True, "veredicto_humano": "rechazar",
             "activo": "web-banking", "timestamp": "2026-09-23T09:00:00Z", "contexto": {"familia": "reconocimiento"}},
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
        # mitre = COBERTURA POR FAMILIA: cada decisión cuenta por TODAS las técnicas de su familia
        # (familias.yml), no solo la que trajo la regla. 2 acceso_credenciales -> T1110 y T1078 = 2 c/u.
        mit = {t["tecnica"]: t["n"] for t in m["mitre"]}
        self.assertEqual(mit["T1110"], 2)
        self.assertEqual(mit["T1078"], 2)
        self.assertEqual(mit["T1595"], 1)               # 1 reconocimiento -> T1595 y T1046
        self.assertEqual([d["n"] for d in m["por_dia"]], [1, 2])   # 23 (1) antes que 24 (2)
        # Métricas de valor: carga del analista y cuánto corrige al motor.
        self.assertEqual(m["escalado_humano"], 2)                  # 2 de 3 fueron a un humano
        self.assertEqual(m["pct_humano"], round(2 / 3, 3))
        self.assertEqual(m["resueltos_humano"], 2)                 # aprobar + rechazar
        self.assertEqual(m["override"], 1)                         # 1 rechazar (corrigió al motor)
        self.assertEqual(m["tasa_override"], round(1 / 2, 3))

    def test_metricas_mitre_es_cobertura_por_familia_incluidas_fim_y_dos(self):
        # Un ataque por familia enciende TODAS las técnicas de esa familia -> la matriz se llena.
        regs = [
            {"clase": "vp_integridad", "contexto": {"familia": "integridad_fichero"}},
            {"clase": "vp_denegacion_servicio", "contexto": {"familia": "denegacion_servicio"}},
            {"clase": "no_soportada", "contexto": {"familia": "plataforma"}},   # familia sin técnicas -> no cuenta
        ]
        mit = {t["tecnica"]: t["n"] for t in tablero.metricas(regs)["mitre"]}
        self.assertEqual(mit.get("T1565"), 1)   # integridad_fichero
        self.assertEqual(mit.get("T1070"), 1)
        self.assertEqual(mit.get("T1498"), 1)   # denegacion_servicio
        self.assertEqual(mit.get("T1499"), 1)
        self.assertNotIn("T9999", mit)          # plataforma no aporta técnicas

    def test_metricas_filtra_por_rango_de_fechas_para_el_informe(self):
        regs = [
            {"id_decision": "s1", "clase": "vp_intento_acceso", "requiere_humano": False, "timestamp": "2026-09-23T09:00:00Z"},
            {"id_decision": "s2", "clase": "vp_intento_acceso", "requiere_humano": False, "timestamp": "2026-09-24T10:00:00Z"},
            {"id_decision": "s3", "clase": "no_soportada", "timestamp": "2026-10-05T10:00:00Z"},
        ]
        self.assertEqual(tablero.metricas(regs)["total"], 3)                 # sin filtro: todo (intacto)
        m = tablero.metricas(regs, desde="2026-09-24", hasta="2026-09-30")
        self.assertEqual(m["total"], 1)                                      # solo s2 (24 sep)
        self.assertEqual((m["desde"], m["hasta"]), ("2026-09-24", "2026-09-30"))  # el periodo viaja en la respuesta
        self.assertIsNone(tablero.metricas(regs)["desde"])                   # sin filtro -> sin periodo

    def test_registros_periodo_agrega_todas_las_trazas_del_directorio(self):
        # El informe por periodo cubre el histórico (una traza por ejecución), no solo la actual.
        import tempfile, os, json
        with tempfile.TemporaryDirectory() as d:
            for nombre, regs in [("trazas-2026-10-05-1000.jsonl", [{"id_decision": "a"}, {"id_decision": "b"}]),
                                 ("trazas-2026-10-06-1000.jsonl", [{"id_decision": "c"}])]:
                with open(os.path.join(d, nombre), "w", encoding="utf-8") as f:
                    for r in regs:
                        f.write(json.dumps(r) + "\n")
            open(os.path.join(d, "otro.jsonl"), "w").close()        # un fichero que no es traza no entra
            regs = tablero._registros_periodo(os.path.join(d, "trazas-2026-10-06-1000.jsonl"))
            self.assertEqual(sorted(r.get("id_decision") for r in regs), ["a", "b", "c"])

    def test_metricas_override_cuenta_reclasificar_y_sin_resueltos_no_divide(self):
        regs = [{"clase": "vp_intento_acceso", "requiere_humano": True, "veredicto_humano": "reclasificar"},
                {"clase": "vp_intento_acceso", "requiere_humano": True, "veredicto_humano": "aprobar"}]
        m = tablero.metricas(regs)
        self.assertEqual(m["override"], 1)                         # reclasificar también es override
        self.assertEqual(m["tasa_override"], 0.5)
        self.assertEqual(tablero.metricas([])["tasa_override"], 0.0)   # sin decisiones, no divide

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


class TestAuth(unittest.TestCase):
    # V1.1 #6/#8: auth OPCIONAL de la consola. Sin token -> abierto (como hoy). Con token -> Bearer exacto.
    def test_sin_token_configurado_todo_pasa(self):
        self.assertTrue(tablero.autorizado(None, None))
        self.assertTrue(tablero.autorizado("", "Bearer lo-que-sea"))

    def test_token_configurado_exige_bearer_correcto(self):
        self.assertTrue(tablero.autorizado("secreto", "Bearer secreto"))
        self.assertFalse(tablero.autorizado("secreto", "Bearer otro"))
        self.assertFalse(tablero.autorizado("secreto", None))
        self.assertFalse(tablero.autorizado("secreto", "secreto"))      # falta el prefijo 'Bearer '

    def test_operador_derivado_del_token(self):
        ops = {"tok-ana": "ana", "tok-leo": "leo"}
        self.assertEqual(tablero.operador_de(ops, "Bearer tok-ana"), "ana")
        self.assertIsNone(tablero.operador_de(ops, "Bearer desconocido"))
        self.assertIsNone(tablero.operador_de({}, "Bearer x"))
        self.assertIsNone(tablero.operador_de([1, 2], "Bearer x"))      # no-dict -> None, no revienta

    def test_autorizado_acepta_coleccion_de_tokens(self):
        # un token por persona (#8): cualquiera de la colección autentica
        self.assertTrue(tablero.autorizado(["tok-ana", "tok-leo"], "Bearer tok-leo"))
        self.assertFalse(tablero.autorizado(["tok-ana", "tok-leo"], "Bearer nadie"))
        self.assertTrue(tablero.autorizado([None, "x"], "Bearer x"))
        self.assertTrue(tablero.autorizado([], "Bearer x"))             # sin tokens -> abierta

    def test_token_no_ascii_no_revienta(self):
        # compare_digest sobre bytes: un token con tildes no debe lanzar TypeError
        self.assertTrue(tablero.autorizado("café", "Bearer café"))
        self.assertFalse(tablero.autorizado("café", "Bearer latte"))

    def test_bearer_es_case_insensitive(self):
        self.assertTrue(tablero.autorizado("s", "bearer s"))


class TestServidor(unittest.TestCase):
    def _servidor(self, estado=None, ruta_traza="/no/existe.jsonl", salud=None,
                  dependencias=None, salud_ejecutar=subprocess.run, estaticos=None,
                  token=None, operadores=None):
        estaticos = estaticos or tempfile.mkdtemp()
        with open(os.path.join(estaticos, "index.html"), "w", encoding="utf-8") as f:
            f.write("<html>tablero</html>")
        srv = tablero.crear_servidor(estado or tablero.EstadoTablero(), ruta_traza, salud=salud,
                                     dependencias=dependencias, estaticos=estaticos, puerto=0,
                                     salud_ejecutar=salud_ejecutar, token=token, operadores=operadores)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv, srv.server_address[1]

    def _get_h(self, puerto, ruta, headers):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta, headers=headers); r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, cuerpo

    def test_con_token_la_api_exige_autorizacion(self):
        _, puerto = self._servidor(token="s3creto")
        self.assertEqual(self._get(puerto, "/api/pendientes")[0], 401)                       # sin cabecera
        self.assertEqual(self._get_h(puerto, "/api/pendientes", {"Authorization": "Bearer malo"})[0], 401)
        self.assertEqual(self._get_h(puerto, "/api/pendientes", {"Authorization": "Bearer s3creto"})[0], 200)

    def test_sin_token_la_api_sigue_abierta(self):
        _, puerto = self._servidor()                                   # comportamiento actual intacto
        self.assertEqual(self._get(puerto, "/api/pendientes")[0], 200)

    def test_token_por_persona_autentica(self):
        # #8: cada persona con su token; todos autentican, uno desconocido no (no-repudio real)
        _, puerto = self._servidor(operadores={"tok-ana": "ana", "tok-leo": "leo"})
        self.assertEqual(self._get(puerto, "/api/pendientes")[0], 401)
        self.assertEqual(self._get_h(puerto, "/api/pendientes", {"Authorization": "Bearer tok-ana"})[0], 200)
        self.assertEqual(self._get_h(puerto, "/api/pendientes", {"Authorization": "Bearer tok-leo"})[0], 200)
        self.assertEqual(self._get_h(puerto, "/api/pendientes", {"Authorization": "Bearer nadie"})[0], 401)

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
        estado.fijar_resolutor(lambda pid, resp, paso=None, operador=None: vistos.append((pid, resp, paso, operador)) or True)
        srv = tablero.crear_servidor(estado, "/no/existe.jsonl", puerto=0, estaticos=tempfile.mkdtemp(),
                                     async_web=True)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        puerto = srv.server_address[1]
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": "1", "respuesta": "1", "paso": 2, "operador": "ana"})[0], 200)
        self.assertEqual(self._post(puerto, "/api/aprobar", {"id": "1", "respuesta": "1"})[0], 200)
        self.assertEqual(vistos, [("1", "1", 2, "ana"), ("1", "1", None, None)])

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


class TestPausaEstado(unittest.TestCase):
    """#8: interruptor de pausa de la automatización en EstadoTablero (seguro entre hilos)."""
    def test_pausar_y_consultar(self):
        e = tablero.EstadoTablero()
        self.assertFalse(e.pausada())
        e.pausar(True)
        self.assertTrue(e.pausada())
        e.pausar(False)
        self.assertFalse(e.pausada())


class TestPausaAPI(unittest.TestCase):
    """#8: GET /api/pausa lee el estado; POST lo fija (kill switch)."""
    def _servidor(self, estado):
        srv = tablero.crear_servidor(estado, "/no/existe.jsonl", puerto=0,
                                     estaticos=tempfile.mkdtemp(), async_web=True)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv.server_address[1]

    def _get(self, puerto, ruta):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta); r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def _post(self, puerto, ruta, obj):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("POST", ruta, json.dumps(obj), {"Content-Type": "application/json"})
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def test_get_y_post_pausa(self):
        estado = tablero.EstadoTablero()
        puerto = self._servidor(estado)
        self.assertEqual(self._get(puerto, "/api/pausa"), (200, {"pausada": False}))
        self.assertEqual(self._post(puerto, "/api/pausa", {"pausar": True}), (200, {"pausada": True}))
        self.assertTrue(estado.pausada())
        self.assertEqual(self._get(puerto, "/api/pausa"), (200, {"pausada": True}))
        self.assertEqual(self._post(puerto, "/api/pausa", {"pausar": False}), (200, {"pausada": False}))
        self.assertFalse(estado.pausada())


class TestRevertirTodoAPI(unittest.TestCase):
    """#8: POST /api/revertir-todo des-bloquea en masa las contenciones activas de la traza."""
    CAT = {"BLOQUEAR_IP": {"reversion": "definida", "comando": "iptables -A INPUT -s {ip} -j DROP",
                           "reversion_cmd": "iptables -D INPUT -s {ip} -j DROP",
                           "verificacion": "iptables -L -n | grep {ip}"}}

    def _ej(self, nodo_ip, cmd):
        return (0, "") if cmd.startswith("iptables -D") else (1, "")   # -D ok; la regla ya no aparece

    def _traza_un_bloqueo(self):
        ruta = os.path.join(tempfile.mkdtemp(), "trazas.jsonl")
        reg = {"tipo": "decision", "id_decision": "s1", "activo": "objetivo-vuln",
               "orden": {"accion_id": "BLOQUEAR_IP", "nodo_objetivo": "objetivo-vuln",
                         "nodo_ip": "192.168.1.30", "params": {"ip": "198.51.100.10"}},
               "ejecucion": {"exito": True}, "verificacion": {"verificado": True}}
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(json.dumps(traza.encadenar(reg, traza.GENESIS)) + "\n")
        return ruta

    def _post(self, puerto, ruta, obj):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
        c.request("POST", ruta, json.dumps(obj), {"Content-Type": "application/json"})
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def test_revertir_todo_desbloquea_las_activas(self):
        ruta = self._traza_un_bloqueo()
        srv = tablero.crear_servidor(tablero.EstadoTablero(), ruta, puerto=0,
                                     estaticos=tempfile.mkdtemp(), catalogo=self.CAT, ejecutor=self._ej)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        estado, cuerpo = self._post(srv.server_address[1], "/api/revertir-todo", {"operador": "ana"})
        self.assertEqual(estado, 200)
        self.assertEqual(cuerpo["revertidas"], 1)
        self.assertEqual(cuerpo["fallidas"], 0)
        # y queda registrado en la traza, con la cadena íntegra
        regs = traza.leer_registros(ruta)
        self.assertTrue(any(r.get("tipo") == "reversion" and r.get("operador") == "ana" for r in regs))
        self.assertTrue(traza.verificar(regs)["valida"])


class TestHealthz(unittest.TestCase):
    """#5: /healthz expone la salud del propio daemon (vitalidad del lazo + ingesta) para un monitor."""
    def _get(self, puerto, ruta):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta); r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def test_healthz_devuelve_la_salud_del_daemon(self):
        from prototipo import stream
        lat = stream.Latido()
        lat.alerta()
        srv = tablero.crear_servidor(tablero.EstadoTablero(), "/no/existe.jsonl", puerto=0,
                                     estaticos=tempfile.mkdtemp(), latido=lat)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        estado, cuerpo = self._get(srv.server_address[1], "/healthz")
        self.assertEqual(estado, 200)
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(cuerpo["alertas"], 1)
        self.assertIn("lazo_quietud_s", cuerpo)


class TestContencionesAPI(unittest.TestCase):
    """#4: /api/contenciones lista las contenciones activas reconstruidas de la traza (el daemon
    'recuerda' qué tiene bloqueado aunque se reinicie)."""
    CAT = {"BLOQUEAR_IP": {"reversion": "definida", "reversion_cmd": "iptables -D INPUT -s {ip} -j DROP"}}

    def _traza(self, registros):
        d = tempfile.mkdtemp()
        ruta = os.path.join(d, "trazas.jsonl")
        with open(ruta, "w", encoding="utf-8") as f:
            for r in registros:
                f.write(json.dumps(r) + "\n")
        return ruta

    def _get(self, puerto, ruta):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta); r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def test_lista_un_bloqueo_activo(self):
        ruta = self._traza([{"tipo": "decision", "id_decision": "s1", "activo": "api-movil",
                             "orden": {"accion_id": "BLOQUEAR_IP", "nodo_objetivo": "api-movil",
                                       "params": {"ip": "198.51.100.10"}},
                             "ejecucion": {"exito": True}, "verificacion": {"verificado": True}}])
        srv = tablero.crear_servidor(tablero.EstadoTablero(), ruta, puerto=0,
                                     estaticos=tempfile.mkdtemp(), catalogo=self.CAT)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        estado, cuerpo = self._get(srv.server_address[1], "/api/contenciones")
        self.assertEqual(estado, 200)
        self.assertEqual(len(cuerpo), 1)
        self.assertEqual(cuerpo[0]["ip"], "198.51.100.10")
        self.assertEqual(cuerpo[0]["accion_id"], "BLOQUEAR_IP")


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

    def _req(self, puerto, metodo, ruta, headers=None, obj=None):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        cuerpo = json.dumps(obj) if obj is not None else None
        c.request(metodo, ruta, cuerpo, headers or {})
        r = c.getresponse(); r.read()
        h = {k.lower(): v for k, v in r.getheaders()}
        c.close()
        return r.status, h

    def test_cors_refleja_origen_localhost_no_asterisco(self):
        puerto = self._srv()
        st, h = self._req(puerto, "GET", "/api/pendientes", {"Origin": f"http://localhost:{puerto}"})
        self.assertEqual(st, 200)
        self.assertEqual(h.get("access-control-allow-origin"), f"http://localhost:{puerto}")

    def test_cors_no_refleja_origen_ajeno(self):     # #6: una web de terceros no puede leer la respuesta
        puerto = self._srv()
        _, h = self._req(puerto, "GET", "/api/pendientes", {"Origin": "http://evil.com"})
        self.assertIsNone(h.get("access-control-allow-origin"))

    def test_options_preflight_204_con_cors_localhost(self):
        puerto = self._srv()
        st, h = self._req(puerto, "OPTIONS", "/api/aprobar", {"Origin": f"http://127.0.0.1:{puerto}"})
        self.assertEqual(st, 204)
        self.assertEqual(h.get("access-control-allow-origin"), f"http://127.0.0.1:{puerto}")
        self.assertIn("POST", h.get("access-control-allow-methods") or "")

    def test_host_ajeno_se_rechaza(self):            # anti DNS-rebinding (el Host no es localhost)
        puerto = self._srv()
        st, _ = self._req(puerto, "GET", "/api/pendientes", {"Host": "evil.com"})
        self.assertEqual(st, 403)

    def test_post_origen_ajeno_no_ejecuta(self):     # anti-CSRF: 403 ANTES del resolutor
        puerto = self._srv()
        st, _ = self._req(puerto, "POST", "/api/aprobar",
                          {"Content-Type": "application/json", "Origin": "http://evil.com"},
                          {"id": "1", "respuesta": "s"})
        self.assertEqual(st, 403)

    def test_post_origen_localhost_pasa_el_guardia(self):   # llega al resolutor (409: sin pendiente)
        puerto = self._srv()
        st, _ = self._req(puerto, "POST", "/api/aprobar",
                          {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{puerto}"},
                          {"id": "1", "respuesta": "s"})
        self.assertEqual(st, 409)

    def test_post_sin_origen_se_permite(self):       # cliente no-navegador (sin Origin) no se bloquea
        puerto = self._srv()
        st, _ = self._req(puerto, "POST", "/api/aprobar",
                          {"Content-Type": "application/json"}, {"id": "1", "respuesta": "s"})
        self.assertEqual(st, 409)

    def test_cuerpo_demasiado_grande_se_rechaza(self):   # #16: DoS por cuerpo sin límite
        puerto = self._srv()
        st, _ = self._req(puerto, "POST", "/api/aprobar",
                          {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{puerto}"},
                          {"id": "x" * 70000, "respuesta": "s"})
        self.assertEqual(st, 413)

    def test_content_length_negativo_se_rechaza(self):   # #16: un CL<0 hacía read(n) leer hasta EOF
        import socket
        puerto = self._srv()
        req = (f"POST /api/aprobar HTTP/1.1\r\nHost: 127.0.0.1:{puerto}\r\n"
               f"Origin: http://127.0.0.1:{puerto}\r\nContent-Type: application/json\r\n"
               f"Content-Length: -1\r\nConnection: close\r\n\r\n" + '{"id":"1"}')
        s = socket.create_connection(("127.0.0.1", puerto), timeout=3)
        s.sendall(req.encode()); resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()
        self.assertIn(b"413", resp.split(b"\r\n", 1)[0])

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

    def test_estado_red_equipo_solo_de_origen_es_origen_no_contenido(self):
        reg = self._dec(contexto={"origen_ip": "10.200.0.10"}, orden={"nodo_objetivo": "web-banking"},
                        ejecucion={"exito": True}, verificacion={"verificado": True})
        e = {n["nombre"]: n["actividad"] for n in tablero.estado_red(self.PERFIL, [reg], [], None)["nodos"]}
        self.assertEqual(e["web-banking"]["estado"], "contenido")
        # taquilla originó el ataque: estado «origen», nunca «contenido» ni «sin actividad»
        self.assertEqual((e["taquilla"]["estado"], e["taquilla"]["origen"]), ("origen", 1))

    def test_relaciones_origen_externo_se_atribuye_al_nodo_externo(self):
        ips = {"web-banking": "10.10.0.10", "taquilla": "10.200.0.10"}
        reg = self._dec(contexto={"origen_ip": "198.51.100.10"})      # IP externa: no casa con nadie interno
        self.assertEqual(tablero.relaciones(reg, ips), {"web-banking": ["objetivo"]})           # sin externos
        self.assertEqual(tablero.relaciones(reg, ips, externos=["internet"]),
                         {"web-banking": ["objetivo"], "internet": ["origen"]})                 # con externos
        interno = self._dec(contexto={"origen_ip": "10.200.0.10"})    # origen interno NO va a internet
        self.assertEqual(tablero.relaciones(interno, ips, externos=["internet"]),
                         {"web-banking": ["objetivo"], "taquilla": ["origen"]})

    def test_estado_red_internet_cuenta_como_origen_externo(self):
        perfil = {**self.PERFIL, "red": {"nodos": {"internet": {"tipo": "externo"}},
                                         "enlaces": {"web-banking": "fw-core", "fw-core": "internet"}}}
        reg = self._dec(contexto={"origen_ip": "198.51.100.10"}, orden={"nodo_objetivo": "web-banking"},
                        ejecucion={"exito": True}, verificacion={"verificado": True})
        nodos = {n["nombre"]: n["actividad"] for n in tablero.estado_red(perfil, [reg], [], None)["nodos"]}
        self.assertEqual(nodos["internet"]["origen"], 1)              # ya no sale originados 0
        self.assertEqual(nodos["internet"]["estado"], "origen")       # ya no sale «sin actividad»
        self.assertEqual(nodos["web-banking"]["estado"], "contenido")

    def test_estado_nodo_origen_informa_pero_objetivo_manda(self):
        base = {"pendientes": 0, "origen": 2, "_ultima_objetivo": None, "_contenido": False}
        self.assertEqual(tablero._estado_nodo(None, base), "origen")
        atacado = {**base, "_ultima_objetivo": self._dec(orden=None)}  # objetivo sin contener gana
        self.assertEqual(tablero._estado_nodo(None, atacado), "atacado")
        contenido = {**base, "_contenido": True}                       # contenido gana sobre origen
        self.assertEqual(tablero._estado_nodo(None, contenido), "contenido")

    def test_estado_red_forma_y_pendientes_sin_alerta(self):
        r = tablero.estado_red(self.PERFIL, [{"tipo": "error"}], [{"id": "1", "tipo": "escalada"}], None)
        self.assertEqual(r["enlaces"], [["web-banking", "fw-core"]])
        self.assertEqual(r["dependencias"], [["web-banking", "middleware"]])
        self.assertEqual(r["zonas"], [{"nombre": "Red", "nodos": ["middleware", "taquilla", "web-banking"]}])
        nodo = [n for n in r["nodos"] if n["nombre"] == "web-banking"][0]
        self.assertEqual(nodo["actividad"]["objetivo"], 0)

    def test_registros_cacheados_reusa_mientras_no_cambia_el_fichero(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "t.jsonl")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(json.dumps(self._dec(orden=None)) + "\n")
            a = tablero._registros_cacheados(ruta)
            self.assertIs(tablero._registros_cacheados(ruta), a)   # no cambió: mismo objeto (cache)
            with open(ruta, "a", encoding="utf-8") as f:           # crece el fichero
                f.write(json.dumps(self._dec(orden=None)) + "\n")
            b = tablero._registros_cacheados(ruta)
            self.assertEqual(len(b), 2)                            # cambió: relee
            self.assertEqual(tablero._registros_cacheados("/no/existe.jsonl"), [])

    def test_resumen_traza_expone_relaciones_y_contencion(self):
        reg = self._dec(orden={"nodo_objetivo": "web-banking"}, ejecucion={"exito": True}, verificacion={"verificado": True})
        r = tablero._resumen_traza(reg, tablero.ips_de(self.PERFIL))
        self.assertEqual(r["relaciones"], {"web-banking": ["objetivo", "contuvo_aqui"]})
        self.assertEqual((r["contencion"], r["dispositivo"]), ("contenida", "web-banking"))

    def test_estado_red_reclasificada_como_fp_no_pinta_atacado(self):
        reg = self._dec(orden=None, veredicto_humano="reclasificar", clase_reclasificada="fp_actividad_legitima")
        e = {n["nombre"]: n["actividad"]["estado"] for n in tablero.estado_red(self.PERFIL, [reg], [], None)["nodos"]}
        self.assertEqual(e["web-banking"], "sin_actividad")

    def test_red_mal_formada_no_tumba_trazas_ni_estado(self):
        perfil = {**self.PERFIL, "red": {"enlaces": ["a", "b"]}}
        r = tablero.estado_red(perfil, [self._dec(orden=None)], [], None)
        self.assertTrue(r["avisos"])
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "t.jsonl")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(json.dumps(self._dec(orden=None)) + "\n")
            self.assertEqual(len(tablero.lista_trazas(ruta, perfil=perfil)), 1)

    def test_red_que_revienta_cae_a_la_reconstruccion_con_aviso(self):
        from unittest import mock
        real = tablero.red.red_de
        def rota(p):
            if "red" in (p or {}):
                raise RuntimeError("boom")
            return real(p)
        with mock.patch.object(tablero.red, "red_de", rota):
            perfil = {**self.PERFIL, "red": {"zonas": {}}}
            self.assertIn("web-banking", tablero.ips_de(perfil))
            r = tablero.estado_red(perfil, [], [], None)
            self.assertTrue(any("boom" in a for a in r["avisos"]))

    def test_la_vista_de_pendientes_expone_activo_y_origen(self):
        v = tablero._vista_pendiente({"id": "1", "alerta": {"activo": "web-banking", "origen_ip": "10.200.0.10"},
                                      "decision": {}, "clave": ("x",)})
        self.assertEqual((v["activo"], v["origen_ip"]), ("web-banking", "10.200.0.10"))
        self.assertNotIn("alerta", v)


class TestResumenRecomendacion(unittest.TestCase):
    def test_resumen_traza_expone_la_recomendacion(self):
        reg = {"id_decision": "d1", "recomendacion": {"respuesta": "endurecer_servicio", "servicio": "rdp"}}
        self.assertEqual(tablero._resumen_traza(reg)["recomendacion"],
                         {"respuesta": "endurecer_servicio", "servicio": "rdp"})

    def test_resumen_traza_sin_recomendacion_es_none(self):
        self.assertIsNone(tablero._resumen_traza({"id_decision": "d1"})["recomendacion"])


class TestCasoAPI(unittest.TestCase):
    """A4 del visor: GET /api/caso/<id> pliega el ciclo de caso sobre el fichero COMPLETO de la traza
    (como /api/metricas), para que el caso no «rejuvenezca» cuando sus actualizaciones salen de la
    ventana de los últimos registros que sirve /api/trazas."""

    def _servir(self, registros):
        d = tempfile.mkdtemp()
        ruta = os.path.join(d, "trazas.jsonl")
        with open(ruta, "w", encoding="utf-8") as f:
            for r in registros:
                f.write(json.dumps(r) + "\n")
        srv = tablero.crear_servidor(tablero.EstadoTablero(), ruta, puerto=0, estaticos=tempfile.mkdtemp())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv.server_address[1]

    def _get(self, puerto, ruta, cabeceras=None):
        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=3)
        c.request("GET", ruta, headers=cabeceras or {})
        r = c.getresponse(); cuerpo = r.read(); cab = dict(r.getheaders()); c.close()
        return r.status, json.loads(cuerpo), cab

    def test_pliega_el_caso_completo(self):
        puerto = self._servir([
            {"tipo": "actualizacion_caso", "id_decision": "s1", "estado": "en_revision",
             "operador": "ana", "decidido_en": "t1"},
            {"tipo": "actualizacion_caso", "id_decision": "s1", "nota": "visto con red",
             "operador": "ana", "decidido_en": "t2"},
        ])
        estado, cuerpo, _ = self._get(puerto, "/api/caso/s1")
        self.assertEqual(estado, 200)
        self.assertEqual(cuerpo["estado"], "en_revision")
        self.assertEqual(cuerpo["notas"][0]["texto"], "visto con red")

    def test_sin_actualizaciones_el_caso_es_nuevo(self):
        puerto = self._servir([])
        estado, cuerpo, _ = self._get(puerto, "/api/caso/zz")
        self.assertEqual(estado, 200)
        self.assertEqual(cuerpo, {"estado": "nuevo", "asignado": None, "notas": []})

    def test_cors_expone_la_cabecera_date(self):
        # A3 del visor: el SLA se ancla a la cabecera `Date`; en dev (origen :5173) el navegador solo
        # la deja leer si va en Access-Control-Expose-Headers.
        puerto = self._servir([])
        _, _, cab = self._get(puerto, "/api/pausa", {"Origin": "http://localhost:5173"})
        self.assertIn("date", cab.get("Access-Control-Expose-Headers", "").lower())


class TestColaAcotada(unittest.TestCase):
    """M3 de la auditoría 20/10: la cola de pendientes tiene tope — un atacante que fabrique claves
    infinitas (un srcip distinto por alerta) no agota la memoria del daemon. Al llenarse se desaloja
    la tarjeta MENOS severa y más vieja (la que el analista vería la última), nunca una en curso."""

    def _entrada(self, n, severidad):
        return {"clave": (f"ip{n}", "fam"), "severidad": severidad}

    def test_al_tope_desaloja_la_menos_severa_mas_vieja_y_lo_cuenta(self):
        import contextlib, io
        estado = tablero.EstadoTablero(max_pendientes=3)
        for n, sev in ((1, 5), (2, 2), (3, 7)):
            estado.encolar_decision(self._entrada(n, sev))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            estado.encolar_decision(self._entrada(4, 4))   # llena: cae la de severidad 2
        pend = estado.decisiones_pendientes()
        self.assertEqual(len(pend), 3)
        self.assertEqual({p["clave"] for p in pend}, {("ip1", "fam"), ("ip3", "fam"), ("ip4", "fam")})
        self.assertEqual(estado.descartadas_tope, 1)
        self.assertIn("tope", err.getvalue())              # el desalojo deja rastro, no es silencioso

    def test_a_igual_severidad_cae_la_mas_vieja(self):
        import contextlib, io
        estado = tablero.EstadoTablero(max_pendientes=2)
        a = estado.encolar_decision(self._entrada(1, 3))
        estado.encolar_decision(self._entrada(2, 3))
        with contextlib.redirect_stderr(io.StringIO()):
            estado.encolar_decision(self._entrada(3, 3))
        self.assertIsNone(estado.ver_decision(a))          # la primera en llegar fue la desalojada

    def test_una_decision_en_curso_no_se_desaloja(self):
        import contextlib, io
        estado = tablero.EstadoTablero(max_pendientes=1)
        a = estado.encolar_decision(self._entrada(1, 1))
        estado.tomar_decision(a)                           # el analista ya respondió: ejecutándose
        with contextlib.redirect_stderr(io.StringIO()):
            b = estado.encolar_decision(self._entrada(2, 9))
        self.assertIsNotNone(estado.ver_decision(a))       # la en curso sobrevive (el tope se excede)
        self.assertIsNotNone(estado.ver_decision(b))

    def test_el_desalojo_se_traza_via_descartador(self):
        # RF-09: una tarjeta que el analista nunca verá no puede desaparecer del rastro auditado.
        import contextlib, io
        estado = tablero.EstadoTablero(max_pendientes=1)
        trazadas = []
        estado.fijar_descartador(trazadas.append)
        estado.encolar_decision(self._entrada(1, 2))
        with contextlib.redirect_stderr(io.StringIO()):
            estado.encolar_decision(self._entrada(2, 5))
        self.assertEqual(len(trazadas), 1)
        self.assertEqual(trazadas[0]["clave"], ("ip1", "fam"))

    def test_un_descartador_que_falla_no_rompe_el_encolado(self):
        import contextlib, io
        estado = tablero.EstadoTablero(max_pendientes=1)
        estado.fijar_descartador(lambda e: (_ for _ in ()).throw(OSError("disco lleno")))
        estado.encolar_decision(self._entrada(1, 2))
        with contextlib.redirect_stderr(io.StringIO()):
            b = estado.encolar_decision(self._entrada(2, 5))
        self.assertIsNotNone(estado.ver_decision(b))       # la nueva entró pese al fallo al trazar


if __name__ == "__main__":
    unittest.main()
