import os, unittest
from prototipo.motor import perfil
from prototipo.accion import catalogo as cat

RAIZ = os.path.join(os.path.dirname(__file__), "..")
BASE = perfil.cargar(os.path.join(RAIZ, "perfiles", "bancario.yml"))
CAT = cat.cargar_catalogo(os.path.join(RAIZ, "catalogo.yml"))
IP = {"ip": "203.0.113.9"}


def _f(p, activo="web-banking", accion="BLOQUEAR_IP", params=IP, familia="reconocimiento"):
    return perfil.filtrar(p, accion, params, CAT, activo, None, 0.99, familia=familia)


class TestCompuertasPostura(unittest.TestCase):
    def test_familia_humano_degrada_auto_a_humano(self):
        self.assertFalse(_f(BASE)["requiere_humano"])
        p = {**BASE, "automatizacion_por_familia": {"reconocimiento": {"automatizacion": "humano_siempre"}}}
        r = _f(p)
        self.assertTrue(r["requiere_humano"])
        self.assertEqual(r["accion_final"], "BLOQUEAR_IP")

    def test_zona_humano_degrada(self):
        p = {**BASE, "politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}}}
        self.assertTrue(_f(p, activo="middleware")["requiere_humano"])

    def test_override_activo_gana_sobre_zona(self):
        p = {**BASE, "overrides_por_activo": {"web-banking": {"automatizacion": "humano_siempre"}}}
        self.assertTrue(_f(p)["requiere_humano"])
        p2 = {**BASE,
              "politicas_por_zona": {"DMZ": {"automatizacion": "humano_siempre"}},
              "overrides_por_activo": {"web-banking": {"automatizacion": "automatica_si_confianza"}}}
        self.assertEqual(perfil.postura_zona_activo(p2, "web-banking"), "automatica_si_confianza")
        self.assertFalse(_f(p2)["requiere_humano"])

    def test_activo_sin_zona_no_recibe_gate(self):
        p = {**BASE, "politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}}}
        self.assertIsNone(perfil.zona_de(p, "objetivo-vuln"))
        self.assertFalse(_f(p, activo="objetivo-vuln")["requiere_humano"])

    def test_posturas_ausentes_sin_efecto(self):
        self.assertFalse(_f(BASE)["requiere_humano"])
        self.assertFalse(_f(BASE, familia=None)["requiere_humano"])

    def test_gate_no_sube_a_auto(self):
        p = {**BASE, "automatizacion_por_familia": {"malware": {"automatizacion": "automatica_si_confianza"}}}
        r = _f(p, accion="AISLAR_NODO", params={}, familia="malware")
        self.assertTrue(r["requiere_humano"])

    def test_resolvers(self):
        self.assertEqual(perfil.zona_de(BASE, "middleware"), "Core")
        self.assertIsNone(perfil.postura_familia(BASE, "x"))
        p = {**BASE, "automatizacion_por_familia": {"x": {"automatizacion": "humano_siempre"}}}
        self.assertEqual(perfil.postura_familia(p, "x"), "humano_siempre")


if __name__ == "__main__":
    unittest.main()
