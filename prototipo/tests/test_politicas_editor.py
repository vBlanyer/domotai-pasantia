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


class TestTriajePasaFamilia(unittest.TestCase):
    def test_triaje_pasa_familia_a_filtrar(self):
        import json, yaml
        from prototipo.motor import triaje
        fx = os.path.join(RAIZ, "tests", "fixtures")
        alerta = json.load(open(os.path.join(fx, "alerta_vp.json"), encoding="utf-8"))
        hall = json.load(open(os.path.join(fx, "hallazgos.json"), encoding="utf-8"))
        base = yaml.safe_load(open(os.path.join(fx, "perfil.yml"), encoding="utf-8"))
        alerta["familia"] = "reconocimiento"
        sin = triaje.procesar(alerta, hall, base, "p", CAT, id_decision="d1", timestamp="t")
        self.assertFalse(sin["requiere_humano"])   # sin la clave: automatica
        p = {**base, "automatizacion_por_familia": {"reconocimiento": {"automatizacion": "humano_siempre"}}}
        r = triaje.procesar(alerta, hall, p, "p", CAT, id_decision="d1", timestamp="t")
        self.assertTrue(r["requiere_humano"])


class TestFusionYValidacion(unittest.TestCase):
    def test_fusionar_no_muta_y_aplica_overlay(self):
        base = {"ip_gestion": "10.0.0.1"}
        out = perfil.fusionar_politicas(base, {"politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}}})
        self.assertEqual(out["politicas_por_zona"]["Core"]["automatizacion"], "humano_siempre")
        self.assertNotIn("politicas_por_zona", base)

    def test_fusionar_none_quita_clave(self):
        base = {"politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}, "DMZ": {"automatizacion": "humano_siempre"}}}
        out = perfil.fusionar_politicas(base, {"politicas_por_zona": {"Core": None}})
        self.assertNotIn("Core", out["politicas_por_zona"])
        self.assertIn("Core", base["politicas_por_zona"])

    def test_validar_avisa_postura_invalida(self):
        p = {**BASE, "automatizacion_por_familia": {"reconocimiento": {"automatizacion": "siempre_si"}}}
        self.assertTrue(any("automatizacion" in a for a in perfil.validar(p)))

    def test_validar_avisa_zona_o_activo_desconocido(self):
        p = {**BASE, "politicas_por_zona": {"NoExiste": {"automatizacion": "humano_siempre"}},
             "overrides_por_activo": {"fantasma": {"automatizacion": "humano_siempre"}}}
        av = perfil.validar(p)
        self.assertTrue(any("NoExiste" in a for a in av))
        self.assertTrue(any("fantasma" in a for a in av))


class TestArranqueOverlay(unittest.TestCase):
    def _canonico(self, d):
        import yaml
        ruta = os.path.join(d, "canon.yml")
        with open(ruta, "w", encoding="utf-8") as f:
            yaml.safe_dump({"ip_gestion": "10.0.0.1"}, f)
        ov = os.path.join(d, "ov.yml")
        with open(ov, "w", encoding="utf-8") as f:
            yaml.safe_dump({"politicas_por_zona": {"Core": {"automatizacion": "humano_siempre"}}}, f)
        return ruta, ov

    def test_arranque_fusiona_overlay(self):
        import tempfile
        from prototipo.servicio import tablero
        with tempfile.TemporaryDirectory() as d:
            ruta, ov = self._canonico(d)
            srv = tablero.crear_servidor(tablero.EstadoTablero(), os.path.join(d, "t.jsonl"),
                                         puerto=0, perfil=perfil.cargar(ruta), ruta_overlay=ov,
                                         ruta_auditoria=os.path.join(d, "a.jsonl"))
            try:
                self.assertIn("politicas_por_zona", srv.perfil)
                self.assertNotIn("politicas_por_zona", perfil.cargar(ruta))
            finally:
                srv.server_close()

    def test_evaluacion_no_ve_overlay(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ruta, _ = self._canonico(d)
            self.assertNotIn("politicas_por_zona", perfil.cargar(ruta))


if __name__ == "__main__":
    unittest.main()
