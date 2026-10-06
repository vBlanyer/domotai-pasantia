"""Buena-formación de las reglas locales de Wazuh del banco y presencia de las reglas web (G4).

No corre Wazuh (eso se valida en vivo): solo comprueba que el fragmento XML está bien formado y que
las reglas web de ataque existen con el grupo 'attack' (que el adaptador mapea a explotacion_conocida)
y con técnica MITRE. Los ficheros de local_rules de Wazuh son FRAGMENTOS (varios <group> de primer
nivel), así que se envuelven en una raíz sintética para parsearlos con ElementTree.
"""
import os
import unittest
import xml.etree.ElementTree as ET

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REGLAS = os.path.join(RAIZ, "lab", "wazuh", "local_rules_banco.xml")


def _arbol():
    with open(REGLAS, encoding="utf-8") as f:
        return ET.fromstring(f"<root>{f.read()}</root>")


class TestReglasWeb(unittest.TestCase):
    def test_fragmento_bien_formado(self):
        _arbol()   # no lanza -> XML bien formado

    def test_reglas_web_presentes_con_grupo_attack_y_mitre(self):
        reglas = {r.get("id"): r for r in _arbol().iter("rule")}
        for rid in ("100300", "100301", "100302"):
            self.assertIn(rid, reglas, f"falta la regla {rid}")
            r = reglas[rid]
            grupos = (r.findtext("group") or "")
            self.assertIn("attack", grupos, f"{rid} sin grupo attack")
            self.assertTrue(r.find("mitre") is not None, f"{rid} sin MITRE")


if __name__ == "__main__":
    unittest.main()
