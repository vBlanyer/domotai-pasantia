import json, os, unittest, yaml
from prototipo import lazo, catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
def j(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return json.loads(f.read().strip())
def y(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f: return yaml.safe_load(f)

def ejecutor_ok(nodo_ip, comando):
    # verificación: no está antes de aplicar, sí después; aplicar: rc 0
    if "grep" in comando: return (1, "")   # primera verificación: no está
    return (0, "")

class TestLazo(unittest.TestCase):
    def test_lazo_vp_ejecuta_y_traza(self):
        # alerta_vp: fuerza bruta SSH contra objetivo-vuln con SSH expuesto -> vp_intento -> BLOQUEAR_IP -> permite
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                               "prueba", CAT, ejecutor_ok, "d1", "2026-08-31T00:00:00Z")
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertIsNotNone(r["orden"])
        self.assertEqual(r["orden"]["accion_id"], "BLOQUEAR_IP")
        self.assertIsNotNone(r["ejecucion"])
        self.assertIn("verificacion", r)
        self.assertIsNone(r["veredicto_humano"])   # confianza alta, no requiere humano

    def test_lazo_rechazo_humano_no_ejecuta(self):
        # forzamos requiere_humano con confianza baja: activo desconocido -> postura None -> confianza 0.5 -> veta
        a = dict(j("alerta_vp.json")); a["activo"] = "fantasma"
        r = lazo.procesar_lazo(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                               ejecutor_ok, "d2", "2026-08-31T00:00:00Z", leer=lambda _: "rechazar")
        self.assertEqual(r["veredicto_humano"], "rechazar")
        self.assertIsNone(r["ejecucion"])          # rechazada -> no se ejecuta

    def test_procesar_lazo_propaga_justificar_fn_a_la_traza(self):
        # el justificador inyectado (dict) fluye a la traza (RF-09): version + pasajes.
        def just_dict(a, c, cl):
            return {"texto": "TEXTO-LLM", "version_justificador": "llm-1b-0:m.gguf", "pasajes_usados": ["p1"]}
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                               lazo._EjecutorAuto(), "d5", "t", leer=lambda *_: "rechazar",
                               justificar_fn=just_dict)
        self.assertEqual(r["justificacion"], "TEXTO-LLM")
        self.assertEqual(r["version_justificador"], "llm-1b-0:m.gguf")
        self.assertEqual(r["pasajes_usados"], ["p1"])

    def test_lazo_reclasificar_registra_la_clase_y_no_ejecuta(self):
        # RF-08: "reclasificar" retiene sin ejecutar y registra la clase corregida como feedback (RF-12).
        a = dict(j("alerta_vp.json")); a["activo"] = "fantasma"
        leer = lambda p: "reclasificar" if "aprobar" in p else "fp_actividad_legitima"
        r = lazo.procesar_lazo(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                               ejecutor_ok, "d3", "2026-08-31T00:00:00Z", leer=leer)
        self.assertEqual(r["veredicto_humano"], "reclasificar")
        self.assertEqual(r["clase_reclasificada"], "fp_actividad_legitima")
        self.assertIsNone(r["ejecucion"])
        self.assertIsNone(r["orden"])


class TestEjecutorAuto(unittest.TestCase):
    def test_ejecutor_auto_confirma_verificacion_tras_aplicar(self):
        ej = lazo._EjecutorAuto()
        # pre-check: aún no aplicado -> rc1
        rc1, _ = ej("192.168.1.30", "iptables -L -n | grep 192.168.1.10")
        self.assertEqual(rc1, 1)
        # aplicar la acción
        rc2, _ = ej("192.168.1.30", "iptables -A INPUT -s 192.168.1.10 -j DROP")
        self.assertEqual(rc2, 0)
        # re-verificación posterior: ya aplicado -> rc0
        rc3, _ = ej("192.168.1.30", "iptables -L -n | grep 192.168.1.10")
        self.assertEqual(rc3, 0)

    def test_lazo_auto_completo_da_ejecucion_exitosa_y_verificada(self):
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                               "prueba", CAT, lazo._EjecutorAuto(), "d4", "2026-08-31T00:00:00Z")
        self.assertTrue(r["ejecucion"]["exito"])
        self.assertTrue(r["verificacion"]["verificado"])
