"""Invariantes de la demo portátil (Docker plano, sin Containerlab). No levantan contenedores:
fijan por contrato lo que el spike del 21/10 descubrió que la plataforma necesita."""
import os
import unittest

import yaml

AQUI = os.path.dirname(os.path.dirname(__file__))


def _compose():
    with open(os.path.join(AQUI, "docker-compose.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestCompose(unittest.TestCase):
    def test_objetivo_tiene_net_admin(self):
        # Lección del spike: sin CAP_NET_ADMIN, iptables falla aunque sudo funcione
        # (Containerlab la concede solo; Docker plano no).
        obj = _compose()["services"]["objetivo"]
        self.assertIn("NET_ADMIN", obj.get("cap_add", []))

    def test_objetivo_arranca_sshd(self):
        obj = _compose()["services"]["objetivo"]
        self.assertIn("sshd", str(obj.get("command", "")))

    def test_los_nodos_se_construyen_de_la_imagen_del_banco(self):
        # `build:` apunta al Dockerfile del banco: la demo es reproducible en una
        # máquina limpia (docker compose up --build), no depende de una imagen local.
        s = _compose()["services"]
        for nombre in ("gestion", "objetivo"):
            self.assertEqual(s[nombre]["image"], "banco-nodo:1", nombre)
            self.assertIn("banco", str(s[nombre].get("build", "")), nombre)

    def test_nombres_estables_para_el_aprovisionador(self):
        # El conector llega al nodo de gestión por NOMBRE de contenedor (docker exec).
        s = _compose()["services"]
        self.assertEqual(s["gestion"]["container_name"], "portatil-gestion")
        self.assertEqual(s["objetivo"]["container_name"], "portatil-objetivo")


class TestDemo(unittest.TestCase):
    def _demo(self):
        with open(os.path.join(AQUI, "demo.sh"), encoding="utf-8") as f:
            return f.read()

    def test_usa_el_aprovisionador_oficial(self):
        # Mínimo privilegio real (usuario triaje + sudoers del catálogo), no un atajo.
        self.assertIn("aprovisionar-minimo-privilegio.sh", self._demo())

    def test_termina_revirtiendo_la_contencion(self):
        self.assertIn("prototipo.revertir", self._demo())

    def test_normaliza_antes_del_lazo(self):
        # Trampa del spike: lazo/triaje por lotes consumen alertas NORMALIZADAS.
        d = self._demo()
        self.assertIn("prototipo.ingesta", d)
        self.assertIn("prototipo.lazo", d)


class TestDatosDeLaDemo(unittest.TestCase):
    def test_alerta_de_muestra_es_un_5760_sobre_objetivo_vuln(self):
        import json
        with open(os.path.join(AQUI, "alerta-muestra.jsonl"), encoding="utf-8") as f:
            a = json.loads(f.readline())
        self.assertEqual(a["rule"]["id"], "5760")
        self.assertEqual(a["predecoder"]["hostname"], "objetivo-vuln")

    def test_hallazgos_minimos_declaran_ssh_abierto(self):
        import json
        with open(os.path.join(AQUI, "hallazgos.json"), encoding="utf-8") as f:
            h = json.load(f)
        puertos = [x["puerto"] for x in h["nodos"]["objetivo-vuln"]]
        self.assertIn(22, puertos)


class TestWazuhParametrizable(unittest.TestCase):
    def test_wazuh_run_acepta_red_y_nombre_del_entorno(self):
        # La variante «viva» de la demo reusa wazuh-run.sh (única fuente del syslog/reglas)
        # sobre la red de compose; los defaults de clab se conservan.
        ruta = os.path.join(os.path.dirname(AQUI), "scripts", "wazuh-run.sh")
        with open(ruta, encoding="utf-8") as f:
            s = f.read()
        self.assertIn("WAZUH_NOMBRE", s)
        self.assertIn("WAZUH_RED", s)
        self.assertIn("clab-red-cliente-wazuh", s)   # default intacto
        self.assertIn('NET="${WAZUH_RED:-clab}"', s)


if __name__ == "__main__":
    unittest.main()
