import json, os, unittest, yaml
from prototipo.motor import triaje
from prototipo.accion import catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))

def j(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return json.loads(f.read().strip())

def y(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return yaml.safe_load(f)

class TestProcesar(unittest.TestCase):
    def test_lazo_completo_una_alerta(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="2026-08-31T00:00:00Z")
        # fuerza bruta SSH contra objetivo-vuln con SSH expuesto -> VP intento -> BLOQUEAR_IP localizado -> permite
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["accion_propuesta"], "BLOQUEAR_IP")
        self.assertEqual(r["resultado_filtro"], "permite")
        self.assertIn("192.168.1.10", r["justificacion"])

    def test_fim_integridad_aisla_el_host_en_el_borde_siempre_con_humano(self):
        # 6ª familia (FIM): un fichero crítico cambió -> vp_integridad -> AISLAR_NODO (cuarentena en el
        # cortafuegos de borde del host, reusa el mecanismo de BLOQUEAR_IP_FIREWALL). Es nunca_automatica
        # -> SIEMPRE validación humana. Con topología hay cuarentena ejecutable (retenida, no vetada).
        a = {**j("alerta_vp.json"), "familia": "integridad_fichero"}   # activo = objetivo-vuln
        p = {**y("perfil.yml"),
             "activos": {"objetivo-vuln": {"ip": "192.168.1.30"}, "borde": {"ip": "192.168.1.1"}},
             "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                           "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_integridad")
        self.assertEqual(r["accion_propuesta"], "AISLAR_NODO")
        self.assertEqual(r["accion_final"], "AISLAR_NODO")   # retenida: hay cuarentena ejecutable
        self.assertTrue(r["requiere_humano"])                # nunca_automatica -> humano incondicional

    def test_fim_sin_cortafuegos_de_borde_no_deja_accion_ejecutable(self):
        # Sin topología (sin ruta a un cortafuegos) un host hoja no se puede aislar: fail-closed a veto
        # duro (el humano recibe la alerta, pero no una acción que no se podría ejecutar).
        a = {**j("alerta_vp.json"), "familia": "integridad_fichero"}
        r = triaje.procesar(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_integridad")
        self.assertIsNone(r["accion_final"])          # vetada: no hay cuarentena ejecutable
        self.assertTrue(r["requiere_humano"])

    def test_dos_limita_la_banda_del_host_con_interfaz_y_pide_humano(self):
        # 7ª familia (DoS/flood): vp_denegacion_servicio -> LIMITAR_BANDA (contención gradual) sobre la
        # interfaz del host víctima; alcanza_servicio -> retenida para humano (no nunca_automatica).
        a = {**j("alerta_vp.json"), "familia": "denegacion_servicio"}   # activo = objetivo-vuln
        p = {**y("perfil.yml"), "activos": {"objetivo-vuln": {"ip": "192.168.1.30", "interfaz": "eth1"}}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_denegacion_servicio")
        self.assertEqual(r["accion_propuesta"], "LIMITAR_BANDA")
        self.assertEqual(r["accion_final"], "LIMITAR_BANDA")   # retenida (hay interfaz)
        self.assertTrue(r["requiere_humano"])

    def test_dos_sin_interfaz_no_deja_accion_ejecutable(self):
        a = {**j("alerta_vp.json"), "familia": "denegacion_servicio"}
        r = triaje.procesar(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_denegacion_servicio")
        self.assertIsNone(r["accion_final"])          # vetada: sin interfaz no hay throttle

    def test_acceso_consumado_corta_la_conexion_del_atacante(self):
        # 8ª familia: intrusión exitosa -> vp_acceso_consumado -> MATAR_CONEXION sobre la IP de origen
        # (cortar la sesión viva). origen_ip presente (login del atacante).
        a = {**j("alerta_vp.json"), "familia": "acceso_consumado"}   # origen_ip 192.168.1.10
        r = triaje.procesar(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_acceso_consumado")
        self.assertEqual(r["accion_propuesta"], "MATAR_CONEXION")
        self.assertEqual(r["accion_final"], "MATAR_CONEXION")

    def test_acceso_consumado_sin_ip_de_origen_se_veta(self):
        # Como toda acción sobre IP: sin origen no hay conexión que cortar -> veto fail-closed.
        a = {**j("alerta_vp.json"), "familia": "acceso_consumado", "origen_ip": None}
        r = triaje.procesar(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_acceso_consumado")
        self.assertIsNone(r["accion_final"])

    def test_exfiltracion_bloquea_el_destino_en_el_borde_con_humano(self):
        # 9ª familia (exfiltración/C2): vp_exfiltracion -> BLOQUEAR_DESTINO (corta el egreso al destino
        # malicioso en el cortafuegos de borde del host que baliza). alcanza_servicio -> retenida para
        # humano. El destino sale de la alerta (dstip); con topología hay acción ejecutable.
        a = {**j("alerta_vp.json"), "familia": "exfiltracion", "destino_ip": "203.0.113.66"}  # activo = objetivo-vuln
        p = {**y("perfil.yml"),
             "activos": {"objetivo-vuln": {"ip": "192.168.1.30"}, "borde": {"ip": "192.168.1.1"}},
             "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                           "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_exfiltracion")
        self.assertEqual(r["accion_propuesta"], "BLOQUEAR_DESTINO")
        self.assertEqual(r["accion_final"], "BLOQUEAR_DESTINO")   # retenida: hay egreso que cortar
        self.assertTrue(r["requiere_humano"])

    def test_exfiltracion_sin_destino_se_veta(self):
        # Sin destino (dstip ausente) no hay egreso que cortar -> veto fail-closed, sin acción.
        a = {**j("alerta_vp.json"), "familia": "exfiltracion"}   # sin destino_ip
        p = {**y("perfil.yml"),
             "activos": {"objetivo-vuln": {"ip": "192.168.1.30"}, "borde": {"ip": "192.168.1.1"}},
             "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                           "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_exfiltracion")
        self.assertIsNone(r["accion_final"])

    def test_malware_aisla_el_host_siempre_con_humano(self):
        # 10ª familia (malware/rootkit): vp_malware -> AISLAR_NODO (reusa la cuarentena en el borde de
        # FIM). nunca_automatica -> SIEMPRE humano. Cierra un hueco: un hit de VirusTotal ya no cae en
        # 'plataforma' (ruido) ni en no_soportada; se reconoce y se contiene.
        a = {**j("alerta_vp.json"), "familia": "malware"}   # activo = objetivo-vuln
        p = {**y("perfil.yml"),
             "activos": {"objetivo-vuln": {"ip": "192.168.1.30"}, "borde": {"ip": "192.168.1.1"}},
             "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                           "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_malware")
        self.assertEqual(r["accion_propuesta"], "AISLAR_NODO")
        self.assertEqual(r["accion_final"], "AISLAR_NODO")   # retenida: hay cuarentena ejecutable
        self.assertTrue(r["requiere_humano"])                # nunca_automatica -> humano incondicional

    def test_no_soportada_grave_se_escala_a_revision_humana(self):
        # Un no_soportada de SEVERIDAD ALTA (nivel Wazuh >= umbral del perfil) no debe quedar solo en el
        # log: se marca para REVISIÓN humana (requiere_humano, resultado 'revisar'), SIN acción (no hay
        # nada que contener). El ruido de plataforma (nivel bajo) sigue sin molestar. Opt-in del perfil.
        a = {**j("alerta_vp.json"), "familia": "plataforma", "nivel_wazuh": 12}   # fuera de las 8 -> no_soportada
        p = {**y("perfil.yml"), "continuidad": {"revisar_no_soportada_nivel": 10}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "no_soportada")
        self.assertTrue(r["requiere_humano"])              # se escala a revisión
        self.assertEqual(r["resultado_filtro"], "revisar")
        self.assertIsNone(r["accion_final"])               # sin acción: no hay nada que contener

    def test_no_soportada_ruidoso_sigue_sin_molestar(self):
        a = {**j("alerta_vp.json"), "familia": "plataforma", "nivel_wazuh": 3}   # ruido de plataforma
        p = {**y("perfil.yml"), "continuidad": {"revisar_no_soportada_nivel": 10}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "no_soportada")
        self.assertFalse(r["requiere_humano"])             # nivel bajo < umbral -> no se escala

    def test_umbral_revisar_mal_escrito_no_rompe_el_triaje(self):
        # Robustez (revisión): un umbral no numérico en el YAML (p.ej. "10" string) NO debe lanzar
        # TypeError en `nivel >= umbral`; se trata como apagado (fail-safe), no se escala.
        a = {**j("alerta_vp.json"), "familia": "plataforma", "nivel_wazuh": 12}
        for malo in ("10", [10], True, {}):
            p = {**y("perfil.yml"), "continuidad": {"revisar_no_soportada_nivel": malo}}
            r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
            self.assertEqual(r["clase"], "no_soportada")
            self.assertFalse(r["requiere_humano"], malo)   # umbral inválido -> no escala, sin crash

    def test_sin_el_opt_in_del_perfil_el_no_soportada_no_se_escala(self):
        # Sin la clave en el perfil el feature está APAGADO (comportamiento de siempre) -> el canónico,
        # medido sobre un perfil sin esta clave, no se mueve.
        a = {**j("alerta_vp.json"), "familia": "plataforma", "nivel_wazuh": 12}
        r = triaje.procesar(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "no_soportada")
        self.assertFalse(r["requiere_humano"])             # opt-in ausente -> apagado

    def test_aviso_vigilancia_en_el_punto_ciego(self):
        # low-and-slow desde un origen de confianza: el motor dice legítimo, pero el volumen de la
        # ventana larga dispara el aviso ASESOR (no cambia el veredicto ni ejecuta nada).
        a = {**j("alerta_vp.json"), "rafaga_60s": 4, "rafaga_600s": 24}
        p = {**y("perfil.yml"), "origenes_legitimos": ["192.168.1.10"],
             "rafaga": {"umbral": 9, "umbral_largo": 15}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "fp_actividad_legitima")   # el veredicto NO cambia
        self.assertIsNone(r["accion_final"])                    # sigue sin contención (asesor)
        self.assertIsNotNone(r["aviso"])

    def test_sin_aviso_en_una_decision_normal(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertIsNone(r["aviso"])

    def test_la_traza_guarda_los_insumos_de_la_decision(self):
        # RF-09/RF-13: sin la ráfaga, el origen legítimo o la postura no se puede auditar por qué
        # salió esa clase (la regla de ráfaga cambia la clase y la confianza).
        a = {**j("alerta_vp.json"), "rafaga_60s": 12}
        p = {**y("perfil.yml"), "rafaga": {"umbral": 9}}
        r = triaje.procesar(a, j("hallazgos.json"), p, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual((r["tipo"], r["version_esquema"]), ("decision", 1))
        c = r["contexto"]
        self.assertEqual((c["rafaga_60s"], c["umbral_rafaga"], c["origen_legitimo"]), (12, 9, False))
        self.assertEqual(c["familia"], a.get("familia"))
        self.assertEqual(c["nivel_wazuh"], a.get("nivel_wazuh"))
        self.assertEqual(c["criticidad"], "alta")
        self.assertEqual(c["postura"], {"expuesto": True, "servicios_abiertos": ["ssh"]})

    def test_amenaza_enrutada_lleva_ruta_en_la_traza_sin_accion(self):
        alerta = {"familia": "explotacion_conocida", "origen_ip": "203.0.113.9",
                  "activo": "web-banking", "servicio": "https", "mitre": ["T1190"]}
        perfil = {"activos": {}, "continuidad": {}, "rutas": {"appsec": "cola-appsec-banco"}}
        tr = triaje.procesar(alerta, {"nodos": {}}, perfil, "bancario", CAT, "d1", "t")
        self.assertEqual(tr["clase"], "amenaza_enrutada")
        self.assertEqual(tr["ruta"], "cola-appsec-banco")
        self.assertIsNone(tr["accion_propuesta"])

class TestJustificarFn(unittest.TestCase):
    def test_procesar_usa_el_justificar_fn_inyectado(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                            id_decision="d1", timestamp="2026-08-31T00:00:00Z",
                            justificar_fn=lambda a, c, cl: "JUSTIFICACION-INYECTADA")
        self.assertEqual(r["justificacion"], "JUSTIFICACION-INYECTADA")
        self.assertEqual(r["version_justificador"], "plantilla-0")   # str -> plantilla (RF-09)

    def test_la_traza_guarda_la_justificacion_del_modelo_descartada(self):
        desc = {"texto": "texto generico", "motivo": "no citaba ningún dato de la alerta"}
        just = lambda a, c, cl: {"texto": "PLANTILLA", "version_justificador": "plantilla-0", "llm_descartada": desc}
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                            id_decision="d3", timestamp="t", justificar_fn=just)
        self.assertEqual(r["justificacion_descartada"], desc)

    def test_procesar_registra_metadata_del_justificador_dict(self):
        def just_dict(a, c, cl):
            return {"texto": "TEXTO", "version_justificador": "llm-1b-0:modelo.gguf", "pasajes_usados": ["p1"]}
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                            id_decision="d2", timestamp="t", justificar_fn=just_dict)
        self.assertEqual(r["justificacion"], "TEXTO")
        self.assertEqual(r["version_justificador"], "llm-1b-0:modelo.gguf")
        self.assertEqual(r["pasajes_usados"], ["p1"])

    def test_procesar_registra_consulta_rag_agentica(self):
        def just_dict(a, c, cl):
            return {"texto": "TEXTO", "version_justificador": "llm-1b-0:m.gguf",
                    "pasajes_usados": ["d3fend-D3-ITF"], "consulta_usada": "D3-ITF filtrado",
                    "recuperacion_agentica": True}
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                            id_decision="d4", timestamp="t", justificar_fn=just_dict)
        self.assertEqual(r["consulta_rag"], "D3-ITF filtrado")
        self.assertTrue(r["recuperacion_agentica"])

class TestImpactoDeterminado(unittest.TestCase):
    def test_la_traza_lleva_el_impacto_determinado(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["impacto_determinado"]["accion_id"], "BLOQUEAR_IP")
        self.assertEqual(r["impacto_determinado"]["actor"]["tipo"], "desconocido")   # la fixture no declara IPs

    def test_con_inventario_el_bloqueo_del_puesto_va_al_humano(self):
        p = y("perfil.yml")
        p["activos"]["puesto"]["ip"] = "192.168.1.10"
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), p, "prueba", CAT,
                            id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_intento_acceso")            # la clasificación no cambia
        self.assertEqual((r["resultado_filtro"], r["requiere_humano"]), ("veta", True))
        self.assertEqual(r["impacto_determinado"]["actor"]["nombre"], "puesto")

    def test_pasa_los_hallazgos_al_filtro(self):
        from unittest import mock
        from prototipo.motor import perfil as perfilm
        h = j("hallazgos.json")
        with mock.patch.object(perfilm, "filtrar", wraps=perfilm.filtrar) as f:
            triaje.procesar(j("alerta_vp.json"), h, y("perfil.yml"), "prueba", CAT, "d1", "t")
        self.assertIs(f.call_args.kwargs["hallazgos"], h)

    def test_sin_accion_no_hay_impacto_determinado(self):
        alerta = {"familia": "explotacion_conocida", "origen_ip": "203.0.113.9",
                  "activo": "web-banking", "servicio": "https", "mitre": ["T1190"]}
        tr = triaje.procesar(alerta, {"nodos": {}}, {"activos": {}, "continuidad": {}}, "p", CAT, "d1", "t")
        self.assertIsNone(tr["impacto_determinado"])


class TestRecomendacion(unittest.TestCase):
    def test_fuerza_bruta_ssh_recomienda_contener_origen_sin_cambiar_accion(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["recomendacion"]["respuesta"], "contener_origen")
        self.assertEqual(r["recomendacion"]["accion_sugerida"], "BLOQUEAR_IP")
        self.assertEqual(r["accion_final"], "BLOQUEAR_IP")      # la accion automatica NO cambia

    def test_servicio_rdp_expuesto_recomienda_endurecer(self):
        alerta = {"familia": "acceso_credenciales", "activo": "srv", "servicio": "rdp",
                  "origen_ip": "203.0.113.9", "regla_id": "5763"}
        perfil = {"activos": {"srv": {"ip": "10.0.0.5", "criticidad": "alta", "servicios_prestados": [3389]}},
                  "ip_gestion": "10.0.0.1"}
        hall = {"nodos": {"srv": [{"puerto": 3389, "servicio": "rdp", "estado": "open"}]}}
        r = triaje.procesar(alerta, hall, perfil, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_intento_acceso")       # rdp expuesto -> VP
        self.assertEqual(r["recomendacion"]["respuesta"], "endurecer_servicio")

    def test_fp_no_lleva_recomendacion(self):
        # explotacion no es FP; usa un origen legitimo para caer en fp_actividad_legitima
        alerta = {"familia": "acceso_credenciales", "activo": "web-banking", "servicio": "ssh",
                  "origen_ip": "10.100.0.10", "regla_id": "5763"}
        perfil = {"activos": {"web-banking": {"servicios_prestados": [22]}},
                  "origenes_legitimos": ["10.100.0.10"], "ip_gestion": "10.100.0.10"}
        r = triaje.procesar(alerta, {"nodos": {}}, perfil, "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "fp_actividad_legitima")
        self.assertIsNone(r["recomendacion"])


class TestTriajeLote(unittest.TestCase):
    def test_lineas_vacias_y_con_espacios_se_saltan_sin_mover_la_numeracion(self):
        # Revisión del traslado a servicio/triaje_lote: parsear_linea ya hace el strip y devuelve
        # None en vacías — este test FIJA que el CLI movido se comporta igual que el original
        # (las saltadas consumen índice: la tercera línea válida sigue siendo d2).
        import contextlib, io, json, os, tempfile
        from prototipo.servicio import triaje_lote
        d = tempfile.mkdtemp()
        alertas, salida = os.path.join(d, "a.jsonl"), os.path.join(d, "s.jsonl")
        valida = json.dumps({"id_alerta": "x", "activo": "objetivo-vuln", "origen_ip": "1.2.3.4",
                             "familia": "acceso_credenciales", "servicio": "ssh", "regla_id": "5760"})
        with open(alertas, "w", encoding="utf-8") as f:
            f.write("\n   \n" + valida + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            triaje_lote.main(["triaje_lote", alertas,
                              os.path.join(FX, "perfil.yml"), os.path.join(FX, "hallazgos.json"), salida])
        regs = [json.loads(l) for l in open(salida, encoding="utf-8")]
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["id_decision"], "d2")     # las dos saltadas consumieron d0 y d1
