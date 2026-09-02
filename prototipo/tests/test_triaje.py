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
