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

    def test_bloquear_la_ip_de_un_activo_del_que_otros_dependen_avisa_la_cascada(self):
        # K1: bloquear la IP del middleware (dependencia de web-banking/api-movil) en core-db lo aísla
        # de su dependencia y arrastra su cadena. Antes se decía "0 servicios detenidos" (fallo conocido).
        perfil = {"activos": {
            "core-db": {"ip": "10.50.0.10", "funcion": "base de datos", "criticidad": "critica", "servicios_prestados": [1521]},
            "middleware": {"ip": "10.40.0.10", "funcion": "middleware del core", "criticidad": "alta",
                           "servicios_prestados": [8443], "depende_de": ["core-db"]},
            "web-banking": {"ip": "10.10.0.10", "funcion": "portal", "criticidad": "alta",
                            "servicios_prestados": [443], "depende_de": ["middleware"]},
            "api-movil": {"ip": "10.20.0.10", "funcion": "api", "criticidad": "alta",
                          "servicios_prestados": [443], "depende_de": ["middleware"]}}}
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "10.40.0.10"}, "core-db", perfil, CAT)
        self.assertEqual(d["actor"]["nombre"], "middleware")
        self.assertEqual(d["activos_afectados_en_cascada"], ["api-movil", "middleware", "web-banking"])
        self.assertNotIn("0 servicios detenidos", d["motivo"])   # ya no miente
        self.assertIn("en cascada", d["motivo"])
        self.assertIn("web-banking", d["motivo"])

    def test_bloquear_un_activo_interno_hoja_no_inventa_cascada(self):
        # puesto es hoja: nadie depende de él -> sin cascada, sigue "0 servicios detenidos".
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "192.168.1.10"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["activos_afectados_en_cascada"], [])
        self.assertIn("0 servicios detenidos", d["motivo"])

    def test_bloquear_un_dispositivo_de_red_sube_a_alcanza_servicio(self):
        d = impacto.determinar("BLOQUEAR_IP", {"ip": "192.168.1.1"}, "objetivo-vuln", PERFIL, CAT)
        self.assertEqual(d["actor"]["tipo"], "dispositivo_red")
        self.assertEqual((d["nivel_catalogo"], d["nivel"]), ("localizado", "alcanza_servicio"))
        self.assertIn("todo lo que enruta", d["motivo"])
        # F4: bloquear un gateway no detiene "0 servicios" -- justo lo contrario de lo que dice
        # la frase que sigue ("puede cortar todo lo que enruta"); la contradiccion no debe verse.
        self.assertNotIn("0 servicios detenidos", d["motivo"])

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


    def test_el_actor_de_un_nodo_sale_de_su_ip(self):
        # Aislar un nodo también «bloquea a alguien»: el propio nodo. Sin actor, el veto de gestión
        # (RF-19) y la política de actores (C1) no lo veían.
        d = impacto.determinar("AISLAR_NODO", {}, "puesto", PERFIL, CAT, HALLAZGOS)
        self.assertEqual((d["actor"]["tipo"], d["actor"]["nombre"]), ("activo_interno", "puesto"))

    def test_ip_nodo_explicita_manda_sobre_el_inventario(self):
        d = impacto.determinar("REINICIAR_NODO", {"ip_nodo": "172.20.20.4"}, "auditor", PERFIL, CAT)
        self.assertEqual(d["actor"]["tipo"], "gestion")
        self.assertIn("canal de gestión del MDR", d["motivo"])

    def test_aislar_el_router_dice_que_corta_lo_que_enruta(self):
        d = impacto.determinar("AISLAR_NODO", {}, "borde", PERFIL, CAT, HALLAZGOS)
        self.assertEqual(d["actor"]["tipo"], "dispositivo_red")
        self.assertIn("puede cortar todo lo que enruta", d["motivo"])

    def test_nodo_sin_ip_declarada_no_tiene_actor(self):
        d = impacto.determinar("AISLAR_NODO", {}, "fantasma", PERFIL, CAT)
        self.assertIsNone(d["actor"])

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


class TestCascada(unittest.TestCase):
    def _perfil(self, deps):
        return {"activos": {n: {"depende_de": d} for n, d in deps.items()}}

    def test_cadena(self):
        p = self._perfil({"a": [], "b": ["a"], "c": ["b"]})
        self.assertEqual(impacto.afectados_en_cascada("a", p), ["b", "c"])

    def test_diamante_cuenta_cada_activo_una_vez(self):
        p = self._perfil({"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]})
        self.assertEqual(impacto.afectados_en_cascada("a", p), ["b", "c", "d"])

    def test_ciclo_termina_y_no_se_incluye_a_si_mismo(self):
        p = self._perfil({"a": ["b"], "b": ["a"]})
        self.assertEqual(impacto.afectados_en_cascada("a", p), ["b"])

    def test_sin_dependencias(self):
        self.assertEqual(impacto.afectados_en_cascada("a", {"activos": {"a": {}}}), [])

    def test_depende_de_escalar_se_normaliza_a_lista(self):
        # M1: en YAML, `depende_de: a` (sin corchetes) llega como str, no como lista de un elemento.
        p = {"activos": {"a": {}, "b": {"depende_de": "a"}}}
        self.assertEqual(impacto.afectados_en_cascada("a", p), ["b"])

    def test_depende_de_escalar_no_hace_falso_match_por_caracter(self):
        # Sin normalizar, iterar la cadena "middleware" caracter a caracter emparejaria de más
        # con un activo llamado "m" (dependientes.setdefault('m', ...)): falso positivo.
        p = {"activos": {"m": {}, "x": {"depende_de": "middleware"}}}
        self.assertEqual(impacto.afectados_en_cascada("m", p), [])

    def test_determinar_la_incluye_para_nodos_y_servicios_no_para_ips(self):
        p = {"activos": {"db": {"servicios_prestados": [5432]}, "app": {"depende_de": ["db"]}}}
        nodo = impacto.determinar("AISLAR_NODO", {}, "db", p, CAT)
        self.assertEqual(nodo["activos_afectados_en_cascada"], ["app"])
        self.assertIn("en cascada: app", nodo["motivo"])
        puerto = impacto.determinar("BLOQUEAR_PUERTO", {"puerto": 5432}, "db", p, CAT)
        self.assertEqual(puerto["activos_afectados_en_cascada"], ["app"])
        ip = impacto.determinar("BLOQUEAR_IP", {"ip": "203.0.113.9"}, "db", p, CAT)
        self.assertEqual(ip["activos_afectados_en_cascada"], [])


if __name__ == "__main__":
    unittest.main()
