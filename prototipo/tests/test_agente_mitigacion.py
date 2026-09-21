import json, os, unittest, yaml
from prototipo import agente_mitigacion as ag, catalogo, lazo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))


def y_perfil():
    return {"topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                          "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
            "ip_gestion": "192.168.1.100"}


class TestTopologia(unittest.TestCase):
    def test_resolver_topologia_expone_roles_e_ip_gestion(self):
        topo = ag.resolver_topologia(y_perfil())
        self.assertEqual(topo["objetivo-vuln"]["rol"], "host_victima")
        self.assertEqual(topo["gateway"]["ip"], "192.168.1.1")
        self.assertEqual(topo["ip_gestion"], "192.168.1.100")

    def test_catalogo_tiene_accion_de_firewall(self):
        self.assertIn("BLOQUEAR_IP_FIREWALL", CAT)
        self.assertIn("FORWARD", CAT["BLOQUEAR_IP_FIREWALL"]["comando"])
        self.assertEqual(CAT["BLOQUEAR_IP_FIREWALL"]["impacto"], "alcanza_servicio")


class TestValidador(unittest.TestCase):
    def test_veta_plano_de_gestion(self):
        ok, motivo = ag.validar_comando("iptables -A INPUT -s 192.168.1.100 -j DROP", "192.168.1.100")
        self.assertFalse(ok); self.assertIn("gestion", motivo)

    def test_veta_destructivo_y_encadenado(self):
        self.assertFalse(ag.validar_comando("iptables -F", None)[0])
        self.assertFalse(ag.validar_comando("reboot", None)[0])
        self.assertFalse(ag.validar_comando("ls; rm -rf /", None)[0])

    def test_permite_comando_renderizado_del_catalogo(self):
        ok, _ = ag.validar_comando("iptables -A FORWARD -s 192.168.1.10 -j DROP", "192.168.1.100")
        self.assertTrue(ok)


class TestParser(unittest.TestCase):
    def test_extrae_action_json(self):
        t = 'Thought: intento el host\nAction: {"tool": "ejecutar_comando", "args": {"dispositivo": "objetivo-vuln", "accion": "bloquear_ip"}}'
        a = ag.parsear_accion(t)
        self.assertEqual(a["kind"], "action")
        self.assertEqual(a["tool"], "ejecutar_comando")
        self.assertEqual(a["args"]["dispositivo"], "objetivo-vuln")

    def test_extrae_final(self):
        a = ag.parsear_accion('Final: {"resultado": "mitigado", "dispositivo_ejecutor": "gateway"}')
        self.assertEqual(a["kind"], "final")
        self.assertEqual(a["resultado"], "mitigado")

    def test_ruido_sin_json_devuelve_none(self):
        self.assertIsNone(ag.parsear_accion("no hay ninguna accion aqui"))


class TestHerramientasReadOnly(unittest.TestCase):
    def test_consultar_topologia_lista_roles(self):
        topo = ag.resolver_topologia(y_perfil())
        obs = ag.herramienta_consultar_topologia(topo)
        self.assertIn("objetivo-vuln=host_victima", obs)
        self.assertIn("gateway=firewall_perimetral", obs)

    def test_verificar_bloqueado_segun_ejecutor(self):
        topo = ag.resolver_topologia(y_perfil())
        self.assertEqual(ag.herramienta_verificar_mitigacion(topo, CAT, lambda ip, c: (0, "DROP"),
                                                             "gateway", "192.168.1.10"), "bloqueado")
        self.assertEqual(ag.herramienta_verificar_mitigacion(topo, CAT, lambda ip, c: (1, ""),
                                                             "gateway", "192.168.1.10"), "activo")

    def test_consultar_conocimiento_resume_pasajes(self):
        from prototipo import rag
        emb = lambda textos: [[1.0 if "bloquear" in t.lower() else 0.0] for t in textos]
        indice = rag.indexar([{"id": "mapeo-acceso_credenciales", "tipo": "mapeo",
                               "titulo": "Mapeo acceso", "texto": "bloquear ip contramedida D3-ITF"}], emb)
        obs = ag.herramienta_consultar_conocimiento({"regla_id": "5760", "mitre": ["T1110.001"], "servicio": "ssh"},
                                                    indice, emb, generador=None, k=1)
        self.assertIn("Mapeo acceso", obs)

    def test_consultar_conocimiento_sin_indice_no_rompe(self):
        obs = ag.herramienta_consultar_conocimiento({"regla_id": "5760"}, None, None)
        self.assertIn("sin", obs.lower())


class TestEjecutarComando(unittest.TestCase):
    def _args(self, ejecutor, **kw):
        base = dict(topo=ag.resolver_topologia(y_perfil()), catalogo=CAT, ejecutor=ejecutor,
                    dispositivo="gateway", accion="bloquear_ip", ip="192.168.1.10",
                    ip_gestion="192.168.1.100", decision_id="d1", timestamp="t",
                    autonomo=True, leer=lambda *_: "s", escribir=lambda *_: None)
        base.update(kw); return base

    def test_ejecuta_en_firewall_y_registra_reversion(self):
        # _EjecutorAuto modela el estado: verif-antes "no está" (rc1), tras aplicar la re-verif da rc0.
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(lazo._EjecutorAuto()))
        self.assertTrue(obs.startswith("OK"))
        self.assertTrue(reg["exito"])
        self.assertEqual(reg["accion_id"], "BLOQUEAR_IP_FIREWALL")
        self.assertIn("FORWARD", reg["reversion_cmd"])

    def test_host_caido_devuelve_error(self):
        ej = lambda ip, cmd: (255, "connect: Connection refused")
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(ej, dispositivo="objetivo-vuln"))
        self.assertTrue(obs.startswith("Error"))
        self.assertFalse(reg["exito"])

    def test_no_autonomo_pide_aprobacion_y_rechazo_cancela(self):
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(lambda ip, c: (0, ""), autonomo=False,
                                                                leer=lambda *_: "n"))
        self.assertIn("Cancelado", obs)
        self.assertTrue(reg["cancelado"])

    def test_dispositivo_desconocido(self):
        obs, reg = ag.herramienta_ejecutar_comando(**self._args(lambda ip, c: (0, ""), dispositivo="marte"))
        self.assertTrue(obs.startswith("Error")); self.assertIsNone(reg)


class GeneradorGuion:
    """LLM falso: emite pasos ReAct prefijados, ignora el prompt."""
    def __init__(self, pasos): self.pasos, self.i = list(pasos), 0
    def __call__(self, prompt):
        if self.i >= len(self.pasos): return "ruido sin accion"
        p = self.pasos[self.i]; self.i += 1; return p

class EjecutorEscalado:
    """host víctima (.30) caído; firewall (.1) responde y modela el estado: verif-antes 'no está',
    tras aplicar la re-verif da 'está'."""
    def __init__(self): self.aplicado = set()
    def __call__(self, nodo_ip, cmd):
        if nodo_ip == "192.168.1.30":
            return (255, "connect to host 192.168.1.30 port 22: Connection refused")
        if "grep" in cmd:                                  # verificación
            return (0, "DROP") if nodo_ip in self.aplicado else (1, "")
        self.aplicado.add(nodo_ip)                          # aplicar
        return (0, "")


class TestBucleReact(unittest.TestCase):
    def _alerta(self):
        return {"id_alerta": "a1", "origen_ip": "192.168.1.10", "activo": "objetivo-vuln",
                "servicio": "ssh", "regla_id": "5760", "mitre": ["T1110.001"]}

    def test_escalado_host_caido_a_firewall(self):
        guion = [
            'Thought: intento el bloqueo local en el host victima.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"objetivo-vuln","accion":"bloquear_ip"}}',
            'Thought: el host no responde; escalo al firewall perimetral.\nAction: {"tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
            'Thought: verifico el corte en el firewall.\nAction: {"tool":"verificar_mitigacion","args":{"dispositivo":"gateway"}}',
            'Final: {"resultado":"mitigado","dispositivo_ejecutor":"gateway"}',
        ]
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              EjecutorEscalado(), GeneradorGuion(guion),
                              leer=lambda *_: "s", autonomo=True, escribir=lambda *_: None)
        self.assertTrue(plan["escalado"])
        self.assertEqual(plan["dispositivo_ejecutor"], "gateway")
        self.assertEqual(plan["resultado"], "mitigado")
        self.assertFalse(plan["degradado"])
        self.assertTrue(any("FORWARD" in r for r in plan["reversiones"]))   # RF-18

    def test_rechazo_humano_cancela(self):
        guion = ['Action: {"tool":"ejecutar_comando","args":{"dispositivo":"objetivo-vuln","accion":"bloquear_ip"}}']
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              lambda ip, c: (0, ""), GeneradorGuion(guion),
                              leer=lambda *_: "n", autonomo=False, escribir=lambda *_: None)
        self.assertEqual(plan["resultado"], "cancelado_por_humano")

    def test_si_el_modelo_no_da_accion_valida_se_contiene_igual(self):
        # Antes esto dejaba la amenaza SIN contener y solo anotaba lo que la politica habria
        # propuesto. Ahora cae a la escalada determinista: el plan sigue marcado como degradado
        # ---para que la traza distinga al modelo de la regla--- pero la amenaza queda contenida.
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              EjecutorEscalado(), GeneradorGuion(["basura", "mas basura"]),
                              leer=lambda *_: "s", autonomo=True, escribir=lambda *_: None, max_pasos=2)
        self.assertTrue(plan["degradado"])                             # lo decidio la regla, no el modelo
        self.assertEqual(plan["resultado"], "mitigado")                # pero se contuvo
        self.assertEqual(plan["dispositivo_ejecutor"], "gateway")      # escalando al perimetro
        self.assertEqual(plan["accion_determinista"], "BLOQUEAR_IP")   # politica.proponer

    def test_gestion_vetada_por_codigo(self):
        alerta = dict(self._alerta()); alerta["origen_ip"] = "192.168.1.100"   # = ip_gestion
        guion = ['Action: {"tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
                 'Final: {"resultado":"fallido"}']
        plan = ag.bucle_react(alerta, "vp_intento_acceso", y_perfil(), CAT,
                              lambda ip, c: (0, ""), GeneradorGuion(guion),
                              leer=lambda *_: "s", autonomo=True, escribir=lambda *_: None)
        self.assertIsNone(plan["dispositivo_ejecutor"])                 # nada se ejecutó
        self.assertTrue(any(p.get("observacion", "").startswith("Error") for p in plan["pasos"]))

    def test_agente_consulta_conocimiento_rag(self):
        from prototipo import rag
        emb = lambda textos: [[1.0 if "bloquear" in t.lower() else 0.0] for t in textos]
        indice = rag.indexar([{"id": "mapeo-acceso_credenciales", "tipo": "mapeo",
                               "titulo": "Mapeo acceso", "texto": "bloquear ip D3-ITF"}], emb)
        guion = ['Action: {"tool":"consultar_conocimiento","args":{}}',
                 'Final: {"resultado":"fallido"}']
        capturado = []
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              lambda ip, c: (0, ""), GeneradorGuion(guion), leer=lambda *_: "s",
                              autonomo=True, escribir=lambda *a, **k: capturado.append(" ".join(map(str, a))),
                              indice=indice, embedder=emb)
        self.assertTrue(any("Mapeo acceso" in p.get("observacion", "") for p in plan["pasos"]))


if __name__ == "__main__":
    unittest.main()


class TestEsquemaAccion(unittest.TestCase):
    def setUp(self):
        self.topo = ag.resolver_topologia(y_perfil())
        self.esq = ag.esquema_accion(CAT, self.topo)

    def test_los_dispositivos_salen_de_la_topologia(self):
        disp = self.esq["properties"]["args"]["properties"]["dispositivo"]["enum"]
        self.assertEqual(disp, ["gateway", "objetivo-vuln"])
        self.assertNotIn("ip_gestion", disp)     # no es un nodo: no tiene rol

    def test_las_acciones_salen_del_catalogo(self):
        self.assertEqual(self.esq["properties"]["args"]["properties"]["accion"]["enum"],
                         ["bloquear_ip"])

    def test_un_dispositivo_nuevo_aparece_solo(self):
        # El esquema se DERIVA: al crecer la topologia no hay que tocarlo a mano.
        topo = dict(self.topo, switch={"rol": "firewall_perimetral", "ip": "192.168.1.2"})
        disp = ag.esquema_accion(CAT, topo)["properties"]["args"]["properties"]["dispositivo"]["enum"]
        self.assertIn("switch", disp)

    def test_solo_admite_las_herramientas_conocidas(self):
        self.assertEqual(set(self.esq["properties"]["tool"]["enum"]), set(ag._HERRAMIENTAS))


class TestParserJSONDesnudo(unittest.TestCase):
    def test_acepta_json_sin_prefijo(self):
        # Es lo que produce la salida restringida por json-schema.
        a = ag.parsear_accion('{"kind": "action", "tool": "consultar_topologia", "args": {}}')
        self.assertEqual(a["kind"], "action")
        self.assertEqual(a["tool"], "consultar_topologia")

    def test_acepta_final_sin_prefijo(self):
        a = ag.parsear_accion('{"kind": "final", "resultado": "mitigado"}')
        self.assertEqual(a["kind"], "final")
        self.assertEqual(a["resultado"], "mitigado")

    def test_sigue_aceptando_el_prefijo_textual(self):
        a = ag.parsear_accion('Thought: pruebo\nAction: {"tool": "consultar_topologia", "args": {}}')
        self.assertEqual(a["kind"], "action")

    def test_json_sin_kind_no_se_confunde_con_accion(self):
        self.assertIsNone(ag.parsear_accion('{"algo": 1}'))


class TestGeneradorQueFalla(unittest.TestCase):
    def test_una_excepcion_del_modelo_no_tumba_la_mitigacion(self):
        def revienta(_prompt):
            raise RuntimeError("el servidor del modelo se cayo")
        plan = ag.bucle_react({"origen_ip": "192.168.1.10", "activo": "objetivo-vuln"},
                              "vp_intento_acceso", y_perfil(), CAT, EjecutorEscalado(),
                              revienta, autonomo=True, timestamp="t")
        self.assertTrue(plan["degradado"])       # degrada, no propaga la excepcion


class TestCadenaDeContencion(unittest.TestCase):
    def test_va_del_activo_al_perimetro(self):
        topo = ag.resolver_topologia(y_perfil())
        self.assertEqual(ag.cadena_de_contencion(topo, "objetivo-vuln"), ["objetivo-vuln", "gateway"])

    def test_si_el_activo_no_esta_contiene_en_el_perimetro(self):
        topo = ag.resolver_topologia(y_perfil())
        self.assertEqual(ag.cadena_de_contencion(topo, "camara-desconocida"), ["gateway"])

    def test_no_entra_en_bucle_si_la_topologia_se_referencia_a_si_misma(self):
        topo = {"a": {"rol": "host_victima", "ip": "1.1.1.1", "gateway": "b"},
                "b": {"rol": "firewall_perimetral", "ip": "1.1.1.2", "gateway": "a"}}
        self.assertEqual(ag.cadena_de_contencion(topo, "a"), ["a", "b"])


class TestEscaladaDeterminista(unittest.TestCase):
    def test_escala_al_firewall_cuando_la_victima_no_responde(self):
        # Mismo escenario que el agente ReAct, sin modelo: es lo que pidio el tutor industrial.
        plan = ag.escalar_determinista({"origen_ip": "192.168.1.10", "activo": "objetivo-vuln"},
                                       "vp_intento_acceso", y_perfil(), CAT, EjecutorEscalado(),
                                       autonomo=True, timestamp="t")
        self.assertEqual(plan["resultado"], "mitigado")
        self.assertEqual(plan["dispositivo_ejecutor"], "gateway")
        self.assertTrue(plan["escalado"])
        self.assertFalse(plan["degradado"])

    def test_registra_la_reversion_de_lo_aplicado(self):
        plan = ag.escalar_determinista({"origen_ip": "192.168.1.10", "activo": "objetivo-vuln"},
                                       "vp_intento_acceso", y_perfil(), CAT, EjecutorEscalado(),
                                       autonomo=True, timestamp="t")
        self.assertTrue(plan["reversiones"])                       # RF-18
        self.assertTrue(any("-D" in r for r in plan["reversiones"]))

    def test_para_en_el_primero_que_verifica(self):
        # Si la victima responde, no se toca el perimetro: minimo impacto.
        class TodoOk:
            def __init__(self): self.aplicado = set()
            def __call__(self, ip, cmd):
                if "grep" in cmd:
                    return (0, "DROP") if ip in self.aplicado else (1, "")
                self.aplicado.add(ip); return (0, "")
        plan = ag.escalar_determinista({"origen_ip": "192.168.1.10", "activo": "objetivo-vuln"},
                                       "vp_intento_acceso", y_perfil(), CAT, TodoOk(),
                                       autonomo=True, timestamp="t")
        self.assertEqual(plan["dispositivo_ejecutor"], "objetivo-vuln")
        self.assertFalse(plan["escalado"])

    def test_devuelve_el_mismo_contrato_que_el_agente(self):
        plan = ag.escalar_determinista({"origen_ip": "192.168.1.10", "activo": "objetivo-vuln"},
                                       "vp_intento_acceso", y_perfil(), CAT, EjecutorEscalado(),
                                       autonomo=True, timestamp="t")
        for clave in ("pasos", "reversiones", "dispositivo_ejecutor", "escalado", "resultado", "degradado"):
            self.assertIn(clave, plan)     # intercambiable como mitigar_fn


class TestFinalSinRespaldo(unittest.TestCase):
    def test_no_se_cree_un_exito_que_no_ejecuto_nada(self):
        # Con la salida restringida por json-schema, un modelo pequeno produce JSON impecable
        # y falso: declara 'mitigado' en el primer paso sin haber invocado ninguna herramienta.
        # El resultado lo decide el registro de lo ejecutado, no la afirmacion del modelo.
        guion = GeneradorGuion(['{"kind":"final","resultado":"mitigado","dispositivo_ejecutor":"gateway"}'])
        plan = ag.bucle_react({"origen_ip": "192.168.1.10", "activo": "objetivo-vuln"},
                              "vp_intento_acceso", y_perfil(), CAT, EjecutorEscalado(), guion,
                              autonomo=True, timestamp="t", escribir=lambda *a: None, max_pasos=2)
        # Cae a la escalada determinista, que si ejecuta y verifica.
        self.assertTrue(plan["degradado"])
        self.assertEqual(plan["dispositivo_ejecutor"], "gateway")   # real, no declarado

    def test_un_final_respaldado_por_ejecucion_si_vale(self):
        guion = GeneradorGuion([
            '{"kind":"action","tool":"ejecutar_comando","args":{"dispositivo":"gateway","accion":"bloquear_ip"}}',
            '{"kind":"final","resultado":"mitigado","dispositivo_ejecutor":"gateway"}'])
        plan = ag.bucle_react({"origen_ip": "192.168.1.10", "activo": "objetivo-vuln"},
                              "vp_intento_acceso", y_perfil(), CAT, EjecutorEscalado(), guion,
                              autonomo=True, timestamp="t", escribir=lambda *a: None, max_pasos=3)
        self.assertEqual(plan["resultado"], "mitigado")
        self.assertFalse(plan["degradado"])
        self.assertEqual(plan["dispositivo_ejecutor"], "gateway")


def y_perfil_empresarial():
    """Como empresarial.yml: localizado automatico con confianza alta; alcanza_servicio, humano."""
    return {**y_perfil(),
            "continuidad": {"impacto_ninguno": "automatica", "impacto_localizado": "automatica_si_confianza",
                            "impacto_alcanza_servicio": "humano_siempre", "reversibilidad_obligatoria": True,
                            "no_cortar_gestion": True}}


class TestEscaladaConPerfil(unittest.TestCase):
    ALERTA = {"id_alerta": "a1", "origen_ip": "192.168.1.10", "activo": "objetivo-vuln", "servicio": "ssh"}

    def test_el_salto_al_cortafuegos_pregunta_al_humano_porque_el_perfil_lo_exige(self):
        # BLOQUEAR_IP_FIREWALL alcanza servicio: humano_siempre. Sin siempre_humano, manda el perfil.
        preguntas = []
        plan = ag.escalar_determinista(self.ALERTA, "vp_intento_acceso", y_perfil_empresarial(), CAT,
                                       EjecutorEscalado(), leer=lambda p: (preguntas.append(p), "s")[1],
                                       escribir=lambda *a: None, siempre_humano=False, confianza=1.0)
        self.assertEqual(plan["resultado"], "mitigado")
        self.assertEqual(len(preguntas), 1)                 # solo el cortafuegos; el host fallo antes de preguntar? no:
        # el host (localizado, automatica_si_confianza, 1.0) NO pregunta; el cortafuegos si.

    def test_el_humano_puede_negar_el_salto_al_cortafuegos(self):
        plan = ag.escalar_determinista(self.ALERTA, "vp_intento_acceso", y_perfil_empresarial(), CAT,
                                       EjecutorEscalado(), leer=lambda p: "n", escribir=lambda *a: None,
                                       siempre_humano=False)
        self.assertEqual(plan["resultado"], "cancelado_por_humano")

    def test_un_veto_duro_del_perfil_salta_el_dispositivo(self):
        # Sin reversion definida en el cortafuegos y reversibilidad obligatoria: veto duro -> se salta.
        cat = {k: dict(v) for k, v in CAT.items()}
        cat["BLOQUEAR_IP_FIREWALL"] = {**cat["BLOQUEAR_IP_FIREWALL"], "reversion": "no_aplica"}
        plan = ag.escalar_determinista(self.ALERTA, "vp_intento_acceso", y_perfil_empresarial(), cat,
                                       EjecutorEscalado(), autonomo=True, siempre_humano=False)
        self.assertEqual(plan["resultado"], "fallido")
        self.assertNotIn("gateway", [d for d in plan["pasos"] if d.get("tipo") == "verificacion"])
        self.assertTrue(any("Vetado por el perfil" in p["observacion"] for p in plan["pasos"]))

    def test_desde_empieza_despues_del_dispositivo_ya_intentado(self):
        ej = EjecutorEscalado()
        plan = ag.escalar_determinista(self.ALERTA, "vp_intento_acceso", y_perfil(), CAT, ej,
                                       autonomo=True, desde="objetivo-vuln")
        dispositivos = [p["dispositivo"] for p in plan["pasos"] if p["tipo"] == "accion"]
        self.assertEqual(dispositivos, ["gateway"])
        self.assertEqual(plan["orden_efectiva"]["nodo_objetivo"], "gateway")
        self.assertEqual(plan["orden_efectiva"]["accion_id"], "BLOQUEAR_IP_FIREWALL")

    def test_el_agente_conserva_la_aprobacion_por_paso(self):
        # siempre_humano por defecto en la herramienta: el agente pregunta aunque el perfil automatice.
        preguntas = []
        topo = ag.resolver_topologia(y_perfil_empresarial())
        ag.herramienta_ejecutar_comando(topo, CAT, EjecutorEscalado(), "gateway", "bloquear_ip",
                                        "192.168.1.10", topo["ip_gestion"], "d", "t", False,
                                        lambda p: (preguntas.append(p), "s")[1], lambda *a: None,
                                        perfil=y_perfil_empresarial(), activo="objetivo-vuln", servicio="ssh",
                                        confianza=1.0)   # siempre_humano=True por defecto
        self.assertEqual(len(preguntas), 1)


def y_perfil_inventariado():
    return {**y_perfil(),
            "activos": {"objetivo-vuln": {"ip": "192.168.1.30", "funcion": "servidor con servicios expuestos",
                                          "criticidad": "media", "servicios_prestados": [22, 80]}}}


class TestVistaDelAgente(unittest.TestCase):
    """Spec de conciencia de impacto §4.5: el agente ve a quien toca, no solo su rol."""

    def test_la_topologia_se_enriquece_con_el_inventario(self):
        topo = ag.resolver_topologia(y_perfil_inventariado())
        self.assertEqual(topo["objetivo-vuln"]["funcion"], "servidor con servicios expuestos")
        self.assertEqual(topo["objetivo-vuln"]["servicios_prestados"], [22, 80])
        self.assertEqual(topo["objetivo-vuln"]["rol"], "host_victima")      # lo de siempre sigue

    def test_con_hallazgos_ve_los_servicios_abiertos(self):
        h = {"nodos": {"objetivo-vuln": [{"puerto": 21, "servicio": "ftp", "estado": "open"},
                                         {"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        topo = ag.resolver_topologia(y_perfil_inventariado(), h)
        self.assertEqual(topo["objetivo-vuln"]["servicios_abiertos"], [21, 22])

    def test_no_muta_el_perfil(self):
        p = y_perfil_inventariado()
        ag.resolver_topologia(p)
        self.assertNotIn("funcion", p["topologia"]["objetivo-vuln"])

    def test_consultar_topologia_describe_a_quien_toca(self):
        obs = ag.herramienta_consultar_topologia(ag.resolver_topologia(y_perfil_inventariado()))
        self.assertIn("objetivo-vuln=host_victima (servidor con servicios expuestos; criticidad media; "
                      "servicios declarados: 22, 80)", obs)
        self.assertIn("canal de gestion (intocable): 192.168.1.100", obs)

    def test_el_prompt_nombra_la_ip_de_gestion(self):
        prompt = ag.construir_prompt_sistema({"origen_ip": "203.0.113.9", "activo": "objetivo-vuln"},
                                             ag.resolver_topologia(y_perfil()))
        self.assertIn("nunca actues sobre el canal de gestion (192.168.1.100)", prompt)

    def test_sin_ip_de_gestion_conserva_la_consigna_generica(self):
        topo = {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30"}, "ip_gestion": None}
        self.assertIn("nunca toques el plano de gestion", ag.construir_prompt_sistema({}, topo))

    def test_el_agente_ve_los_servicios_abiertos_al_consultar_la_topologia(self):
        h = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        guion = GeneradorGuion(['Action: {"tool":"consultar_topologia","args":{}}'])
        plan = ag.bucle_react({"origen_ip": "203.0.113.9", "activo": "objetivo-vuln"}, "vp_intento_acceso",
                              y_perfil_inventariado(), CAT, EjecutorEscalado(), guion, autonomo=True,
                              timestamp="t", escribir=lambda *a: None, max_pasos=1, hallazgos=h)
        lectura = next(p for p in plan["pasos"] if p.get("tool") == "consultar_topologia")
        self.assertIn("abiertos segun el auditor: 22", lectura["observacion"])

