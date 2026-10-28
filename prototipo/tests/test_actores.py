import unittest
from prototipo.motor import actores

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

    def test_ipv4_mapeada_en_ipv6_coincide_con_el_activo(self):   # F3
        a = actores.quien_es("::ffff:192.168.1.10", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"]), ("activo_interno", "puesto"))

    def test_espacios_alrededor_de_la_ip_no_rompen_la_coincidencia(self):   # F3
        a = actores.quien_es(" 192.168.1.10 ", PERFIL)
        self.assertEqual((a["tipo"], a["nombre"]), ("activo_interno", "puesto"))
        self.assertEqual(a["ip"], " 192.168.1.10 ")   # el "ip" devuelto es la entrada tal cual


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

    def test_tercero_confiable_por_ip_exacta_y_por_rango(self):
        p = {"terceros_confiables": ["203.0.113.7", "198.51.100.0/24"]}
        self.assertTrue(actores.es_tercero_confiable("203.0.113.7", p))       # IP exacta
        self.assertTrue(actores.es_tercero_confiable("::ffff:203.0.113.7", p)) # forma mapeada
        self.assertTrue(actores.es_tercero_confiable("198.51.100.42", p))     # dentro del /24
        self.assertFalse(actores.es_tercero_confiable("8.8.8.8", p))          # fuera
        self.assertFalse(actores.es_tercero_confiable(None, p))
        self.assertFalse(actores.es_tercero_confiable("203.0.113.7", {}))     # sin lista
        # una errata (escalar donde va una lista) no debe lanzar: se trata como sin allowlist
        self.assertFalse(actores.es_tercero_confiable("1.2.3.4", {"terceros_confiables": 7}))
        self.assertFalse(actores.es_tercero_confiable("1.2.3.4", {"terceros_confiables": "1.2.3.4"}))


if __name__ == "__main__":
    unittest.main()


class TestEnriquecerOrigen(unittest.TestCase):
    """Enriquecimiento de la IP de origen para el visor (additivo): alcance, clasificación de IP,
    tercero de confianza y geolocalización (seam offline, hoy None)."""
    PERFIL = {**PERFIL, "terceros_confiables": ["203.0.113.200"]}

    def test_clasifica_la_ip_por_su_rango(self):
        self.assertEqual(actores.clasificar_ip("8.8.8.8"), "publica")
        self.assertEqual(actores.clasificar_ip("10.40.0.11"), "privada")
        self.assertEqual(actores.clasificar_ip("198.51.100.10"), "documentacion")
        self.assertEqual(actores.clasificar_ip("203.0.113.9"), "documentacion")
        self.assertEqual(actores.clasificar_ip("127.0.0.1"), "loopback")
        self.assertEqual(actores.clasificar_ip("nope"), "invalida")

    def test_un_externo_de_documentacion_no_geolocaliza(self):
        e = actores.enriquecer_origen("198.51.100.10", self.PERFIL)
        self.assertEqual(e["alcance"], "externo")
        self.assertFalse(e["inventariado"])
        self.assertEqual(e["clasificacion_ip"], "documentacion")
        self.assertFalse(e["geolocalizable"])
        self.assertIsNone(e["geo"])

    def test_clasifica_el_origen_con_quien_es(self):
        # Siempre resuelve el actor sobre la PROPIA IP de origen (no reutiliza el del motor): una IP
        # de las redes internas sale "interno/inventariado".
        e = actores.enriquecer_origen("10.0.0.5", self.PERFIL)
        self.assertEqual(e["alcance"], "interno")
        self.assertTrue(e["inventariado"])
        self.assertEqual(e["por"], "redes_internas")

    def test_marca_el_tercero_de_confianza_y_la_legitimidad(self):
        e = actores.enriquecer_origen("203.0.113.200", self.PERFIL, legitimo=True)
        self.assertTrue(e["tercero_confiable"])
        self.assertTrue(e["legitimo"])

    def test_una_ip_publica_en_la_tabla_se_geolocaliza(self):
        e = actores.enriquecer_origen("8.8.8.8", self.PERFIL)
        self.assertTrue(e["geolocalizable"])
        self.assertEqual((e["geo"] or {}).get("codigo"), "US")   # geo offline de la tabla de muestra

    def test_una_publica_fuera_de_la_tabla_es_geolocalizable_sin_geo(self):
        e = actores.enriquecer_origen("193.0.14.129", self.PERFIL)
        self.assertTrue(e["geolocalizable"])
        self.assertIsNone(e["geo"])             # pública pero no en la muestra

    def test_sin_ip_es_none(self):
        self.assertIsNone(actores.enriquecer_origen(None, self.PERFIL))


class TestGeolocalizar(unittest.TestCase):
    """Geolocalización OFFLINE con la tabla de muestra (sin dependencias ni egreso). Solo IPs públicas."""
    def test_ip_publica_en_la_tabla_da_pais(self):
        g = actores.geolocalizar("8.8.8.8")
        self.assertIsNotNone(g)
        self.assertEqual(g["codigo"], "US")
        self.assertIn("lat", g)

    def test_ip_de_documentacion_o_privada_no_geolocaliza(self):
        self.assertIsNone(actores.geolocalizar("198.51.100.10"))   # documentación
        self.assertIsNone(actores.geolocalizar("10.0.0.5"))        # privada

    def test_ip_publica_fuera_de_la_tabla_es_none(self):
        self.assertIsNone(actores.geolocalizar("193.0.14.129"))    # pública pero no en la muestra


class TestAsnYRdns(unittest.TestCase):
    """ASN offline (tabla de muestra, sin egreso) y rDNS OPT-IN (apagado por defecto: sin egreso)."""
    def test_asn_de_ip_publica_en_la_tabla(self):
        a = actores.asn_de("8.8.8.8")
        self.assertEqual(a["asn"], "AS15169")
        self.assertIn("Google", a["org"])

    def test_asn_no_aplica_a_interna_ni_documentacion(self):
        self.assertIsNone(actores.asn_de("10.0.0.5"))
        self.assertIsNone(actores.asn_de("198.51.100.10"))

    def test_enriquecer_incluye_asn(self):
        e = actores.enriquecer_origen("8.8.8.8", {})
        self.assertEqual((e["asn"] or {}).get("asn"), "AS15169")

    def test_rdns_apagado_por_defecto_no_resuelve(self):
        from unittest import mock
        with mock.patch.dict("os.environ", {}, clear=False):
            os_environ = __import__("os").environ
            os_environ.pop("TRIAJE_RDNS", None)
            # aunque pasemos un resolutor, sin el opt-in NO se consulta (sin egreso por defecto)
            self.assertIsNone(actores.rdns("8.8.8.8", resolutor=lambda ip: ("malo.example", [], [])))

    def test_rdns_optin_resuelve_solo_ip_publica(self):
        import os
        os.environ["TRIAJE_RDNS"] = "1"
        try:
            self.assertEqual(actores.rdns("8.8.8.8", resolutor=lambda ip: ("dns.google", [], [])), "dns.google")
            self.assertIsNone(actores.rdns("10.0.0.5", resolutor=lambda ip: ("x", [], [])))   # interna: no
        finally:
            del os.environ["TRIAJE_RDNS"]

    def test_rdns_no_cachea_fallos_transitorios(self):
        import os
        actores._RDNS_CACHE.pop("1.1.1.1", None)
        os.environ["TRIAJE_RDNS"] = "1"
        def rompe(ip):
            raise OSError("fallo transitorio de DNS")
        try:
            self.assertIsNone(actores.rdns("1.1.1.1", resolutor=rompe))   # falla -> None
            self.assertNotIn("1.1.1.1", actores._RDNS_CACHE)              # pero NO se cachea el None
            # tras recuperarse el DNS, el siguiente intento sí resuelve (no quedó condenada)
            self.assertEqual(actores.rdns("1.1.1.1", resolutor=lambda ip: ("one.one.one.one", [], [])), "one.one.one.one")
        finally:
            del os.environ["TRIAJE_RDNS"]
            actores._RDNS_CACHE.pop("1.1.1.1", None)

    def test_rdns_restaura_el_timeout_global_del_socket(self):
        import os, socket
        from unittest import mock
        actores._RDNS_CACHE.pop("9.9.9.9", None)
        previo = socket.getdefaulttimeout()
        os.environ["TRIAJE_RDNS"] = "1"
        try:
            # ruta por defecto (resolutor None): fija el timeout del socket y debe restaurarlo
            with mock.patch("socket.gethostbyaddr", side_effect=OSError("sin PTR")):
                self.assertIsNone(actores.rdns("9.9.9.9"))
            self.assertEqual(socket.getdefaulttimeout(), previo)         # no deja tocado el proceso
        finally:
            del os.environ["TRIAJE_RDNS"]
            socket.setdefaulttimeout(previo)
