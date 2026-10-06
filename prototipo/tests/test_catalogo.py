import os, unittest
from prototipo import catalogo

RAIZ = os.path.join(os.path.dirname(__file__), "..", "catalogo.yml")

class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.cat = catalogo.cargar_catalogo(RAIZ)

    def test_carga_las_15_acciones(self):
        # 14 originales + BLOQUEAR_IP_FIREWALL (accion perimetral del agente de mitigacion)
        self.assertEqual(len(self.cat), 15)

    def test_impacto_de_bloquear_ip_firewall_es_alcanza_servicio(self):
        # el bloqueo perimetral tiene mayor radio de daño que el local (localizado)
        self.assertEqual(catalogo.impacto_de(self.cat, "BLOQUEAR_IP_FIREWALL"), "alcanza_servicio")

    def test_impacto_de_bloquear_ip_es_localizado(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "BLOQUEAR_IP"), "localizado")

    def test_impacto_de_bloquear_puerto_es_alcanza_servicio(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "BLOQUEAR_PUERTO"), "alcanza_servicio")

    def test_observacion_es_impacto_ninguno(self):
        self.assertEqual(catalogo.impacto_de(self.cat, "OBS_CONEXIONES"), "ninguno")


class TestMinimoPrivilegio(unittest.TestCase):
    CAT = {
        "BLOQUEAR_IP": {"comando": "iptables -A INPUT -s {ip} -j DROP", "reversion_cmd": "iptables -D INPUT -s {ip} -j DROP",
                        "verificacion": "iptables -L -n | grep {ip}"},
        "OBS_CONFIG": {"comando": "ip addr; ip route", "verificacion": "salida capturada"},
        "OBS_CAPTURA": {"comando": "timeout 10 tcpdump -c 100 -w -", "verificacion": "pcap devuelto"},
        "CERRAR_SERVICIO": {"comando": "service {servicio} stop", "reversion_cmd": "service {servicio} start",
                            "verificacion": "ss -lntu"},
        "OBS_ESCUCHA": {"comando": "ss -lntu", "verificacion": "salida capturada"},
    }

    def test_los_parametros_son_comodines_y_solo_el_primer_tramo_de_una_tuberia(self):
        cmds = catalogo.comandos_privilegiados(self.CAT)
        self.assertIn(("iptables", "-A INPUT -s * -j DROP"), cmds)
        self.assertIn(("iptables", "-L -n"), cmds)            # sin el '| grep'
        self.assertNotIn(("grep", "*"), cmds)

    def test_una_secuencia_con_punto_y_coma_da_dos_comandos(self):
        cmds = catalogo.comandos_privilegiados(self.CAT)
        self.assertIn(("ip", "addr"), cmds); self.assertIn(("ip", "route"), cmds)

    def test_las_verificaciones_descriptivas_no_son_comandos(self):
        binarios = {b for b, _ in catalogo.comandos_privilegiados(self.CAT)}
        self.assertNotIn("salida", binarios); self.assertNotIn("pcap", binarios)
        self.assertIn("ss", binarios)      # 'ss -lntu' si: es un binario que el catalogo ya usa

    def test_sudoers_usa_rutas_absolutas_y_reporta_lo_que_falta(self):
        texto, faltan = catalogo.sudoers(self.CAT, "triaje", {"iptables": "/sbin/iptables", "ss": "/sbin/ss"})
        self.assertIn("triaje ALL=(root) NOPASSWD: /sbin/iptables -A INPUT -s * -j DROP", texto)
        self.assertNotIn("timeout", texto)
        self.assertEqual(sorted(faltan), ["ip", "service", "timeout"])

    def test_el_catalogo_real_no_deja_pasar_texto_descriptivo(self):
        import os
        cat = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
        binarios = {b for b, _ in catalogo.comandos_privilegiados(cat)}
        for descriptivo in ("salida", "pcap", "diff", "config"):
            self.assertNotIn(descriptivo, binarios)
        self.assertTrue({"iptables", "ss", "tc", "service", "passwd"} <= binarios)

