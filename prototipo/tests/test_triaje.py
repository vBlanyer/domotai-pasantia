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

    def test_amenaza_enrutada_lleva_ruta_en_la_traza_sin_accion(self):
        alerta = {"familia": "explotacion_conocida", "origen_ip": "203.0.113.9",
                  "activo": "web-banking", "servicio": "https", "mitre": ["T1190"]}
        perfil = {"activos": {}, "continuidad": {}, "rutas": {"appsec": "cola-appsec-banco"}}
        tr = triaje.procesar(alerta, {"nodos": {}}, perfil, "bancario", CAT, "d1", "t")
        self.assertEqual(tr["clase"], "amenaza_enrutada")
        self.assertEqual(tr["ruta"], "cola-appsec-banco")
        self.assertIsNone(tr["accion_propuesta"])

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

class TestImpactoDeterminado(unittest.TestCase):
    def test_la_traza_lleva_el_impacto_determinado(self):
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                            "prueba", CAT, id_decision="d1", timestamp="t")
        self.assertEqual(r["impacto_determinado"]["accion_id"], "BLOQUEAR_IP")
        self.assertEqual(r["impacto_determinado"]["actor"]["tipo"], "desconocido")   # la fixture no declara IPs

    def test_con_inventario_el_bloqueo_del_puesto_va_al_humano(self):
        p = y("perfil.yml")
        p["activos"]["puesto"]["ip"] = "192.168.1.10"
        r = triaje.procesar(j("alerta_vp.json"), j("hallazgos.json"), p, "prueba", CAT,
                            id_decision="d1", timestamp="t")
        self.assertEqual(r["clase"], "vp_intento_acceso")            # la clasificación no cambia
        self.assertEqual((r["resultado_filtro"], r["requiere_humano"]), ("veta", True))
        self.assertEqual(r["impacto_determinado"]["actor"]["nombre"], "puesto")

    def test_pasa_los_hallazgos_al_filtro(self):
        from unittest import mock
        from prototipo import perfil as perfilm
        h = j("hallazgos.json")
        with mock.patch.object(perfilm, "filtrar", wraps=perfilm.filtrar) as f:
            triaje.procesar(j("alerta_vp.json"), h, y("perfil.yml"), "prueba", CAT, "d1", "t")
        self.assertIs(f.call_args.kwargs["hallazgos"], h)

    def test_sin_accion_no_hay_impacto_determinado(self):
        alerta = {"familia": "explotacion_conocida", "origen_ip": "203.0.113.9",
                  "activo": "web-banking", "servicio": "https", "mitre": ["T1190"]}
        tr = triaje.procesar(alerta, {"nodos": {}}, {"activos": {}, "continuidad": {}}, "p", CAT, "d1", "t")
        self.assertIsNone(tr["impacto_determinado"])
