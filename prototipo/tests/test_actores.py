import unittest
from prototipo import actores

PERFIL = {
    "ip_gestion": "172.20.20.4",
    "activos": {
        "puesto": {"ip": "192.168.1.10", "funcion": "puesto de trabajo de un empleado"},
        "borde": {"ip": "192.168.1.1", "funcion": "equipo de borde: enruta la LAN"},
    },
    "topologia": {
        "objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
        "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"},
    },
    "redes_internas": ["10.0.0.0/8"],
    "origenes_legitimos": ["198.51.100.7"],
}


class TestQuienEs(unittest.TestCase):
    def test_canal_de_gestion(self):
        a = actores.quien_es("172.20.20.4", PERFIL)
        self.assertEqual((a["tipo"], a["por"]), ("gestion", "ip_gestion"))

    def test_dispositivo_de_red_por_su_rol_en_la_topologia(self):
        a = actores.quien_es("192.168.1.1", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"]), ("dispositivo_red", "borde"))
        self.assertEqual(a["funcion"], "equipo de borde: enruta la LAN")   # la función sale del inventario

    def test_activo_del_inventario(self):
        a = actores.quien_es("192.168.1.10", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"]), ("activo_interno", "puesto", "inventario"))
        self.assertEqual(a["funcion"], "puesto de trabajo de un empleado")

    def test_otro_nodo_de_la_topologia_es_interno(self):
        a = actores.quien_es("192.168.1.30", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"]), ("activo_interno", "objetivo-vuln", "topologia"))

    def test_ip_dentro_de_las_redes_internas(self):
        a = actores.quien_es("10.40.0.99", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"]), ("activo_interno", None, "redes_internas"))

    def test_origen_legitimo_es_interno(self):
        a = actores.quien_es("198.51.100.7", PERFIL)
        self.assertEqual((a["tipo"], a["por"]), ("activo_interno", "origenes_legitimos"))

    def test_lo_no_declarado_es_desconocido(self):
        a = actores.quien_es("203.0.113.9", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"], a["por"], a["ip"]), ("desconocido", None, None, "203.0.113.9"))

    def test_la_gestion_gana_a_todo(self):
        # la IP de gestión también es un activo inventariado: manda la gestión (precedencia 1)
        p = {**PERFIL, "activos": {"auditor": {"ip": "172.20.20.4"}}}
        self.assertEqual(actores.quien_es("172.20.20.4", p)["tipo"], "gestion")

    def test_el_rol_de_red_gana_al_inventario(self):
        # borde está en el inventario Y es cortafuegos en la topología: es dispositivo de red
        self.assertEqual(actores.quien_es("192.168.1.1", PERFIL)["tipo"], "dispositivo_red")

    def test_perfil_sin_ips_resuelve_todo_a_desconocido(self):
        # las fixtures actuales no declaran IPs: su comportamiento no cambia
        p = {"activos": {"puesto": {"criticidad": "media"}}, "continuidad": {}}
        for ip in ("192.168.1.10", "192.168.1.1", "10.0.0.1"):
            self.assertEqual(actores.quien_es(ip, p)["tipo"], "desconocido")

    def test_sin_ip_no_hay_actor(self):
        self.assertIsNone(actores.quien_es(None, PERFIL))
        self.assertIsNone(actores.quien_es("", PERFIL))

    def test_una_ip_mal_formada_no_rompe_y_es_desconocida(self):
        self.assertEqual(actores.quien_es("no-es-una-ip", PERFIL)["tipo"], "desconocido")

    def test_un_cidr_invalido_en_el_perfil_es_error_de_configuracion(self):
        # tratarlo como «fuera de las redes internas» desprotegería esas IPs: debe verse
        with self.assertRaises(ValueError):
            actores.quien_es("10.0.0.1", {"redes_internas": ["10.0.0.0/33"]})


class TestPolitica(unittest.TestCase):
    def test_por_defecto_humano_siempre(self):   # C1
        self.assertEqual(actores.politica({}, "activo_interno"), "humano_siempre")
        self.assertEqual(actores.politica({"continuidad": {}}, "dispositivo_red"), "humano_siempre")

    def test_configurable_por_perfil(self):
        p = {"continuidad": {"actores": {"activo_interno": "automatica_si_confianza"}}}
        self.assertEqual(actores.politica(p, "activo_interno"), "automatica_si_confianza")
        self.assertEqual(actores.politica(p, "dispositivo_red"), "humano_siempre")

    def test_un_valor_desconocido_no_desprotege(self):
        # una errata en el perfil no puede volver automático el bloqueo de lo propio
        p = {"continuidad": {"actores": {"activo_interno": "automatico"}}}
        self.assertEqual(actores.politica(p, "activo_interno"), "humano_siempre")


if __name__ == "__main__":
    unittest.main()
