import subprocess
import unittest
from lab.banco import demo


class TestDemo(unittest.TestCase):
    def _fake(self):
        llamadas = []
        def ejecutar(args, **kw):
            llamadas.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")
        return llamadas, ejecutar

    def test_casos_vivos_son_los_atacables(self):
        ids = [c["id"] for c in demo.casos_vivos()]
        self.assertEqual(ids, ["CASCADA", "D1", "A1", "K1", "E1", "RECON", "EXPLOIT"])
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
        caso = {"ataque": ("internet", "x"), "origen": "198.51.100.10", "destino_ip": "10.10.0.10"}
        nodo, cmd = demo.ataque_rotado(caso, "198.51.100.11")
        self.assertEqual(nodo, "internet")
        self.assertIn("ip addr add 198.51.100.11/24 dev eth1", cmd)  # alias en la interfaz de datos
        self.assertIn("ssh -b 198.51.100.11", cmd)                   # cliente atado a la IP nueva
        self.assertIn("cliente@10.10.0.10", cmd)                     # mismo destino

    def test_lanzar_con_src_ip_usa_ataque_rotado(self):
        llamadas, ejecutar = self._fake()
        caso = {"ataque": ("internet", "base"), "origen": "198.51.100.10", "destino_ip": "10.10.0.10"}
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


if __name__ == "__main__":
    unittest.main()
