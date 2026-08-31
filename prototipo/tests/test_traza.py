import unittest
from prototipo import traza

class TestConstruir(unittest.TestCase):
    def test_registro_completo(self):
        r = traza.construir(
            id_decision="d1", timestamp="2026-08-31T00:00:00Z",
            alerta={"id_alerta":"a1","activo":"objetivo-vuln"},
            analisis_out={"clase":"vp_intento_acceso","prioridad":4,"confianza":1.0,"justificacion":"..."},
            accion_prop="BLOQUEAR_IP", impacto="localizado", perfil_nombre="empresarial",
            filtro_out={"resultado":"permite","accion_final":"BLOQUEAR_IP","requiere_humano":False})
        for k in ("id_decision","id_alerta","clase","confianza","justificacion","accion_propuesta",
                  "impacto","perfil_aplicado","resultado_filtro","accion_final","requiere_humano","version_baseline"):
            self.assertIn(k, r)
        self.assertEqual(r["id_alerta"], "a1")
        self.assertEqual(r["resultado_filtro"], "permite")
        self.assertEqual(r["version_baseline"], "baseline-0")
