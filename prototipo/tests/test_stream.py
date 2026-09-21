import io, json, os, tempfile, unittest, yaml
from prototipo import stream, catalogo, lazo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))

def _txt(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return f.read().strip()
def j(n): return json.loads(_txt(n))
def y(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return yaml.safe_load(f)

def _linea_wazuh(srcip="192.168.1.10", rule_id="5760"):
    # una alerta CRUDA de Wazuh (la que el adaptador normaliza): activo <- predecoder.hostname,
    # servicio ssh <- groups sshd, familia acceso_credenciales <- groups authentication_failed.
    return json.dumps({
        "id": "a1", "rule": {"id": rule_id, "level": 10, "description": "sshd brute force",
                             "groups": ["sshd", "authentication_failed"],
                             "mitre": {"id": ["T1110.001"]}},
        "predecoder": {"hostname": "objetivo-vuln", "program_name": "sshd"},
        "data": {"srcip": srcip}, "timestamp": "2026-08-31T00:00:00Z",
        "full_log": "Failed password for root from %s" % srcip})


class TestBucleInmediato(unittest.TestCase):
    def test_una_alerta_produce_un_incidente_y_traza(self):
        buf = io.StringIO()
        salidas = []
        resumen = stream.ejecutar(
            [_linea_wazuh(), "", "no-es-json", None],
            hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"), perfil_nombre="prueba",
            catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None,
            ventana_agrupacion=0, salida_traza=buf,
            escribir=lambda *a, **k: salidas.append(" ".join(str(x) for x in a)), leer=lambda *_: "2")
        self.assertEqual(resumen["alertas"], 1)      # la vacía y la corrupta se saltan (RNF-07)
        self.assertEqual(resumen["incidentes"], 1)
        lineas = [l for l in buf.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(lineas), 1)
        traza = json.loads(lineas[0])
        self.assertEqual(traza["clase"], "vp_intento_acceso")
        # RF-09: lo que escribe el daemon esta encadenado y verifica
        from prototipo import traza as traza_mod
        self.assertEqual(traza["hash_previo"], traza_mod.GENESIS)
        self.assertTrue(traza_mod.verificar([traza])["valida"])
        self.assertIn("192.168.1.10", traza["justificacion"])


class TestModoAgente(unittest.TestCase):
    def test_ejecutar_delega_al_mitigar_fn_y_cuenta(self):
        buf = io.StringIO()
        def mitigar(decision, alerta, leer):
            return {"resultado": "mitigado", "escalado": True, "dispositivo_ejecutor": "gateway"}
        resumen = stream.ejecutar(
            [_linea_wazuh(), None], hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
            perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None,
            ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
            leer=lambda *_: "s", mitigar_fn=mitigar)
        self.assertEqual(resumen["incidentes"], 1)
        self.assertEqual(resumen["ejecutadas"], 1)                 # resultado mitigado -> ejecutada
        traza = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(traza["mitigacion_agente"]["dispositivo_ejecutor"], "gateway")


class TestModoAgenteEscalada(unittest.TestCase):
    def test_daemon_delega_y_el_agente_escala_a_firewall(self):
        from prototipo import agente_mitigacion as ag
        perfil = dict(y("perfil.yml"))
        perfil["topologia"] = {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30"},
                               "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}
        perfil["ip_gestion"] = "192.168.1.100"

        class EjecEscalado:                               # host caído / firewall responde (con estado)
            def __init__(s): s.ap = set()
            def __call__(s, ip, cmd):
                if ip == "192.168.1.30": return (255, "refused")
                if "grep" in cmd: return (0, "DROP") if ip in s.ap else (1, "")
                s.ap.add(ip); return (0, "")

        guion = ['Action: {"tool":"ejecutar_comando","args":{"dispositivo":"objetivo-vuln","accion":"bloquear_ip"}}',
                 'Action: {"tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
                 'Final: {"resultado":"mitigado","dispositivo_ejecutor":"gateway"}']
        class Gen:
            def __init__(s): s.i = 0
            def __call__(s, p):
                v = guion[s.i] if s.i < len(guion) else "ruido"; s.i += 1; return v

        ejec = EjecEscalado()
        mitigar = lambda decision, alerta, leer: ag.bucle_react(
            alerta, decision["clase"], perfil, CAT, ejec, Gen(), leer=lambda *_: "s",
            autonomo=False, escribir=lambda *a, **k: None)
        buf = io.StringIO()
        stream.ejecutar([_linea_wazuh(), None], hallazgos=j("hallazgos.json"), perfil=perfil,
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=ejec, justificar_fn=None,
                        ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
                        leer=lambda *_: "s", mitigar_fn=mitigar)
        traza = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertTrue(traza["mitigacion_agente"]["escalado"])                       # host->firewall
        self.assertEqual(traza["mitigacion_agente"]["dispositivo_ejecutor"], "gateway")


class TestVentana(unittest.TestCase):
    def test_rafaga_se_colapsa_en_un_incidente(self):
        # 3 alertas de la misma clave llegan "dentro" de la ventana; luego un tick vence la ventana.
        reloj = iter([0, 0, 1, 2, 100, 100, 100]).__next__   # el 5º valor (100) vence ventana=10
        fuente = [_linea_wazuh(), _linea_wazuh(), _linea_wazuh(), None]
        buf = io.StringIO()
        resumen = stream.ejecutar(
            fuente, hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"), perfil_nombre="prueba",
            catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None,
            ventana_agrupacion=10, salida_traza=buf,
            escribir=lambda *a, **k: None, leer=lambda *_: "2", reloj=reloj)
        self.assertEqual(resumen["alertas"], 3)
        self.assertEqual(resumen["incidentes"], 1)          # las 3 -> un incidente (misma clave)
        self.assertEqual(len([l for l in buf.getvalue().splitlines() if l.strip()]), 1)

    def test_fuente_agotada_descarga_lo_pendiente(self):
        reloj = iter([0, 0, 0]).__next__
        resumen = stream.ejecutar(
            [_linea_wazuh(), _linea_wazuh()], hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
            perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(),
            ventana_agrupacion=10, salida_traza=None,
            escribir=lambda *a, **k: None, leer=lambda *_: "2", reloj=reloj)
        self.assertEqual(resumen["incidentes"], 1)          # se descarga al agotar la fuente


class TestFuentes(unittest.TestCase):
    def test_fichero_inexistente_rinde_tick_y_no_rompe(self):
        gen = stream.leer_lineas_fichero("/no/existe/aqui.json", intervalo=0,
                                         detener=iter([False, True]).__next__, dormir=lambda s: None)
        self.assertIsNone(next(gen))           # primer yield: tick de reposo, sin excepcion

    def test_fichero_desde_inicio_lee_lineas_existentes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write('{"a":1}\n{"a":2}\n'); ruta = f.name
        try:
            stop = iter([False, False, False, True]).__next__
            got = list(stream.leer_lineas_fichero(ruta, intervalo=0, desde_inicio=True,
                                                  detener=stop, dormir=lambda s: None))
        finally:
            os.unlink(ruta)
        self.assertEqual([g for g in got if g is not None][:2], ['{"a":1}\n', '{"a":2}\n'])

    def test_stdin_rinde_cada_linea(self):
        got = list(stream.leer_lineas_stdin(io.StringIO("l1\nl2\n")))   # StringIO -> sin ticks, iteración simple
        self.assertEqual(got, ["l1\n", "l2\n"])

    def test_stdin_rinde_ticks_en_reposo_y_lee_la_linea(self):
        r, w = os.pipe()
        rf = os.fdopen(r)
        try:
            gen = stream.leer_lineas_stdin(rf, intervalo=0.02)
            self.assertIsNone(next(gen))            # sin datos -> tick de reposo
            os.write(w, b"hola\n")
            got = None
            for _ in range(50):
                v = next(gen)
                if v is not None:
                    got = v; break
            self.assertEqual(got, "hola\n")
        finally:
            os.close(w); rf.close()


class TestCLI(unittest.TestCase):
    def test_parsear_args_defaults_y_flags(self):
        cfg = stream.parsear_args(["alerts.json"])
        self.assertEqual(cfg["ruta"], "alerts.json")
        self.assertFalse(cfg["con_llm"])
        self.assertEqual(cfg["ventana"], 5)
        cfg2 = stream.parsear_args(["-", "prototipo/perfiles/residencial.yml", "--con-llm",
                                    "--ventana-agrupacion", "20", "--sin-lab"])
        self.assertEqual(cfg2["ruta"], "-")
        self.assertTrue(cfg2["con_llm"])
        self.assertTrue(cfg2["sin_lab"])
        self.assertEqual(cfg2["ventana"], 20)
        self.assertTrue(cfg2["perfil"].endswith("residencial.yml"))

    def test_sin_llm_no_construye_justificador(self):
        self.assertIsNone(stream.construir_justificar_fn(False))

    def test_parsear_args_agente(self):
        self.assertFalse(stream.parsear_args(["alerts.json"])["agente"])
        self.assertTrue(stream.parsear_args(["-", "p.yml", "--agente"])["agente"])

    def test_sin_agente_no_construye_mitigar_fn(self):
        self.assertIsNone(stream.construir_mitigar_fn(False, {}, CAT, lambda *_: (0, "")))

    def test_banner_menciona_perfil_y_ruta(self):
        b = stream.banner({"perfil": "empresarial.yml", "ruta": "alerts.json", "con_llm": False,
                           "ventana": 5, "sin_lab": True})
        self.assertIn("empresarial", b)
        self.assertIn("alerts.json", b)
        self.assertIn("MDR", b)

    def test_resumen_final_cuenta(self):
        s = stream._resumen_final({"alertas": 4, "incidentes": 2, "aprobadas": 1, "rechazadas": 1,
                                   "reclasificadas": 0, "ejecutadas": 1})
        self.assertIn("2", s); self.assertIn("Incidentes", s)


class TestLecturaInteractiva(unittest.TestCase):
    def test_lee_del_tty_cuando_existe(self):
        # el analista responde por /dev/tty (teclado), no por stdin (el pipe de alertas)
        import builtins
        orig = builtins.open
        fake = io.StringIO("aprobar\n")
        builtins.open = lambda p, *a, **k: fake if p == "/dev/tty" else orig(p, *a, **k)
        try:
            leer = stream._leer_interactivo()
            self.assertEqual(leer("¿aprobar/rechazar? "), "aprobar")
        finally:
            builtins.open = orig

    def test_cae_a_input_si_no_hay_tty(self):
        import builtins
        orig = builtins.open
        def fake(p, *a, **k):
            if p == "/dev/tty":
                raise OSError("no tty")
            return orig(p, *a, **k)
        builtins.open = fake
        try:
            self.assertIs(stream._leer_interactivo(), input)   # sin terminal -> input estándar
        finally:
            builtins.open = orig


class TestStream(unittest.TestCase):
    def test_linea_decision_muestra_encaminamiento(self):
        from prototipo import stream
        d = {"clase": "amenaza_enrutada", "prioridad": 3, "confianza": 1.0,
             "accion_propuesta": None, "accion_final": None, "resultado_filtro": "sin_accion",
             "version_justificador": "plantilla-0", "ruta": "cola-appsec-banco"}
        linea = stream._linea_decision(d)
        self.assertIn("Enrutado a: cola-appsec-banco", linea)

    def test_linea_decision_muestra_la_consecuencia(self):
        d = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0,
             "accion_propuesta": "BLOQUEAR_IP", "accion_final": "BLOQUEAR_IP", "resultado_filtro": "veta",
             "version_justificador": "plantilla-0",
             "impacto_determinado": {"motivo": "bloquea a puesto (activo interno) · 0 servicios detenidos"}}
        self.assertIn("\n  Consecuencia: bloquea a puesto", stream._linea_decision(d))

    def test_linea_decision_prefija_vetada_si_no_hay_accion_final(self):   # F5
        d = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0,
             "accion_propuesta": "BLOQUEAR_IP", "accion_final": None, "resultado_filtro": "veta",
             "version_justificador": "plantilla-0",
             "impacto_determinado": {"motivo": "bloquea a puesto (activo interno) · 0 servicios detenidos"}}
        self.assertIn("\n  Consecuencia: (vetada) bloquea a puesto", stream._linea_decision(d))

    def test_linea_decision_muestra_el_filtro_legible(self):
        d = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0,
             "accion_propuesta": "BLOQUEAR_IP", "accion_final": "BLOQUEAR_IP", "resultado_filtro": "veta",
             "requiere_humano": True, "version_justificador": "plantilla-0"}
        linea = stream._linea_decision(d)
        self.assertIn("(filtro: retenida — espera tu aprobación)", linea)
        self.assertNotIn("filtro veta", linea)

    def test_mitigar_fn_pasa_los_hallazgos_al_agente(self):
        from unittest import mock
        from prototipo import agente_mitigacion as ag, justificador_llm, rag
        vistos = {}
        def falso_bucle(*a, **k):
            vistos.update(k)
            return {"resultado": "mitigado"}
        with mock.patch.object(rag, "cargar_indice", return_value=None), \
             mock.patch.object(rag, "embedder_por_defecto", return_value=None), \
             mock.patch.object(justificador_llm, "generador_por_defecto", return_value=lambda p: ""), \
             mock.patch.object(ag, "bucle_react", side_effect=falso_bucle):
            fn = stream.construir_mitigar_fn(True, y("perfil.yml"), CAT, lambda ip, c: (0, ""),
                                             escribir=lambda *a: None, hallazgos={"nodos": {}})
            fn({"clase": "vp_intento_acceso", "timestamp": "t"}, {"origen_ip": "203.0.113.9"}, lambda *_: "s")
        self.assertEqual(vistos["hallazgos"], {"nodos": {}})


if __name__ == "__main__":
    unittest.main()
