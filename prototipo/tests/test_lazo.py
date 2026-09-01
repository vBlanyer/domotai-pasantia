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
