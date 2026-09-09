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

    def test_degrada_si_no_hay_accion_valida(self):
        plan = ag.bucle_react(self._alerta(), "vp_intento_acceso", y_perfil(), CAT,
                              lambda ip, c: (0, ""), GeneradorGuion(["basura", "mas basura"]),
                              leer=lambda *_: "s", autonomo=True, escribir=lambda *_: None, max_pasos=2)
        self.assertTrue(plan["degradado"])
        self.assertEqual(plan["resultado"], "degradado")
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
