import os, unittest
from prototipo import impacto, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
PERFIL = {
    "ip_gestion": "172.20.20.4",
    "activos": {
        "objetivo-vuln": {"ip": "192.168.1.30", "funcion": "servidor con servicios expuestos",
                          "criticidad": "media", "servicios_prestados": [22, 80]},
        "puesto": {"ip": "192.168.1.10", "funcion": "puesto de trabajo de un empleado",
                   "criticidad": "media", "servicios_prestados": []},
        "borde": {"ip": "192.168.1.1", "funcion": "equipo de borde: enruta la LAN",
                  "criticidad": "media", "servicios_prestados": []},
    },
    "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                  "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
}
HALLAZGOS = {"nodos": {
    "objetivo-vuln": [{"puerto": 21, "servicio": "ftp", "estado": "open"},
                      {"puerto": 22, "servicio": "ssh", "estado": "open"},
                      {"puerto": 3306, "servicio": "mysql", "estado": "open"},
                      {"puerto": 8080, "servicio": "http-proxy", "estado": "closed"}],
    "puesto": []}}


class TestAccionesSobreIP(unittest.TestCase):
    def test_bloquear_un_activo_interno_nombra_a_quien(self):
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "192.168.1.10"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["nombre"], "puesto")
        self.assertEqual(d["nivel"], "localizado")            # un host interno no sube el nivel
        self.assertEqual(d["servicios_afectados"], [])
        self.assertEqual(d["motivo"],
                         "bloquea a puesto (activo interno: puesto de trabajo de un empleado) · 0 servicios detenidos")

    def test_bloquear_un_dispositivo_de_red_sube_a_alcanza_servicio(self):
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "192.168.1.1"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["tipo"], "dispositivo_red")
        self.assertEqual((d["nivel_catalogo"], d["nivel"]), ("localizado", "alcanza_servicio"))
        self.assertIn("todo lo que enruta", d["motivo"])

    def test_un_origen_externo_queda_como_en_el_catalogo(self):
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "203.0.113.9"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["tipo"], "desconocido")
        self.assertEqual(d["nivel"], "localizado")
        self.assertEqual(d["motivo"], "bloquea a 203.0.113.9 (origen no inventariado) · 0 servicios detenidos")

    def test_matar_conexion_tambien_resuelve_el_actor(self):
        d = impacto.determinar("MATAR_CONEXION", {"ip": "192.168.1.10"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["nombre"], "puesto")

    def test_nunca_por_debajo_del_catalogo(self):   # C2
        d = impacto.determinar("BLOQUEAR_IP_FIREWALL", {"ip": "203.0.113.9"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["nivel"], "alcanza_servicio")      # el catálogo ya dice alcanza_servicio

    def test_sin_ip_no_hay_actor(self):
        d = impacto.determinar("BLOQUEAR_IP", {}, "objetivo-vuln", PERFIL, CAT)
        self.assertIsNone(d["actor"])


class TestAccionesSobrePuerto(unittest.TestCase):
    def test_bloquear_puerto_declarado_y_abierto(self):
        d = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": 22}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        self.assertEqual(d["servicios_afectados"],
                         [{"puerto": 22, "servicio": "ssh", "declarado": True, "abierto": True}])
        self.assertEqual(d["nivel"], "alcanza_servicio")
        self.assertIsNone(d["actor"])

    def test_el_cruce_es_por_puerto_aunque_llegue_como_texto(self):
        d = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": "80"}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        s = d["servicios_afectados"][0]
        self.assertEqual((s["puerto"], s["declarado"], s["abierto"]), (80, True, False))

    def test_cerrar_servicio_empareja_por_nombre(self):
        d = impacto.determinar("CERRAR_SERVICIO", {"servicio": "mysql"}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        self.assertEqual(d["servicios_afectados"],
                         [{"puerto": 3306, "servicio": "mysql", "declarado": False, "abierto": True}])
        self.assertIn("no declarado", d["motivo"])

    def test_sin_hallazgos_no_se_inventa_el_estado(self):   # RNF-07
        d = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": 22}, "objetivo-vuln", PERFIL, CAT)
        self.assertIsNone(d["servicios_afectados"][0]["abierto"])
        self.assertIn("sin datos del auditor", d["motivo"])


class TestAccionesSobreNodo(unittest.TestCase):
    def test_aislar_nodo_da_el_radio_de_impacto(self):
        d = impacto.determinar("AISLAR_NODO", {"ip_nodo": "192.168.1.30"}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        # declarados ∪ abiertos; el 8080 está cerrado y no cuenta
        self.assertEqual([s["puerto"] for s in d["servicios_afectados"]], [21, 22, 80, 3306])
        self.assertIn("detendría 4 servicio(s) de objetivo-vuln (criticidad media)", d["motivo"])

    def test_nodo_sin_servicios_conocidos(self):
        d = impacto.determinar("AISLAR_NODO", {}, "puesto", PERFIL, CAT, HALLAZGOS)
        self.assertEqual(d["servicios_afectados"], [])
        self.assertIn("sin servicios conocidos", d["motivo"])


class TestObservacion(unittest.TestCase):
    def test_observar_no_tiene_impacto(self):
        d = impacto.determinar("OBS_CONEXIONES", {}, "objetivo-vuln", PERFIL, CAT, HALLAZGOS)
        self.assertEqual((d["nivel"], d["servicios_afectados"], d["actor"]), ("ninguno", [], None))


class TestPuertosAbiertos(unittest.TestCase):
    def test_no_escaneado_es_none_y_escaneado_sin_servicios_es_vacio(self):   # RNF-07
        self.assertIsNone(impacto.puertos_abiertos(HALLAZGOS, "iot"))
        self.assertEqual(impacto.puertos_abiertos(HALLAZGOS, "puesto"), {})
        self.assertIsNone(impacto.puertos_abiertos(None, "puesto"))

    def test_solo_los_abiertos_con_puerto(self):
        self.assertEqual(impacto.puertos_abiertos(HALLAZGOS, "objetivo-vuln"),
                         {21: "ftp", 22: "ssh", 3306: "mysql"})


if __name__ == "__main__":
    unittest.main()
