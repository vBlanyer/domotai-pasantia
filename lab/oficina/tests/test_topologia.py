"""Laboratorio «oficina» (plan del asistente de red, tarea 1): la topología de Containerlab coincide con
la fuente única lab/oficina/red.py, y nada trae preparado el acceso del conector."""
import os
import unittest

import yaml

from lab.oficina import red

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOPO = os.path.join(RAIZ, "lab", "topologias", "oficina.clab.yml")
GUION = os.path.join(RAIZ, "lab", "oficina", "oficina.sh")


class TestTopologia(unittest.TestCase):
    def setUp(self):
        with open(TOPO, encoding="utf-8") as f:
            self.t = yaml.safe_load(f)
        self.nodos = self.t["topology"]["nodes"]

    def _exec(self, nodo):
        return " ".join(self.nodos[nodo].get("exec", []))

    def test_nombre_del_laboratorio(self):
        self.assertEqual(self.t["name"], "oficina")

    def test_cada_nodo_tiene_su_ip_y_su_puerta(self):
        for nombre, n in red.NODOS.items():
            self.assertIn(nombre, self.nodos, nombre)
            self.assertIn(f"ip addr add {n['ip']}/24", self._exec(nombre), nombre)
            self.assertIn(f"via {n['gw']}", self._exec(nombre), nombre)

    def test_los_cortafuegos_tienen_todas_sus_interfaces(self):
        for nombre, f in red.CORTAFUEGOS.items():
            for ip in f["interfaces"].values():
                self.assertIn(f"ip addr add {ip}/24", self._exec(nombre), (nombre, ip))
            self.assertEqual(self.nodos[nombre]["sysctls"], {"net.ipv4.ip_forward": 1}, nombre)

    def test_internet_sin_salida_real(self):
        self.assertIn("ip route del default", self._exec("internet"))
        self.assertIn("iptables -A OUTPUT -o eth0 -j DROP", self._exec("internet"))

    def test_nadie_trae_el_conector(self):
        with open(TOPO, encoding="utf-8") as f:
            topo = f.read()
        with open(GUION, encoding="utf-8") as f:
            guion = f.read()
        for texto in (topo, guion):
            self.assertNotIn("aprovisionar", texto)
            self.assertNotIn("adduser triaje", texto)
            self.assertNotIn("useradd triaje", texto)

    def test_servicios_simulados(self):
        orden = red.orden_servicio("impresora")
        self.assertIn("--puerto 80", orden)
        self.assertIn("--puerto 9100", orden)
        self.assertEqual(red.orden_servicio("puesto"), "")

    def test_rangos_cubren_a_todos(self):
        import ipaddress
        redes = [ipaddress.ip_network(r) for r in red.RANGOS]
        ips = [n["ip"] for k, n in red.NODOS.items() if k != "internet"]
        ips += [ip for f in red.CORTAFUEGOS.values() for ip in f["interfaces"].values()]
        for ip in ips:
            if ip.startswith("198.51.100."):
                continue                                       # la cara de fw-borde hacia internet
            self.assertTrue(any(ipaddress.ip_address(ip) in r for r in redes), ip)


class TestOrdenMdr(unittest.TestCase):
    """oficina.sh mdr: arranca el MDR como en un cliente nuevo (perfil mínimo, nada aprovisionado)."""
    def setUp(self):
        with open(GUION, encoding="utf-8") as f:
            self.guion = f.read()
        self.bloque = self.guion.split("\n  mdr)", 1)[1].split(";;", 1)[0] if "\n  mdr)" in self.guion else ""

    def test_orden_mdr(self):
        self.assertTrue(self.bloque, "falta la orden mdr")
        for trozo in ("TRIAJE_NODO_GESTION=clab-oficina-mdr", "perfil_minimo", "run/oficina/perfil.yml",
                      "run/oficina/postura.json", "TRIAJE_ASISTENTE_ABIERTO=1", "prototipo.servicio.stream"):
            self.assertIn(trozo, self.bloque, trozo)
        self.assertNotIn("aprovisionar", self.guion)

    def test_el_perfil_minimo_usa_los_rangos_del_laboratorio(self):
        for r in red.RANGOS:
            self.assertIn(f"--rango {r}", self.bloque, r)
        self.assertIn(f"--gestion {red.GESTION}", self.bloque)


if __name__ == "__main__":
    unittest.main()
