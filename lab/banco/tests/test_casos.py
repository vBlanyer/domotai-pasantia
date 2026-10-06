import unittest
from lab.banco import casos, pruebas


class TestCatalogo(unittest.TestCase):
    def test_cada_caso_tiene_id_titulo_y_nivel_valido(self):
        vistos = set()
        for c in casos.CASOS:
            self.assertTrue(c["id"] and c["titulo"], c)
            self.assertIn(c["nivel"], casos.NIVELES, c["id"])
            self.assertNotIn(c["id"], vistos, f"id duplicado: {c['id']}")
            vistos.add(c["id"])

    def test_los_casos_vivos_se_pueden_deshacer(self):
        for c in casos.CASOS:
            if c["nivel"] == "vivo":
                self.assertIn("deshacer", c, c["id"])

    def test_los_casos_vivos_solo_esperan_lo_que_se_comprueba(self):
        # Una clave de `esperado` que evaluar() no mira se da por buena en silencio.
        for c in casos.CASOS:
            if c["nivel"] == "vivo":
                self.assertLessEqual(set(c["esperado"]), set(pruebas.CLAVES_VIVO), c["id"])

    def test_todo_caso_tiene_esperado(self):
        for c in casos.CASOS:
            self.assertIn("esperado", c, c["id"])


class TestAtaqueAMedida(unittest.TestCase):
    def test_tipos_para_ofrece_web_solo_con_puerto_web(self):
        claves = lambda p: [t["clave"] for t in casos.tipos_para(p)]
        web = {t["clave"] for t in casos.TIPOS_ATAQUE if t["web"]}   # exploit_web, traversal, log4shell, cmdi
        self.assertFalse(web & set(claves([1521])))            # core-db (sql): sin web
        self.assertTrue(web <= set(claves([443, 80])))         # web-banking: todos los web
        self.assertTrue(web <= set(claves([8080])))            # atm
        for p in ([1521], [443], [], None):                    # ssh/recon/telnet, siempre
            self.assertEqual({"fuerza_bruta", "recon", "telnet"}, set(claves(p)) - web)

    def test_caso_a_medida_externo_ssh_trae_ataque_origen_y_deshacer(self):
        c = casos.caso_a_medida("fuerza_bruta", "internet", "198.51.100.10", "web-banking", "10.10.0.10")
        self.assertEqual(c["nivel"], "vivo")
        nodo, cmd = c["ataque"]
        self.assertEqual(nodo, "internet")                     # docker exec corre en el nodo origen
        self.assertIn("cliente@10.10.0.10", cmd)               # contra la IP objetivo
        self.assertEqual(c["origen"], "198.51.100.10")         # IP de origen (para rotación y aviso)
        self.assertEqual(c["destino_ip"], "10.10.0.10")
        self.assertIn(("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP"), c["deshacer"])
        self.assertIn("web-banking", c["titulo"])

    def test_caso_a_medida_origen_interno_sale_del_nodo_elegido(self):
        c = casos.caso_a_medida("fuerza_bruta", "taquilla", "10.200.0.10", "web-banking", "10.10.0.10")
        self.assertEqual(c["ataque"][0], "taquilla")
        self.assertEqual(c["origen"], "10.200.0.10")

    def test_caso_a_medida_web_usa_el_puerto_y_no_se_deshace(self):
        c = casos.caso_a_medida("exploit_web", "internet", "198.51.100.10", "web-banking", "10.10.0.10", puerto=443)
        self.assertIn(":443", c["ataque"][1])                  # al puerto web del objetivo
        self.assertEqual(c["deshacer"], [])                    # amenaza enrutada: el MDR no bloquea


class TestAtaquesWebRealistas(unittest.TestCase):
    def test_nuevos_tipos_web_en_el_catalogo(self):
        claves = {t["clave"] for t in casos.TIPOS_ATAQUE}
        self.assertTrue({"traversal", "log4shell", "cmdi"} <= claves, claves)
        for t in casos.TIPOS_ATAQUE:
            if t["clave"] in ("traversal", "log4shell", "cmdi"):
                self.assertTrue(t["web"] and not t["bloquea"], t["clave"])   # web, amenaza enrutada

    def test_builders_llevan_la_firma_y_el_destino(self):
        _, cmd = casos._exploit_log4shell("internet", "10.10.0.10", 443)
        self.assertIn("jndi", cmd); self.assertIn("10.10.0.10", cmd)
        _, cmd = casos._exploit_traversal("internet", "10.10.0.10", 443)
        self.assertIn("etc/passwd", cmd)
        _, cmd = casos._exploit_cmdi("internet", "10.10.0.10", 443)
        self.assertIn("cmd=", cmd)

    def test_sqli_sigue_igual(self):
        _, cmd = casos._exploit_web("internet", "10.10.0.10")
        self.assertIn("OR", cmd); self.assertIn("10.10.0.10", cmd)


if __name__ == "__main__":
    unittest.main()
