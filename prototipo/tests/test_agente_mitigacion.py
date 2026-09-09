import json, os, unittest, yaml
from prototipo import agente_mitigacion as ag, catalogo

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


if __name__ == "__main__":
    unittest.main()
