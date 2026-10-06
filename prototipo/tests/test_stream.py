import contextlib, io, json, os, tempfile, time, unittest, yaml
from prototipo import stream, catalogo, lazo, tablero

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
    def test_avisa_si_la_ingesta_queda_en_silencio(self):
        t = [0.0]
        salidas = []
        def fuente():
            yield _linea_wazuh()        # una alerta: ultimo_evento = 0
            t[0] = 200.0                # pasa el tiempo
            yield None                  # reposo: 200 s de silencio -> avisa
            yield None                  # otro reposo: no repite el aviso
        stream.ejecutar(fuente(), hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(),
                        justificar_fn=None, ventana_agrupacion=0, salida_traza=io.StringIO(),
                        reloj=lambda: t[0], silencio_s=120,
                        escribir=lambda *a, **k: salidas.append(" ".join(str(x) for x in a)),
                        leer=lambda *_: "2")
        avisos = [s for s in salidas if "sin alertas" in s]
        self.assertEqual(len(avisos), 1)            # avisa una vez, no en cada reposo

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


class TestColaNoBloqueante(unittest.TestCase):
    def _linea_humana(self):
        d = json.loads(_linea_wazuh())
        d["predecoder"]["hostname"] = "fantasma"     # activo desconocido -> requiere humano
        return json.dumps(d)

    def _ejecutar(self, estado, buf):
        stream.ejecutar([self._linea_humana(), None], hallazgos=j("hallazgos.json"),
                        perfil=y("perfil.yml"), perfil_nombre="prueba", catalogo=CAT,
                        ejecutor=lazo._EjecutorAuto(), justificar_fn=None, ventana_agrupacion=0,
                        salida_traza=buf, escribir=lambda *a, **k: None, estado_web=estado)

    def test_encola_sin_bloquear_y_al_aprobar_ejecuta_y_traza(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)                  # NO bloquea (sin leer)
        cola = estado.decisiones_pendientes()
        self.assertEqual(len(cola), 1)
        self.assertEqual(buf.getvalue().strip(), "")  # aún no hay traza
        pid = cola[0]["id"]
        self.assertTrue(estado.resolver_decision(pid, "1"))   # aprobar
        self.assertEqual(estado.decisiones_pendientes(), [])  # sale de la cola
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["veredicto_humano"], "aprobar")
        self.assertIsNotNone(r["orden"])

    def test_reclasificar_es_en_dos_pasos(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)
        pid = estado.decisiones_pendientes()[0]["id"]
        self.assertTrue(estado.resolver_decision(pid, "3"))   # reclasificar -> submenú de clases
        p = estado.decisiones_pendientes()[0]
        self.assertTrue(p["esperando_clase"])
        self.assertTrue(p["clases"])
        self.assertTrue(estado.resolver_decision(pid, "1"))   # elige una clase -> finaliza
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["veredicto_humano"], "reclasificar")
        self.assertIsNone(r["orden"])                          # reclasificar no ejecuta

    def test_la_entrada_lleva_la_accion_final_para_el_visor(self):
        # Una decisión vetada (p. ej. el canal de gestión, RF-19) se encola SIN acción final: el visor
        # necesita saberlo para no prometer una contención que no se va a ejecutar.
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)
        p = estado.decisiones_pendientes()[0]
        self.assertIn("accion_final", tablero._vista_pendiente(p))
        self.assertTrue(estado.resolver_decision(p["id"], "2", paso=0))
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(p["accion_final"], r["accion_final"])

    def test_reclasificar_avanza_el_paso(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)
        pid = estado.decisiones_pendientes()[0]["id"]
        self.assertTrue(estado.resolver_decision(pid, "3", paso=0))
        self.assertEqual(estado.decisiones_pendientes()[0]["paso"], 1)

    def test_respuesta_al_menu_superado_se_rechaza(self):
        # Carrera: el analista pulsa «Reclasificar» y, antes de que el visor refresque, «Aprobar».
        # Ese "1" iba dirigido al menú de veredicto (paso 0); el backend ya está en el submenú de
        # clases (paso 1) y NO debe leerlo como índice de clase.
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)
        pid = estado.decisiones_pendientes()[0]["id"]
        self.assertTrue(estado.resolver_decision(pid, "3", paso=0))    # -> submenú de clases
        self.assertFalse(estado.resolver_decision(pid, "1", paso=0))   # menú viejo: rechazado
        self.assertEqual(len(estado.decisiones_pendientes()), 1)       # sigue en cola
        self.assertEqual(buf.getvalue().strip(), "")                   # nada trazado ni ejecutado
        self.assertTrue(estado.resolver_decision(pid, "1", paso=1))    # clase elegida en el paso vigente
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["veredicto_humano"], "reclasificar")

    def test_aprobar_con_el_paso_vigente_ejecuta(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)
        pid = estado.decisiones_pendientes()[0]["id"]
        self.assertTrue(estado.resolver_decision(pid, "1", paso=0))
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["veredicto_humano"], "aprobar")

    def test_rechazar_con_el_paso_vigente_retiene(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)
        pid = estado.decisiones_pendientes()[0]["id"]
        self.assertTrue(estado.resolver_decision(pid, "2", paso=0))
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["veredicto_humano"], "rechazar")
        self.assertIsNone(r["orden"])                          # rechazar no ejecuta

    def test_paso_no_numerico_se_rechaza(self):
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        self._ejecutar(estado, buf)
        pid = estado.decisiones_pendientes()[0]["id"]
        self.assertFalse(estado.resolver_decision(pid, "1", paso="x"))
        self.assertEqual(len(estado.decisiones_pendientes()), 1)


class TestActividadPropiaDelMDR(unittest.TestCase):
    """Para contener, el conector entra por SSH desde el nodo de gestión al activo, y Wazuh registra
    ese login (regla 5715) como una alerta más: cada contención generaba una decisión fantasma."""

    def _perfil(self):
        p = dict(y("perfil.yml"))
        p["activos"] = {**p["activos"], "objetivo-vuln": {**p["activos"]["objetivo-vuln"], "ip": "192.168.1.30"}}
        p["ip_gestion"] = "192.168.1.100"
        return p

    def _login_mdr(self, host="objetivo-vuln"):
        return json.dumps({
            "id": "e1", "rule": {"id": "5715", "level": 3, "description": "sshd: authentication success.",
                                 "groups": ["syslog", "sshd", "authentication_success"]},
            "predecoder": {"hostname": host, "program_name": "sshd"}, "data": {"srcip": "192.168.1.100"},
            "timestamp": "2026-08-31T00:00:05Z", "full_log": "Accepted password for msfadmin from 192.168.1.100"})

    def _correr(self, lineas):
        buf = io.StringIO()
        resumen = stream.ejecutar(lineas, hallazgos=j("hallazgos.json"), perfil=self._perfil(),
                                  perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(),
                                  justificar_fn=None, ventana_agrupacion=0, salida_traza=buf,
                                  escribir=lambda *a, **k: None, leer=lambda *_: "1")
        return resumen, [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]

    def test_el_login_del_mdr_tras_contener_es_actividad_propia(self):
        resumen, regs = self._correr([_linea_wazuh(), self._login_mdr(), None])
        self.assertIsNotNone(regs[0]["orden"])                            # hubo contención
        self.assertEqual([r.get("tipo") for r in regs], ["decision", "actividad_propia"])
        self.assertEqual(regs[1]["activo"], "objetivo-vuln")
        self.assertEqual(resumen["incidentes"], 1)                        # no cuenta como decisión
        self.assertEqual(resumen["propias"], 1)

    def test_sin_una_orden_previa_del_mdr_el_login_se_tria(self):
        _, regs = self._correr([self._login_mdr(), None])
        self.assertEqual(regs[0].get("tipo"), "decision")
        self.assertEqual(regs[0]["clase"], "no_soportada")

    def test_un_ataque_desde_el_nodo_de_gestion_no_se_oculta(self):
        # Fallos de login desde ip_gestion tras una contención: si mdr-siem estuviera comprometido,
        # sería una amenaza real, no un eco.
        _, regs = self._correr([_linea_wazuh(), _linea_wazuh(srcip="192.168.1.100"), None])
        self.assertNotIn("actividad_propia", [r.get("tipo") for r in regs])
        self.assertEqual(len(regs), 2)


class TestEscaladaEnModoWeb(unittest.TestCase):
    """Caso E1 del banco: la víctima no responde al MDR y la escalada al cortafuegos pide humano.
    En modo web no bloqueante eso congelaba el daemon entero (pregunta invisible y sin plazo)."""

    class HostCaido:
        def __init__(self): self.aplicado = set()
        def __call__(self, nodo_ip, cmd):
            if nodo_ip == "192.168.1.30":
                return (255, "Connection refused")
            if "grep" in cmd:
                return (0, "DROP") if nodo_ip in self.aplicado else (1, "")
            self.aplicado.add(nodo_ip); return (0, "")

    def _perfil(self):
        p = dict(y("perfil.yml"))
        p["topologia"] = {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                          "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}
        p["ip_gestion"] = "192.168.1.100"
        return p

    def _ejecutar(self, estado, buf, ej):
        def no_leas(*_):
            raise AssertionError("en modo web el lazo no debe bloquearse leyendo")
        stream.ejecutar([_linea_wazuh(), None], hallazgos=j("hallazgos.json"), perfil=self._perfil(),
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=ej, justificar_fn=None,
                        ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
                        leer=no_leas, estado_web=estado)

    def test_la_escalada_que_pide_humano_se_encola_sin_bloquear(self):
        estado, buf, ej = tablero.EstadoTablero(), io.StringIO(), self.HostCaido()
        self._ejecutar(estado, buf, ej)                          # vuelve: no se congela
        cola = estado.decisiones_pendientes()
        self.assertEqual(len(cola), 1)
        self.assertEqual(cola[0]["tipo"], "escalada")
        # El visor descarta las líneas «──…»: la acción y el dispositivo van en una línea «Acción:».
        self.assertTrue(any(l.startswith("Acción: BLOQUEAR_IP_FIREWALL en gateway") for l in cola[0]["lineas"]))
        self.assertFalse(any(l.startswith("──") for l in cola[0]["lineas"]))
        self.assertEqual(buf.getvalue().strip(), "")              # se traza al resolver
        self.assertEqual(ej.aplicado, set())

    def test_aprobar_la_escalada_contiene_en_el_cortafuegos_y_traza(self):
        estado, buf, ej = tablero.EstadoTablero(), io.StringIO(), self.HostCaido()
        self._ejecutar(estado, buf, ej)
        p = estado.decisiones_pendientes()[0]
        self.assertTrue(estado.resolver_decision(p["id"], "s", paso=p["paso"]))
        self.assertEqual(estado.decisiones_pendientes(), [])
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["escalada"]["resultado"], "mitigado")
        self.assertEqual(r["escalada"]["dispositivo_ejecutor"], "gateway")
        self.assertEqual(r["veredicto_escalada"], "aprobar")
        self.assertIn("192.168.1.1", ej.aplicado)

    def test_la_aprobacion_registra_quien_aprobo(self):
        estado, buf, ej = tablero.EstadoTablero(), io.StringIO(), self.HostCaido()
        self._ejecutar(estado, buf, ej)
        p = estado.decisiones_pendientes()[0]
        self.assertTrue(estado.resolver_decision(p["id"], "s", paso=p["paso"], operador="ana"))
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["veredicto_por"], "ana")           # no repudio: queda quién aprobó

    def test_rechazar_la_escalada_no_contiene_y_traza(self):
        estado, buf, ej = tablero.EstadoTablero(), io.StringIO(), self.HostCaido()
        self._ejecutar(estado, buf, ej)
        p = estado.decisiones_pendientes()[0]
        self.assertTrue(estado.resolver_decision(p["id"], "", paso=p["paso"]))
        r = json.loads([l for l in buf.getvalue().splitlines() if l.strip()][0])
        self.assertEqual(r["escalada"]["resultado"], "cancelado_por_humano")
        self.assertEqual(r["veredicto_escalada"], "rechazar")
        self.assertEqual(ej.aplicado, set())


class TestEscaladaConHumanoEnCadaSalto(unittest.TestCase):
    """En la web, cada salto que el perfil manda preguntar genera su tarjeta: ni aprobar el bloqueo
    en el host aprueba el del cortafuegos, ni aprobar un cortafuegos aprueba el siguiente."""

    class Nodos:
        def __init__(self, caidos): self.caidos, self.aplicado = set(caidos), set()
        def __call__(self, nodo_ip, cmd):
            if nodo_ip in self.caidos:
                return (255, "Connection refused")
            if "grep" in cmd:
                return (0, "DROP") if nodo_ip in self.aplicado else (1, "")
            self.aplicado.add(nodo_ip); return (0, "")

    def _perfil(self, host_humano=False):
        p = dict(y("perfil.yml"))
        p["topologia"] = {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                          "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1", "gateway": "edge"},
                          "edge": {"rol": "firewall_perimetral", "ip": "192.168.1.2"}}
        p["ip_gestion"] = "192.168.1.100"
        if host_humano:
            p["continuidad"] = {**p["continuidad"], "impacto_localizado": "humano_siempre"}
        return p

    def _ejecutar(self, estado, buf, ej, perfil):
        stream.ejecutar([_linea_wazuh(), None], hallazgos=j("hallazgos.json"), perfil=perfil,
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=ej, justificar_fn=None,
                        ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
                        leer=lambda *_: (_ for _ in ()).throw(AssertionError("no debe leer")),
                        estado_web=estado)

    def _resolver(self, estado, respuesta):
        p = estado.decisiones_pendientes()[0]
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            self.assertTrue(estado.resolver_decision(p["id"], respuesta, paso=p["paso"]))
        self.assertNotIn("Validación humana", salida.getvalue())     # nada se pregunta por stdout
        return estado.decisiones_pendientes()

    def test_aprobar_el_bloqueo_en_el_host_caido_encola_la_escalada(self):
        estado, buf, ej = tablero.EstadoTablero(), io.StringIO(), self.Nodos({"192.168.1.30"})
        self._ejecutar(estado, buf, ej, self._perfil(host_humano=True))
        self.assertEqual(estado.decisiones_pendientes()[0]["tipo"], "menu")
        cola = self._resolver(estado, "1")
        self.assertEqual([c["tipo"] for c in cola], ["escalada"])
        self.assertTrue(any("en gateway" in l for l in cola[0]["lineas"]))
        self.assertEqual(ej.aplicado, set())                         # el cortafuegos, intacto
        self.assertEqual(buf.getvalue().strip(), "")                 # se traza al resolver la escalada
        cola = self._resolver(estado, "s")
        r = json.loads(buf.getvalue().splitlines()[0])
        self.assertEqual(r["veredicto_humano"], "aprobar")
        self.assertEqual(r["escalada"]["dispositivo_ejecutor"], "gateway")

    def test_aprobar_un_cortafuegos_caido_no_aprueba_el_siguiente(self):
        estado, buf, ej = tablero.EstadoTablero(), io.StringIO(), self.Nodos({"192.168.1.30", "192.168.1.1"})
        self._ejecutar(estado, buf, ej, self._perfil())
        cola = estado.decisiones_pendientes()
        self.assertTrue(any("en gateway" in l for l in cola[0]["lineas"]))
        cola = self._resolver(estado, "s")
        self.assertEqual([c["tipo"] for c in cola], ["escalada"])
        self.assertTrue(any("en edge" in l for l in cola[0]["lineas"]), cola[0]["lineas"])
        self.assertEqual(ej.aplicado, set())
        self.assertEqual(buf.getvalue().strip(), "")
        self.assertEqual(self._resolver(estado, "s"), [])
        r = json.loads(buf.getvalue().splitlines()[0])
        self.assertEqual(r["escalada"]["resultado"], "mitigado")
        self.assertEqual(r["escalada"]["dispositivo_ejecutor"], "edge")
        self.assertEqual(ej.aplicado, {"192.168.1.2"})


class TestModoAgente(unittest.TestCase):
    def test_ejecutar_delega_al_mitigar_fn_y_cuenta(self):
        buf = io.StringIO()
        def mitigar(decision, alerta, leer, escribir=None, ejecutor=None):
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


class TestAgenteEscribeEnLaTarjeta(unittest.TestCase):
    def test_el_agente_usa_el_escribir_que_le_pasa_el_lazo(self):
        from unittest import mock
        from prototipo import agente_mitigacion as ag, justificador_llm, rag
        visto = {}
        with mock.patch.object(rag, "cargar_indice", return_value=None), \
             mock.patch.object(rag, "embedder_por_defecto", return_value=None), \
             mock.patch.object(justificador_llm, "generador_por_defecto", return_value=lambda p: ""), \
             mock.patch.object(ag, "bucle_react", lambda *a, **k: visto.update(k) or {}):
            fn = stream.construir_mitigar_fn(True, y("perfil.yml"), CAT, lambda *a: (0, ""))
            web = lambda *a: None
            fn({"clase": "vp_intento_acceso"}, {"origen_ip": "1.1.1.1"}, lambda *_: "s", escribir=web)
        self.assertIs(visto["escribir"], web)


class TestAgenteYActividadPropia(unittest.TestCase):
    def test_el_login_del_mdr_tras_contener_con_el_agente_es_actividad_propia(self):
        # El agente ejecutaba con el conector crudo de main: su SSH no quedaba anotado y el eco del
        # login de gestión se triaba como una alerta más (s2 no_soportada, 54 s de LLM en vivo).
        p = {**y("perfil.yml"), "ip_gestion": "10.100.0.10",
             "activos": {**y("perfil.yml")["activos"], "objetivo-vuln": {"ip": "192.168.1.30"}}}
        def mitigar(decision, alerta, leer, escribir=None, ejecutor=None):
            ejecutor("192.168.1.30", "iptables -A INPUT -s 1.1.1.1 -j DROP")
            return {"resultado": "mitigado", "escalado": False, "dispositivo_ejecutor": "objetivo-vuln"}
        eco = json.loads(_linea_wazuh("10.100.0.10", rule_id="5715"))
        eco["rule"]["groups"] = ["sshd", "authentication_success"]
        buf = io.StringIO()
        stream.ejecutar([_linea_wazuh("1.1.1.1"), json.dumps(eco)], hallazgos=j("hallazgos.json"), perfil=p,
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None,
                        ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
                        leer=lambda *_: "s", mitigar_fn=mitigar)
        tipos = [json.loads(l).get("tipo") for l in buf.getvalue().splitlines() if l.strip()]
        self.assertEqual(tipos, ["decision", "actividad_propia"])


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
        mitigar = lambda decision, alerta, leer, escribir=None, ejecutor=None: ag.bucle_react(
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
        reloj = iter([0, 0, 1, 2, 100]).__next__   # init + 1 por iteración; el 100 (None) vence ventana=10
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

    def _hasta_el_tick(self, gen, maximo=50):
        """Las líneas que rinde el lector antes de su primer tick de reposo (None)."""
        lineas = []
        for _ in range(maximo):
            v = next(gen)
            if v is None:
                if lineas:
                    return lineas
                continue
            lineas.append(v)
        return lineas

    def test_stdin_entrega_todas_las_lineas_de_una_rafaga_antes_del_reposo(self):
        # Wazuh escribe varias alertas de golpe. Con readline sobre un stdin con búfer, las líneas
        # que quedaban en el búfer de Python eran invisibles para select: salían minutos después,
        # con la siguiente alerta, y se agrupaban con otro ataque (tarjetas duplicadas y tardías).
        r, w = os.pipe()
        rf = os.fdopen(r)
        try:
            gen = stream.leer_lineas_stdin(rf, intervalo=0.02)
            os.write(w, b"a1\na2\na3\n")
            self.assertEqual(self._hasta_el_tick(gen), ["a1\n", "a2\n", "a3\n"])
        finally:
            os.close(w); rf.close()

    def test_stdin_recompone_una_linea_partida_entre_dos_escrituras(self):
        r, w = os.pipe()
        rf = os.fdopen(r)
        try:
            gen = stream.leer_lineas_stdin(rf, intervalo=0.02)
            os.write(w, b"a1\nmit")
            self.assertEqual(self._hasta_el_tick(gen), ["a1\n"])       # la mitad no sale sola
            os.write(w, b"ad\n")
            self.assertEqual(self._hasta_el_tick(gen), ["mitad\n"])
        finally:
            os.close(w); rf.close()

    def test_stdin_entrega_la_ultima_linea_sin_salto_al_cerrarse(self):
        r, w = os.pipe()
        rf = os.fdopen(r)
        try:
            gen = stream.leer_lineas_stdin(rf, intervalo=0.02)
            os.write(w, b"a1\nfinal")
            os.close(w); w = None
            self.assertEqual([v for v in gen if v is not None], ["a1\n", "final"])
        finally:
            if w is not None:
                os.close(w)
            rf.close()


class TestCLI(unittest.TestCase):
    def test_parsear_args_defaults_y_flags(self):
        cfg = stream.parsear_args(["alerts.json"])
        self.assertEqual(cfg["ruta"], "alerts.json")
        self.assertFalse(cfg["con_llm"])
        self.assertEqual(cfg["ventana"], 5)
        self.assertEqual(cfg["salida"], "run/trazas-stream.jsonl")  # runtime bajo run/, no en la raíz
        cfg2 = stream.parsear_args(["-", "prototipo/perfiles/residencial.yml", "--con-llm",
                                    "--ventana-agrupacion", "20", "--sin-lab"])
        self.assertEqual(cfg2["ruta"], "-")
        self.assertTrue(cfg2["con_llm"])
        self.assertTrue(cfg2["sin_lab"])
        self.assertEqual(cfg2["ventana"], 20)
        self.assertTrue(cfg2["perfil"].endswith("residencial.yml"))

    def test_sin_llm_no_construye_justificador(self):
        self.assertIsNone(stream.construir_justificar_fn(False))

    def test_con_llm_la_justificacion_es_estructurada(self):
        # En vivo se usa la salida JSON restringida: con el 1B, la libre caía casi siempre a plantilla.
        from unittest import mock
        from prototipo import justificador_llm, rag
        with mock.patch.object(rag, "cargar_indice", return_value={}), \
             mock.patch.object(rag, "embedder_por_defecto", return_value=None), \
             mock.patch.object(rag, "recuperar_fn_agentico", return_value=lambda a, c: []), \
             mock.patch.object(justificador_llm, "justificar_fn_rag") as fn_rag:
            stream.construir_justificar_fn(True, escribir=lambda *_: None)
        self.assertTrue(fn_rag.call_args.kwargs.get("estructurada"))

    def test_sin_servidor_del_modelo_se_arranca_en_modo_determinista(self):
        # B4: con --con-llm/--agente y sin servidor, cada alerta pagaba los plazos del modelo y el
        # banner anunciaba «LLM+RAG». Ahora se avisa y se arranca sin modelo.
        avisos = []
        cfg = stream.ajustar_modo_llm({"con_llm": True, "agente": True}, sondear=lambda url: False,
                                      escribir=avisos.append)
        self.assertEqual((cfg["con_llm"], cfg["agente"]), (False, False))
        self.assertTrue(any("modelo" in a for a in avisos))
        cfg = stream.ajustar_modo_llm({"con_llm": True, "agente": False}, sondear=lambda url: True,
                                      escribir=avisos.append)
        self.assertTrue(cfg["con_llm"])

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


class TestWeb(unittest.TestCase):
    def test_parsear_args_web(self):
        self.assertIs(stream.parsear_args(["-", "p"])["web"], False)
        cfg = stream.parsear_args(["-", "p", "--web"])
        self.assertTrue(cfg["web"])
        self.assertEqual(cfg["web_puerto"], 8787)
        self.assertEqual(stream.parsear_args(["-", "p", "--web", "9000"])["web_puerto"], 9000)

    def test_construir_web_liga_a_localhost_e_inyecta_lector(self):
        d = tempfile.mkdtemp()
        cfg = {"web": True, "web_puerto": 0, "salida": os.path.join(d, "t.jsonl")}
        perfil = {"activos": {"middleware": {"depende_de": ["core-db"]}}}
        estado, servidor, escribir_fn, leer_fn = stream.construir_web(cfg, perfil)
        try:
            self.assertEqual(servidor.server_address[0], "127.0.0.1")
            self.assertIsInstance(estado, tablero.EstadoTablero)
            self.assertIsInstance(leer_fn, tablero.LectorWeb)
            self.assertEqual(servidor.dependencias, {"middleware": ["core-db"]})
            with contextlib.redirect_stdout(io.StringIO()):
                escribir_fn("⚠ hola")               # imprime y acumula
            estado.registrar_pendiente("menu", "x")
            self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ hola"])
        finally:
            servidor.server_close()


class TestMemoriaDecisiones(unittest.TestCase):
    def _inc(self, ip="10.200.0.10", familia="acceso_credenciales", conteo=1, nivel=10):
        return {"clave": {"origen_ip": ip, "activo": "web", "servicio": "ssh", "familia": familia},
                "conteo": conteo, "representante": {"nivel_wazuh": nivel},
                "primera_ts": "2026-08-31T00:00:00Z", "ultima_ts": "2026-08-31T00:00:05Z"}

    RECHAZADA = {"id_decision": "s5", "veredicto_humano": "rechazar", "clase": "vp_intento_acceso"}

    def test_clave_nueva_no_decidida_y_tras_recordar_si(self):
        m = stream.MemoriaDecisiones()
        clave = stream._clave_supresion(self._inc())
        self.assertIsNone(m.buscar(clave))
        m.recordar(clave, self.RECHAZADA)
        self.assertEqual(m.buscar(clave)["id_decision"], "s5")

    def test_otra_familia_desde_la_misma_ip_no_esta_decidida(self):
        m = stream.MemoriaDecisiones()
        m.recordar(stream._clave_supresion(self._inc(familia="acceso_credenciales")), self.RECHAZADA)
        self.assertIsNone(m.buscar(stream._clave_supresion(self._inc(familia="reconocimiento"))))

    def test_registro_supresion_referencia_la_decision_y_cuenta(self):
        m = stream.MemoriaDecisiones()
        clave = stream._clave_supresion(self._inc())
        m.recordar(clave, self.RECHAZADA)
        reg = m.registro_supresion(self._inc(conteo=3), m.buscar(clave))
        self.assertEqual(reg["tipo"], "actividad_suprimida")
        self.assertEqual(reg["referencia"], "s5")
        self.assertEqual(reg["alertas_suprimidas"], 3)
        self.assertEqual(reg["clave"], {"origen_ip": "10.200.0.10", "activo": "web",
                                        "familia": "acceso_credenciales"})
        self.assertEqual(reg["veredicto_previo"], "rechazar")
        self.assertEqual(reg["desenlace"], "rechazada por el analista")
        self.assertEqual(m.suprimidas, 3)

    def test_ordenar_por_severidad_descendente(self):
        bajo, alto = self._inc(nivel=3), self._inc(nivel=12)
        self.assertEqual(stream._ordenar_por_severidad([bajo, alto]), [alto, bajo])


class TestSupresionEnVivo(unittest.TestCase):
    def _correr(self, lineas, **kw):
        buf = io.StringIO()
        resumen = stream.ejecutar(
            lineas, hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"), perfil_nombre="prueba",
            catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None, ventana_agrupacion=0,
            salida_traza=buf, escribir=lambda *a, **k: None, leer=lambda *_: "2", **kw)
        registros = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
        return resumen, registros

    def test_repeticion_se_suprime_cuenta_y_deja_resumen_en_la_traza(self):
        resumen, registros = self._correr([_linea_wazuh("1.1.1.1"), _linea_wazuh("1.1.1.1")])
        self.assertEqual(resumen["incidentes"], 1)                 # solo la primera decide
        self.assertEqual(resumen["suprimidas"], 1)                 # la segunda se cuenta
        sup = [r for r in registros if r.get("tipo") == "actividad_suprimida"]
        self.assertEqual(len(sup), 1)                              # y queda un resumen en la traza
        self.assertEqual(sup[0]["clave"]["origen_ip"], "1.1.1.1")
        from prototipo import traza as tm
        self.assertTrue(tm.verificar(registros)["valida"])         # la cadena sigue integra

    def test_otra_ip_no_se_suprime(self):
        resumen, _ = self._correr([_linea_wazuh("1.1.1.1"), _linea_wazuh("2.2.2.2")])
        self.assertEqual(resumen["incidentes"], 2)
        self.assertEqual(resumen["suprimidas"], 0)

    def test_sin_supresion_procesa_todo(self):
        resumen, _ = self._correr([_linea_wazuh("1.1.1.1"), _linea_wazuh("1.1.1.1")], suprimir=False)
        self.assertEqual(resumen["incidentes"], 2)
        self.assertEqual(resumen["suprimidas"], 0)

    def test_parsear_args_sin_supresion(self):
        self.assertFalse(stream.parsear_args(["-", "p"])["sin_supresion"])
        self.assertTrue(stream.parsear_args(["-", "p", "--sin-supresion"])["sin_supresion"])



def _linea(srcip="1.1.1.1", host="objetivo-vuln", seg=0):
    d = json.loads(_linea_wazuh(srcip))
    d["predecoder"]["hostname"] = host
    d["timestamp"] = f"2026-08-31T00:00:{seg:02d}Z"
    if srcip is None:
        del d["data"]["srcip"]
    return json.dumps(d)


class TestMemoriaDeSupresion(unittest.TestCase):
    """La supresión recuerda lo decidido por (origen, activo, familia), también lo que resuelve el
    analista en la web, y no congela una decisión que ya no es la que el motor tomaría."""
    HALLAZGOS = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"}],
                           "puesto": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}

    def _correr(self, fuente, perfil=None, ejecutor=None, leer=lambda *_: "2", estado_web=None,
                hallazgos=None):
        buf = io.StringIO()
        resumen = stream.ejecutar(
            fuente, hallazgos=hallazgos or self.HALLAZGOS, perfil=perfil or y("perfil.yml"),
            perfil_nombre="prueba", catalogo=CAT, ejecutor=ejecutor or lazo._EjecutorAuto(),
            justificar_fn=None, ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
            leer=leer, estado_web=estado_web)
        return resumen, [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]

    def _perfil_humano(self):
        p = dict(y("perfil.yml"))
        p["continuidad"] = {**p["continuidad"], "impacto_localizado": "humano_siempre"}
        return p

    def test_lo_rechazado_en_la_web_no_vuelve_a_pedir_tarjeta(self):
        estado = tablero.EstadoTablero()
        def fuente():
            yield _linea()
            p = estado.decisiones_pendientes()[0]
            estado.resolver_decision(p["id"], "2", paso=p["paso"])
            yield _linea(seg=5)
        resumen, regs = self._correr(fuente(), perfil=self._perfil_humano(), estado_web=estado)
        self.assertEqual(estado.decisiones_pendientes(), [])
        self.assertEqual((resumen["incidentes"], resumen["rechazadas"], resumen["suprimidas"]), (1, 1, 1))
        sup = [r for r in regs if r.get("tipo") == "actividad_suprimida"]
        self.assertEqual(sup[0]["clave"]["activo"], "objetivo-vuln")
        self.assertIn("rechazada", sup[0]["desenlace"])

    def test_en_terminal_da_lo_mismo_que_en_la_web(self):
        resumen, _ = self._correr([_linea(), _linea(seg=5)], perfil=self._perfil_humano())
        self.assertEqual((resumen["incidentes"], resumen["rechazadas"], resumen["suprimidas"]), (1, 1, 1))

    def test_el_mismo_atacante_contra_otro_activo_se_decide(self):
        resumen, regs = self._correr([_linea(host="objetivo-vuln"), _linea(host="puesto", seg=5)])
        self.assertEqual((resumen["incidentes"], resumen["suprimidas"]), (2, 0))

    def test_contenido_en_el_perimetro_cubre_a_los_demas_activos(self):
        p = dict(y("perfil.yml"))
        p["topologia"] = {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                          "puesto": {"rol": "host_victima", "ip": "192.168.1.31", "gateway": "gateway"},
                          "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}
        ej = TestEscaladaConHumanoEnCadaSalto.Nodos({"192.168.1.30"})
        resumen, regs = self._correr([_linea(host="objetivo-vuln"), _linea(host="puesto", seg=5)],
                                     perfil=p, ejecutor=ej, leer=lambda *_: "s")
        self.assertEqual(regs[0]["escalada"]["dispositivo_ejecutor"], "gateway")
        self.assertEqual((resumen["incidentes"], resumen["suprimidas"]), (1, 1))

    def test_una_rafaga_lenta_desde_un_origen_legitimo_acaba_decidiendose_como_amenaza(self):
        # La primera alerta sale FP (origen declarado); al pasar el umbral de ráfaga el motor ya no
        # la descarta: la supresión no puede congelar aquella primera decisión.
        p = {**y("perfil.yml"), "origenes_legitimos": ["1.1.1.1"], "rafaga": {"umbral": 9}}
        resumen, regs = self._correr([_linea(seg=2 * i) for i in range(12)], perfil=p)
        clases = [r.get("clase") for r in regs if r.get("tipo") == "decision"]
        self.assertEqual(clases[0], "fp_actividad_legitima")
        self.assertTrue(any(c and c.startswith("vp_") for c in clases), clases)

    def test_las_repeticiones_de_una_tarjeta_pendiente_no_vuelven_a_ejecutar(self):
        estado = tablero.EstadoTablero()
        p = {**y("perfil.yml"), "ip_gestion": "192.168.1.100",
             "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                           "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}}
        ej = TestEscaladaConHumanoEnCadaSalto.Nodos({"192.168.1.30"})
        llamadas = []
        def contado(ip, cmd):
            llamadas.append(cmd); return ej(ip, cmd)
        def fuente():
            yield _linea()
            self.antes = len(llamadas)
            for i in range(3):
                yield _linea(seg=5 + i)
        resumen, regs = self._correr(fuente(), perfil=p, ejecutor=contado, estado_web=estado)
        self.assertEqual(len(llamadas), self.antes)                   # 0 SSH extra contra el host caído
        cola = estado.decisiones_pendientes()
        self.assertEqual(len(cola), 1)
        self.assertEqual(resumen["suprimidas"], 3)
        self.assertEqual(len([r for r in regs if r.get("tipo") == "actividad_suprimida"]), 3)

    def test_sin_ip_de_origen_no_se_suprime(self):
        resumen, _ = self._correr([_linea(srcip=None), _linea(srcip=None, seg=5)])
        self.assertEqual((resumen["incidentes"], resumen["suprimidas"]), (2, 0))

    def test_una_contencion_fallida_no_silencia_al_atacante(self):
        cae = lambda ip, cmd: (255, "Connection refused")
        resumen, _ = self._correr([_linea(), _linea(seg=5)], ejecutor=cae)
        self.assertEqual((resumen["incidentes"], resumen["suprimidas"]), (2, 0))


class TestCierreConCtrlC(unittest.TestCase):
    """El daemon en vivo siempre se cierra con Ctrl+C: el resumen tenía que salir con las cifras de la
    sesión (salía a ceros) y lo que esperaba en la ventana de agrupación no podía perderse."""

    def _fuente(self):
        yield _linea("1.1.1.1")
        yield _linea("2.2.2.2", seg=1)
        raise KeyboardInterrupt

    def test_ejecutar_descarga_la_ventana_y_deja_el_resumen(self):
        buf, resumen = io.StringIO(), {}
        with self.assertRaises(KeyboardInterrupt):
            stream.ejecutar(self._fuente(), hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
                            perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(),
                            justificar_fn=None, ventana_agrupacion=5, salida_traza=buf,
                            escribir=lambda *a, **k: None, leer=lambda *_: "2",
                            reloj=lambda: 0, resumen=resumen)
        self.assertEqual((resumen["alertas"], resumen["incidentes"]), (2, 2))
        self.assertEqual(len([l for l in buf.getvalue().splitlines() if l.strip()]), 2)

    def test_main_imprime_el_resumen_real(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            salida = io.StringIO()
            with mock.patch.object(stream, "leer_lineas_fichero", lambda ruta: self._fuente()), \
                 contextlib.redirect_stdout(salida):
                stream.main(["alertas.json", os.path.join(FX, "perfil.yml"), os.path.join(FX, "hallazgos.json"),
                             "--sin-lab", "--ventana-agrupacion", "0", "--salida", os.path.join(d, "t.jsonl")])
        self.assertIn("Alertas vistas: 2 · Incidentes: 2", salida.getvalue())


class TestBarreraDeExcepciones(unittest.TestCase):
    """Una alerta rara o un ejecutor que lanza no pueden tumbar el daemon ni perder una decisión."""

    def _correr(self, lineas, ejecutor, estado_web=None):
        buf = io.StringIO()
        resumen = stream.ejecutar(lineas, hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
                                  perfil_nombre="prueba", catalogo=CAT, ejecutor=ejecutor, justificar_fn=None,
                                  ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
                                  leer=lambda *_: "2", estado_web=estado_web)
        return resumen, [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]

    def test_json_valido_pero_mal_tipado_se_descarta(self):
        raras = ["[1,2]", "null", '"x"', '{"rule": null}',
                 json.dumps({**json.loads(_linea_wazuh()), "data": [1]})]
        resumen, regs = self._correr(raras + [_linea_wazuh()], lazo._EjecutorAuto())
        self.assertEqual(resumen["incidentes"], 1)

    def test_un_ejecutor_que_lanza_deja_un_error_en_la_traza_y_el_daemon_sigue(self):
        def roto(ip, cmd):
            raise OSError("docker: no such file")
        resumen, regs = self._correr([_linea_wazuh("1.1.1.1"), _linea_wazuh("2.2.2.2")], roto)
        errores = [r for r in regs if r.get("tipo") == "error"]
        self.assertEqual(len(errores), 2)
        self.assertIn("docker", errores[0]["error"])
        self.assertEqual(errores[0]["origen_ip"], "1.1.1.1")
        from prototipo import traza as tm
        self.assertTrue(tm.verificar(regs)["valida"])

    def test_un_ejecutor_que_lanza_al_aprobar_en_la_web_deja_la_decision_en_la_traza(self):
        def roto(ip, cmd):
            raise OSError("docker: no such file")
        estado = tablero.EstadoTablero()
        # Activo sin postura del auditor (iot no escaneado) -> confianza 0.5 -> requiere humano; pero
        # con IP valida (IP_DE_NODO: 192.168.1.20), asi la orden supera el guard de nodo_ip y llega al
        # ejecutor (que lanza, para probar la barrera). «fantasma» no servia: sin IP -> guard lo rechaza.
        d = json.loads(_linea_wazuh()); d["predecoder"]["hostname"] = "iot"
        buf = io.StringIO()
        stream.ejecutar([json.dumps(d)], hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=roto, justificar_fn=None,
                        ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
                        estado_web=estado)
        p = estado.decisiones_pendientes()[0]
        self.assertTrue(estado.resolver_decision(p["id"], "1", paso=p["paso"]))
        r = json.loads(buf.getvalue().splitlines()[0])
        self.assertEqual(r["veredicto_humano"], "aprobar")
        self.assertFalse(r["ejecucion"]["exito"])
        self.assertIn("docker", r["ejecucion"]["error"])


class TestTrazaDelDaemon(unittest.TestCase):
    def test_el_registro_dice_cuando_se_decidio_y_que_agrupa(self):
        import datetime
        buf = io.StringIO()
        stream.ejecutar([_linea("1.1.1.1"), _linea("1.1.1.1", seg=3)], hallazgos=j("hallazgos.json"),
                        perfil=y("perfil.yml"), perfil_nombre="prueba", catalogo=CAT,
                        ejecutor=lazo._EjecutorAuto(), justificar_fn=None, ventana_agrupacion=5,
                        salida_traza=buf, escribir=lambda *a, **k: None, reloj=lambda: 0, suprimir=False)
        r = json.loads(buf.getvalue().splitlines()[0])
        self.assertIsNotNone(datetime.datetime.fromisoformat(r["decidido_en"]).tzinfo)
        self.assertEqual(r["incidente"]["conteo"], 2)
        self.assertTrue(r["incidente"]["primera_ts"].startswith("2026-08-31T00:00:00"))


class TestRevertirConElDaemonVivo(unittest.TestCase):
    def test_revertir_desde_la_cli_a_mitad_de_sesion_no_rompe_la_cadena(self):
        from unittest import mock
        from prototipo import revertir, traza as tm
        from prototipo.tests.iptables_falso import NodoIptables
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "t.jsonl")
            def fuente():
                yield _linea("1.1.1.1")
                with mock.patch("prototipo.conector.ejecutor_por_defecto",
                                lambda *a, **k: NodoIptables(drop_input=["1.1.1.1"])), mock.patch("builtins.print"):
                    self.assertEqual(revertir._main([ruta, "s1"]), 0)
                yield _linea("2.2.2.2", seg=5)
            with open(ruta, "a", encoding="utf-8") as f:
                stream.ejecutar(fuente(), hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
                                perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(),
                                justificar_fn=None, ventana_agrupacion=0, salida_traza=f, ruta_traza=ruta,
                                escribir=lambda *a, **k: None)
            regs = tm.leer_registros(ruta)
        self.assertEqual([r.get("tipo") for r in regs], ["decision", "reversion", "decision"])
        self.assertTrue(tm.verificar(regs)["valida"])


class TestRevisionFinal(unittest.TestCase):
    """Fallos del camino en vivo encontrados en la revisión final de la tanda 1."""

    def _perfil(self, host_humano=True, topologia=None):
        p = dict(y("perfil.yml"))
        p["ip_gestion"] = "192.168.1.100"
        p["topologia"] = topologia or {
            "objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
            "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1", "gateway": "edge"},
            "edge": {"rol": "firewall_perimetral", "ip": "192.168.1.2"}}
        if host_humano:
            p["continuidad"] = {**p["continuidad"], "impacto_localizado": "humano_siempre"}
        return p

    def test_una_repeticion_mientras_se_ejecuta_la_aprobacion_no_duplica_la_tarjeta(self):
        import threading
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        dentro, seguir = threading.Event(), threading.Event()
        base = lazo._EjecutorAuto()
        def lento(ip, cmd):
            if threading.current_thread() is not threading.main_thread() and not seguir.is_set():
                dentro.set(); seguir.wait(5)
            return base(ip, cmd)
        hilo = []
        def fuente():
            yield _linea()
            p = estado.decisiones_pendientes()[0]
            t = threading.Thread(target=estado.resolver_decision, args=(p["id"], "1"), kwargs={"paso": p["paso"]})
            t.start(); hilo.append(t)
            self.assertTrue(dentro.wait(5))            # el analista aprobó y el SSH está en curso
            yield _linea(seg=5)                        # llega una repetición del mismo ataque
            seguir.set(); t.join(5)
        resumen = stream.ejecutar(fuente(), hallazgos=j("hallazgos.json"), perfil=self._perfil(topologia={}),
                                  perfil_nombre="prueba", catalogo=CAT, ejecutor=lento, justificar_fn=None,
                                  ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None,
                                  estado_web=estado)
        regs = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
        self.assertEqual(estado.decisiones_pendientes(), [])          # sin tarjeta duplicada
        self.assertEqual(resumen["incidentes"], 1)
        self.assertEqual(sorted(r.get("tipo") for r in regs), ["actividad_suprimida", "decision"])

    def test_la_traza_conserva_los_saltos_de_una_escalada_diferida_varias_veces(self):
        # gateway aplica la regla pero no la verifica; edge contiene. La regla puesta en gateway tiene
        # que quedar en la traza (y su reversión), y el tiempo de espera cuenta desde la primera tarjeta.
        aplicado = set()
        def nodos(ip, cmd):
            if ip == "192.168.1.30": return (255, "Connection refused")
            if "grep" in cmd: return (0, "DROP") if (ip in aplicado and ip != "192.168.1.1") else (1, "")
            aplicado.add(ip); return (0, "")
        estado, buf = tablero.EstadoTablero(), io.StringIO()
        stream.ejecutar([_linea()], hallazgos=j("hallazgos.json"), perfil=self._perfil(host_humano=False),
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=nodos, justificar_fn=None,
                        ventana_agrupacion=0, salida_traza=buf, escribir=lambda *a, **k: None, estado_web=estado)
        primera = estado.decisiones_pendientes()[0]
        estado.resolver_decision(primera["id"], "s", paso=primera["paso"])
        segunda = estado.decisiones_pendientes()[0]
        estado.resolver_decision(segunda["id"], "s", paso=segunda["paso"])
        r = json.loads(buf.getvalue().splitlines()[0])
        esc = r["escalada"]
        self.assertEqual(esc["dispositivo_ejecutor"], "edge")
        self.assertIn("gateway", [p["dispositivo"] for p in esc["pasos"]])
        self.assertIn("iptables -D FORWARD -s 1.1.1.1 -j DROP", esc["reversiones"])
        self.assertEqual(len(esc["reversiones"]), 2)
        self.assertEqual(r["veredictos_escalada"], ["aprobar", "aprobar"])
        self.assertEqual(r["recibido_en"], primera["recibido_en"])

    def test_ctrl_c_a_mitad_de_un_lote_no_lo_vuelve_a_procesar(self):
        preguntas = []
        def leer(*_):
            preguntas.append(1); raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            stream.ejecutar([_linea("1.1.1.1"), _linea("2.2.2.2", seg=1)], hallazgos=j("hallazgos.json"),
                            perfil=self._perfil(topologia={}), perfil_nombre="prueba", catalogo=CAT,
                            ejecutor=lazo._EjecutorAuto(), justificar_fn=None, ventana_agrupacion=5,
                            salida_traza=io.StringIO(), escribir=lambda *a, **k: None, leer=leer, reloj=lambda: 0)
        self.assertEqual(len(preguntas), 1)

    def test_si_la_aprobacion_falla_la_amenaza_no_queda_como_cerrada(self):
        estado = tablero.EstadoTablero()
        def roto(ip, cmd):
            raise OSError("docker: no such file")
        def fuente():
            yield _linea()
            p = estado.decisiones_pendientes()[0]
            estado.resolver_decision(p["id"], "1", paso=p["paso"])
            yield _linea(seg=5)
        resumen = stream.ejecutar(fuente(), hallazgos=j("hallazgos.json"), perfil=self._perfil(topologia={}),
                                  perfil_nombre="prueba", catalogo=CAT, ejecutor=roto, justificar_fn=None,
                                  ventana_agrupacion=0, salida_traza=io.StringIO(), escribir=lambda *a, **k: None,
                                  estado_web=estado)
        self.assertEqual(resumen["suprimidas"], 0)
        self.assertEqual(len(estado.decisiones_pendientes()), 1)       # vuelve a pedir al analista

class TestAvisosRed(unittest.TestCase):
    def test_lineas_avisos_red(self):
        self.assertEqual(stream.lineas_avisos_red({"activos": {"a": {}}}), [])
        ls = stream.lineas_avisos_red({"activos": {"a": {}}, "red": "si"})
        self.assertEqual(len(ls), 1)
        self.assertTrue(ls[0].startswith("[aviso] perfil, sección red: "))


class TestAgenteEnModoWeb(unittest.TestCase):
    """Modo --agente web: cada incidente se resuelve en su hilo (el agente aprueba paso a paso), de
    modo que el daemon no se congela y varias tarjetas coexisten, cada una con su propio contexto."""

    def _mitigar(self, llamadas):
        def fn(decision, alerta, leer, escribir=print, ejecutor=None):
            escribir(f"🤖 agente contra {alerta.get('origen_ip')}")   # línea propia del incidente
            llamadas.append(alerta.get("origen_ip"))
            resp = leer("¿aprobar la ejecución? [s/N] ")              # bloquea hasta que el analista responde
            return {"pasos": [], "reversiones": [], "dispositivo_ejecutor": "objetivo-vuln",
                    "escalado": False, "degradado": False,
                    "resultado": "mitigado" if resp.lower().startswith("s") else "fallido"}
        return fn

    def _correr(self, estado, buf, mitigar_fn, lineas):
        stream.ejecutar(lineas, hallazgos=j("hallazgos.json"), perfil=y("perfil.yml"),
                        perfil_nombre="prueba", catalogo=CAT, ejecutor=lazo._EjecutorAuto(),
                        justificar_fn=None, ventana_agrupacion=0, salida_traza=buf,
                        escribir=lambda *a, **k: None, leer=lambda *_: "s", mitigar_fn=mitigar_fn,
                        lector_incidente=lambda b: tablero.LectorWeb(estado, lineas=b))

    def _esperar(self, cond, msg):
        for _ in range(400):
            if cond():
                return
            time.sleep(0.005)
        self.fail(msg)

    def test_no_bloquea_y_cada_tarjeta_trae_su_contexto(self):
        estado, buf, llamadas = tablero.EstadoTablero(), io.StringIO(), []
        self._correr(estado, buf, self._mitigar(llamadas),
                     [_linea_wazuh(srcip="192.168.1.10"), None, _linea_wazuh(srcip="192.168.1.11"), None])
        # ejecutar ya volvió (no se congeló) con los dos agentes esperando aprobación en su hilo
        self._esperar(lambda: len(estado.pendientes()) >= 2, "no llegaron las dos tarjetas")
        contextos = [" ".join(p["lineas"]) for p in estado.pendientes()]
        self.assertTrue(any("192.168.1.10" in c for c in contextos))
        self.assertTrue(any("192.168.1.11" in c for c in contextos))
        for c in contextos:                                  # cada tarjeta trae SOLO su incidente
            self.assertFalse("192.168.1.10" in c and "192.168.1.11" in c)
        for p in estado.pendientes():
            estado.resolver(p["id"], "s")
        self._esperar(lambda: len([l for l in buf.getvalue().splitlines() if l.strip()]) >= 2,
                      "no se trazaron las dos mitigaciones")
        trazas = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
        self.assertTrue(all(t["mitigacion_agente"]["resultado"] == "mitigado" for t in trazas))
        self.assertEqual(sorted(llamadas), ["192.168.1.10", "192.168.1.11"])

    def test_repeticion_en_vuelo_no_lanza_un_segundo_agente(self):
        estado, buf, llamadas = tablero.EstadoTablero(), io.StringIO(), []
        # el mismo (ip, activo, familia) dos veces: la segunda llega mientras el agente sigue pendiente
        self._correr(estado, buf, self._mitigar(llamadas),
                     [_linea_wazuh(srcip="192.168.1.10"), None, _linea_wazuh(srcip="192.168.1.10"), None])
        self._esperar(lambda: len(estado.pendientes()) >= 1, "no llegó la tarjeta del agente")
        time.sleep(0.05)                                     # margen por si apareciera una segunda
        self.assertEqual(len(estado.pendientes()), 1)        # un solo agente; la repetición se suprimió
        self.assertEqual(llamadas, ["192.168.1.10"])
        estado.resolver(estado.pendientes()[0]["id"], "s")


if __name__ == "__main__":
    unittest.main()
