import contextlib
import io
import subprocess
import unittest
from lab.banco import casos, demo, red


class TestDemo(unittest.TestCase):
    def _fake(self):
        llamadas = []
        def ejecutar(args, **kw):
            llamadas.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")
        return llamadas, ejecutar

    def test_casos_vivos_son_los_atacables(self):
        ids = [c["id"] for c in demo.casos_vivos()]
        self.assertEqual(ids, ["CASCADA", "D1", "A1", "K1", "E1", "RECON", "EXPLOIT", "TELNET"])
        self.assertTrue(all(c.get("ataque") or c.get("preparar") for c in demo.casos_vivos()))

    def test_menu_numera_los_casos(self):
        m = demo.menu(demo.casos_vivos())
        self.assertIn("1. CASCADA", m)
        self.assertIn("5. E1", m)

    def test_lanzar_ejecuta_preparar_y_luego_ataque_en_orden(self):
        llamadas, ejecutar = self._fake()
        caso = {"preparar": [("web-banking", "echo prep")], "ataque": ("internet", "echo atk")}
        demo.lanzar(caso, ejecutar=ejecutar)
        self.assertEqual(llamadas[0], ["docker", "exec", "clab-banco-web-banking", "sh", "-c", "echo prep"])
        self.assertEqual(llamadas[1], ["docker", "exec", "clab-banco-internet", "sh", "-c", "echo atk"])

    def test_deshacer_maneja_rearrancar_y_comandos(self):
        llamadas, ejecutar = self._fake()
        caso = {"deshacer": [("core-db", "REARRANCAR"), ("web-banking", "echo undo")]}
        demo.deshacer(caso, ejecutar=ejecutar)
        self.assertIn("-d", llamadas[0])                       # el rearranque va en segundo plano
        self.assertEqual(llamadas[1][-1], "echo undo")

    def test_ip_rotada_rota_en_la_misma_subred_sin_pisar_gateway_ni_nodo(self):
        self.assertEqual(demo.ip_rotada("198.51.100.10", 0), "198.51.100.11")
        self.assertEqual(demo.ip_rotada("198.51.100.10", 1), "198.51.100.12")
        self.assertEqual(demo.ip_rotada("10.200.0.10", 0), "10.200.0.11")
        # nunca la .1 (gateway) ni la .10 (nodo base), siempre en la /24 de la base
        for n in range(300):
            ip = demo.ip_rotada("198.51.100.10", n)
            self.assertTrue(ip.startswith("198.51.100."))
            ultimo = int(ip.rsplit(".", 1)[1])
            self.assertNotIn(ultimo, (0, 1, 10, 255))

    def test_ataque_rotado_agrega_alias_y_ata_el_ssh(self):
        caso = {"ataque": casos._fuerza_bruta("internet", "10.10.0.10"), "origen": "198.51.100.10",
                "destino_ip": "10.10.0.10"}
        nodo, cmd = demo.ataque_rotado(caso, "198.51.100.11")
        self.assertEqual(nodo, "internet")
        self.assertIn("ip addr add 198.51.100.11/24 dev eth1", cmd)  # alias en la interfaz de datos
        self.assertIn("ssh -b 198.51.100.11", cmd)                   # cliente atado a la IP nueva
        self.assertIn("cliente@10.10.0.10", cmd)                     # mismo destino

    def test_lanzar_con_src_ip_usa_ataque_rotado(self):
        llamadas, ejecutar = self._fake()
        caso = {"ataque": casos._fuerza_bruta("internet", "10.10.0.10"), "origen": "198.51.100.10",
                "destino_ip": "10.10.0.10"}
        demo.lanzar(caso, ejecutar=ejecutar, src_ip="198.51.100.11")
        self.assertIn("ssh -b 198.51.100.11", llamadas[0][-1])
        self.assertNotEqual(llamadas[0][-1], "base")                 # no usó el comando base

    def test_lanzar_sin_src_ip_no_cambia(self):
        llamadas, ejecutar = self._fake()
        caso = {"ataque": ("internet", "base")}
        demo.lanzar(caso, ejecutar=ejecutar)
        self.assertEqual(llamadas[0][-1], "base")                    # comportamiento actual intacto

    def test_deshacer_rotado_sustituye_la_ip_base_por_la_rotada(self):
        llamadas, ejecutar = self._fake()
        caso = {"origen": "198.51.100.10",
                "deshacer": [("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP")]}
        demo.deshacer(caso, ejecutar=ejecutar, src_ip="198.51.100.11")
        self.assertEqual(llamadas[0][-1], "iptables -D INPUT -s 198.51.100.11 -j DROP")

    def test_main_con_rotacion_lanza_d1_desde_ip_nueva(self):
        # Enciende la rotación (r), lanza D1 (2), no deshace (N), sale (0).
        llamadas, ejecutar = self._fake()
        respuestas = iter(["r", "2", "N", "0"])
        demo.main(leer=lambda _="": next(respuestas), ejecutar=ejecutar, dormir=lambda _: None)
        ataques = [a[-1] for a in llamadas if "sshpass" in a[-1]]
        self.assertTrue(ataques, "D1 debía lanzar un ataque")
        self.assertIn("ssh -b 198.51.100.11", ataques[0])           # primera IP rotada de la /24 externa
        self.assertIn("ip addr add 198.51.100.11/24 dev eth1", ataques[0])


    def _caso(self, id_):
        return next(c for c in demo.casos_vivos() if c["id"] == id_)

    def test_la_rotacion_ata_el_propio_ataque_del_caso(self):
        # Antes solo sabía rotar una fuerza bruta: RECON (nc), EXPLOIT (curl) y TELNET (nc) no rotaban
        # y la tecla r se ignoraba en silencio, atacando desde una IP ya bloqueada.
        esperado = {"D1": "ssh -b 198.51.100.11", "RECON": "nc -s 198.51.100.11",
                    "EXPLOIT": "curl --interface 198.51.100.11", "TELNET": "nc -s 198.51.100.11"}
        for id_, atado in esperado.items():
            caso = self._caso(id_)
            self.assertTrue(demo.rotable(caso), id_)
            nodo, cmd = demo.ataque_rotado(caso, "198.51.100.11")
            self.assertEqual(nodo, caso["ataque"][0])
            self.assertIn("ip addr add 198.51.100.11/24 dev eth1", cmd, id_)
            self.assertIn(atado, cmd, id_)

    def test_todos_los_casos_que_atacan_son_rotables(self):
        self.assertTrue(all(demo.rotable(c) for c in demo.casos_vivos() if c.get("ataque")))

    def _main(self, respuestas):
        llamadas, ejecutar = self._fake()
        salida = io.StringIO()
        r = iter(respuestas)
        with contextlib.redirect_stdout(salida):
            demo.main(leer=lambda _="": next(r), ejecutar=ejecutar, dormir=lambda _: None)
        return salida.getvalue()

    def test_avisa_si_un_caso_reusa_un_origen_que_quedo_sin_deshacer(self):
        # D1 (2) sin deshacer y luego RECON (6) desde la misma IP: el MDR ya la bloqueó.
        out = self._main(["2", "N", "6", "N", "0"])
        self.assertIn("198.51.100.10 ya atacó en D1 sin deshacer", out)

    def test_no_avisa_si_el_caso_anterior_se_deshizo(self):
        out = self._main(["2", "s", "6", "N", "0"])
        self.assertNotIn("ya atacó en", out)

    def test_no_avisa_si_se_rota_la_ip(self):
        out = self._main(["2", "N", "r", "6", "N", "0"])
        self.assertNotIn("ya atacó en", out)

    def test_la_preparacion_de_e1_no_se_acumula(self):
        # Cada lanzamiento insertaba otra regla; si no se deshacía, quedaban varias.
        _, cmd = self._caso("E1")["preparar"][0]
        self.assertIn("iptables -C INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP", cmd)
        self.assertLess(cmd.index("-C INPUT"), cmd.index("-I INPUT"))

    # --- Ataque a medida: elegir objetivo, servicio y origen ---
    def _resp(self, respuestas):
        r = iter(respuestas)
        return lambda _="": next(r)

    def test_elegir_a_medida_externo(self):
        objetivos = sorted(red.NODOS)
        i_wb = objetivos.index("web-banking") + 1
        # objetivo web-banking -> tipo 1 (fuerza bruta SSH) -> origen 1 (internet)
        caso = demo.elegir_a_medida(self._resp([str(i_wb), "1", "1"]))
        self.assertEqual(caso["ataque"][0], "internet")
        self.assertEqual(caso["origen"], "198.51.100.10")
        self.assertEqual(caso["destino_ip"], "10.10.0.10")
        self.assertIn("cliente@10.10.0.10", caso["ataque"][1])
        self.assertIn("web-banking", caso["titulo"])

    def test_elegir_a_medida_origen_interno(self):
        objetivos = sorted(red.NODOS)
        i_wb = objetivos.index("web-banking") + 1
        origenes = ["internet"] + [n for n in objetivos if n != "web-banking"]
        i_taq = origenes.index("taquilla") + 1
        caso = demo.elegir_a_medida(self._resp([str(i_wb), "1", str(i_taq)]))
        self.assertEqual(caso["ataque"][0], "taquilla")            # el docker exec corre en taquilla
        self.assertEqual(caso["origen"], "10.200.0.10")            # su IP es el origen

    def test_elegir_a_medida_oculta_web_en_un_objetivo_sin_servicio_http(self):
        objetivos = sorted(red.NODOS)
        i_cdb = objetivos.index("core-db") + 1                     # core-db presta sql (1521), no web
        tipos = casos.tipos_para(red.SERVICIOS["core-db"]["puertos"])
        self.assertNotIn("exploit_web", [t["clave"] for t in tipos])
        # elegir el "cuarto tipo" ya no existe: la opción 4 es inválida y cancela
        self.assertIsNone(demo.elegir_a_medida(self._resp([str(i_cdb), "4"])))

    def test_elegir_a_medida_cancela_con_cero(self):
        self.assertIsNone(demo.elegir_a_medida(self._resp(["0"])))

    def test_main_ataque_a_medida_lanza_el_ataque(self):
        objetivos = sorted(red.NODOS)
        i_wb = objetivos.index("web-banking") + 1
        llamadas, ejecutar = self._fake()
        # a -> objetivo web-banking -> tipo 1 -> origen 1 (internet) -> no deshacer -> salir
        resp = self._resp(["a", str(i_wb), "1", "1", "N", "0"])
        demo.main(leer=resp, ejecutar=ejecutar, dormir=lambda _: None)
        ataques = [a[-1] for a in llamadas if "sshpass" in a[-1]]
        self.assertTrue(ataques, "el ataque a medida debía lanzarse")
        self.assertIn("cliente@10.10.0.10", ataques[0])

    def test_menu_ofrece_el_ataque_a_medida(self):
        self.assertIn("a. Ataque a medida", demo.menu(demo.casos_vivos()) + demo.LINEA_A_MEDIDA)


if __name__ == "__main__":
    unittest.main()
