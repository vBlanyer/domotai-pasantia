import unittest
from prototipo import traza

class TestConstruir(unittest.TestCase):
    def test_registro_completo(self):
        r = traza.construir(
            id_decision="d1", timestamp="2026-08-31T00:00:00Z",
            alerta={"id_alerta":"a1","activo":"objetivo-vuln"},
            analisis_out={"clase":"vp_intento_acceso","prioridad":4,"confianza":1.0,"justificacion":"..."},
            accion_prop="BLOQUEAR_IP", impacto="localizado", perfil_nombre="empresarial",
            filtro_out={"resultado":"permite","accion_final":"BLOQUEAR_IP","requiere_humano":False},
            version_perfil="v0")
        for k in ("id_decision","timestamp","id_alerta","activo","clase","prioridad","confianza",
                  "justificacion","accion_propuesta","impacto","perfil_aplicado","resultado_filtro",
                  "accion_final","requiere_humano","version_baseline","version_perfil"):
            self.assertIn(k, r)
        self.assertEqual(r["id_alerta"], "a1")
        self.assertEqual(r["resultado_filtro"], "permite")
        self.assertEqual(r["version_baseline"], "baseline-0")
        self.assertEqual(r["version_perfil"], "v0")


class TestJustificacionEstructurada(unittest.TestCase):
    ALERTA = {"id_alerta": "a1", "regla_id": "5760", "origen_ip": "192.168.1.10",
              "activo": "objetivo-vuln", "servicio": "ssh", "mitre": ["T1110.001", "T1021.004"]}
    ANALISIS = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0, "justificacion": "..."}

    def _construir(self, alerta=None, accion="BLOQUEAR_IP"):
        return traza.construir(
            id_decision="d1", timestamp="t", alerta=alerta or self.ALERTA,
            analisis_out=self.ANALISIS, accion_prop=accion, impacto="localizado",
            perfil_nombre="empresarial",
            filtro_out={"resultado": "permite", "accion_final": accion, "requiere_humano": False},
            version_perfil="v0")

    def test_tiene_los_4_componentes(self):
        est = self._construir()["justificacion_estructurada"]
        self.assertEqual(set(est), {"evidencia", "hipotesis", "tecnica_mitre", "accion_sugerida"})

    def test_copia_accion_y_mitre_y_evidencia(self):
        est = self._construir()["justificacion_estructurada"]
        self.assertEqual(est["accion_sugerida"], "BLOQUEAR_IP")
        self.assertEqual(est["tecnica_mitre"], ["T1110.001", "T1021.004"])
        self.assertEqual(est["evidencia"]["regla"], "5760")
        self.assertEqual(est["evidencia"]["origen_ip"], "192.168.1.10")
        self.assertEqual(est["hipotesis"]["clase"], "vp_intento_acceso")
        self.assertEqual(est["hipotesis"]["confianza"], 1.0)

    def test_tolera_campos_ausentes(self):
        est = self._construir(alerta={"id_alerta": "a2"}, accion=None)["justificacion_estructurada"]
        self.assertEqual(est["tecnica_mitre"], [])
        self.assertIsNone(est["evidencia"]["origen_ip"])
        self.assertIsNone(est["accion_sugerida"])


class TestVersionJustificadorTraza(unittest.TestCase):
    def _c(self, analisis_out):
        return traza.construir(id_decision="d", timestamp="t", alerta={"id_alerta": "a"},
                               analisis_out=analisis_out, accion_prop="BLOQUEAR_IP", impacto="localizado",
                               perfil_nombre="p", filtro_out={"resultado": "permite", "accion_final": "BLOQUEAR_IP",
                               "requiere_humano": False}, version_perfil="v0")

    def test_registra_version_justificador_y_pasajes(self):
        r = self._c({"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0, "justificacion": "x",
                     "version_justificador": "llm-1b-0:llama-3.2-1b-q4.gguf", "pasajes_usados": ["regla-5760"]})
        self.assertEqual(r["version_justificador"], "llm-1b-0:llama-3.2-1b-q4.gguf")
        self.assertEqual(r["pasajes_usados"], ["regla-5760"])

    def test_default_plantilla_sin_metadata(self):
        r = self._c({"clase": "no_soportada", "prioridad": 1, "confianza": 1.0, "justificacion": "x"})
        self.assertEqual(r["version_justificador"], "plantilla-0")
        self.assertEqual(r["pasajes_usados"], [])
