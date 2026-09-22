import os
import unittest
import yaml
from lab.banco import red

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOPO = os.path.join(RAIZ, "lab", "topologias", "banco.clab.yml")


class TestTopologia(unittest.TestCase):
    def setUp(self):
        with open(TOPO, encoding="utf-8") as f:
            self.t = yaml.safe_load(f)
        self.nodos = self.t["topology"]["nodes"]

    def test_nombre_del_laboratorio(self):
        self.assertEqual(self.t["name"], "banco")

    def test_cada_nodo_de_la_red_tiene_su_ip_y_su_puerta(self):
        for nombre, n in red.NODOS.items():
            self.assertIn(nombre, self.nodos, nombre)
            execs = " ".join(self.nodos[nombre].get("exec", []))
            self.assertIn(f"{n['ip']}/24", execs, nombre)
            self.assertIn(f"via {n['gw']}", execs, nombre)

    def test_fw_core_es_la_puerta_de_cada_segmento(self):
        execs = " ".join(self.nodos["fw-core"]["exec"])
        for nombre, n in red.NODOS.items():
            if nombre in ("mdr-siem", "auditor"):
                continue
            self.assertIn(f"{n['gw']}/24", execs, nombre)
        self.assertIn("10.100.0.1/24", execs)
        self.assertIn("10.0.0.1/24", execs)

    def test_internet_no_tiene_ruta_por_defecto_propia(self):
        # Aislamiento: el atacante solo sabe llegar al banco, no a una salida real.
        execs = " ".join(self.nodos["internet"]["exec"])
        self.assertNotIn("default", execs)


if __name__ == "__main__":
    unittest.main()
