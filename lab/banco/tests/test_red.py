import os
import unittest
import yaml
from lab.banco import red

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PERFIL = yaml.safe_load(open(os.path.join(RAIZ, "prototipo", "perfiles", "bancario.yml"), encoding="utf-8"))


class TestCoherenciaConElPerfil(unittest.TestCase):
    def test_las_ips_del_laboratorio_son_las_del_perfil(self):
        for nombre, activo in PERFIL["activos"].items():
            self.assertIn(nombre, red.NODOS, nombre)
            self.assertEqual(red.NODOS[nombre]["ip"], activo["ip"], nombre)

    def test_toda_dependencia_declarada_existe_en_el_laboratorio(self):
        for nombre, activo in PERFIL["activos"].items():
            for dep in activo.get("depende_de") or []:
                self.assertIn(dep, red.SERVICIOS[nombre]["depende"], f"{nombre} -> {dep}")

    def test_la_unica_dependencia_no_declarada_es_la_de_k3(self):
        reales = {(n, d) for n, s in red.SERVICIOS.items() for d in s["depende"]}
        declaradas = {(n, d) for n, a in PERFIL["activos"].items() for d in (a.get("depende_de") or [])}
        self.assertEqual(reales - declaradas, red.NO_DECLARADAS)
        self.assertEqual(red.NO_DECLARADAS, {("atm", "middleware")})


class TestDerivados(unittest.TestCase):
    def test_comando_de_servicio_con_dependencias_por_ip(self):
        cmd = red.comando_servicio("middleware")
        self.assertIn("--nombre middleware", cmd)
        self.assertIn("--puerto 8443", cmd)
        self.assertIn("--depende 10.50.0.10:1521", cmd)
        self.assertIn("--depende 10.60.0.10:9000", cmd)

    def test_nodo_sin_servicio_no_tiene_comando(self):
        self.assertIsNone(red.comando_servicio("taquilla"))

    def test_monitor_vigila_todos_los_servicios(self):
        self.assertEqual(sorted(a.split("=")[0] for a in red.args_monitor()), sorted(red.SERVICIOS))
        self.assertIn("core-db=10.50.0.10:1521", red.args_monitor())

    def test_el_auditor_escanea_ssh_y_los_puertos_nominales(self):
        puertos = red.puertos_auditor().split(",")
        for p in ("22", "80", "443", "1521", "8080", "8443", "9000", "48002"):
            self.assertIn(p, puertos)
        self.assertIn("core-db:10.50.0.10", red.nodos_auditor().split())


if __name__ == "__main__":
    unittest.main()
