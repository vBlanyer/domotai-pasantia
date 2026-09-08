import json, os, unittest, yaml
from prototipo import triaje, catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))

def j(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return json.loads(f.read().strip())

def y(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return yaml.safe_load(f)

class TestProcesar(unittest.TestCase):
    def test_lazo_completo_una_alerta(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="2026-08-31T00:00:00Z")
        # fuerza bruta SSH contra objetivo-vuln con SSH expuesto -> VP intento -> BLOQUEAR_IP localizado -> permite
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["accion_propuesta"], "BLOQUEAR_IP")
        self.assertEqual(r["resultado_filtro"], "permite")
        self.assertIn("192.168.1.10", r["justificacion"])

class TestJustificarFn(unittest.TestCase):
    def test_procesar_usa_el_justificar_fn_inyectado(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                            id_decision="d1", timestamp="2026-08-31T00:00:00Z",
                            justificar_fn=lambda a, c, cl: "JUSTIFICACION-INYECTADA")
        self.assertEqual(r["justificacion"], "JUSTIFICACION-INYECTADA")
        self.assertEqual(r["version_justificador"], "plantilla-0")   # str -> plantilla (RF-09)

    def test_procesar_registra_metadata_del_justificador_dict(self):
        def just_dict(a, c, cl):
            return {"texto": "TEXTO", "version_justificador": "llm-1b-0:modelo.gguf", "pasajes_usados": ["p1"]}
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                            id_decision="d2", timestamp="t", justificar_fn=just_dict)
        self.assertEqual(r["justificacion"], "TEXTO")
        self.assertEqual(r["version_justificador"], "llm-1b-0:modelo.gguf")
        self.assertEqual(r["pasajes_usados"], ["p1"])

    def test_procesar_registra_consulta_rag_agentica(self):
        def just_dict(a, c, cl):
            return {"texto": "TEXTO", "version_justificador": "llm-1b-0:m.gguf",
                    "pasajes_usados": ["d3fend-D3-ITF"], "consulta_usada": "D3-ITF filtrado",
                    "recuperacion_agentica": True}
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                            id_decision="d4", timestamp="t", justificar_fn=just_dict)
        self.assertEqual(r["consulta_rag"], "D3-ITF filtrado")
        self.assertTrue(r["recuperacion_agentica"])
