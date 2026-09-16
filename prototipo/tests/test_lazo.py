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
                               ejecutor_ok, "d2", "2026-08-31T00:00:00Z", leer=lambda _: "2")  # 2) rechazar
        self.assertEqual(r["veredicto_humano"], "rechazar")
        self.assertIsNone(r["ejecucion"])          # rechazada -> no se ejecuta

    def test_procesar_lazo_propaga_justificar_fn_a_la_traza(self):
        # el justificador inyectado (dict) fluye a la traza (RF-09): version + pasajes.
        def just_dict(a, c, cl):
            return {"texto": "TEXTO-LLM", "version_justificador": "llm-1b-0:m.gguf", "pasajes_usados": ["p1"]}
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                               lazo._EjecutorAuto(), "d5", "t", leer=lambda *_: "2",  # 2) rechazar
                               justificar_fn=just_dict)
        self.assertEqual(r["justificacion"], "TEXTO-LLM")
        self.assertEqual(r["version_justificador"], "llm-1b-0:m.gguf")
        self.assertEqual(r["pasajes_usados"], ["p1"])

    def test_lazo_reclasificar_registra_la_clase_y_no_ejecuta(self):
        # RF-08: "reclasificar" retiene sin ejecutar y registra la clase corregida como feedback (RF-12).
        a = dict(j("alerta_vp.json")); a["activo"] = "fantasma"
        # menú cerrado por número: 3) reclasificar, luego 1) la 1ª clase distinta de la actual
        guion = iter(["3", "1"]); leer = lambda *_: next(guion)
        r = lazo.procesar_lazo(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                               ejecutor_ok, "d3", "2026-08-31T00:00:00Z", leer=leer)
        self.assertEqual(r["veredicto_humano"], "reclasificar")
        self.assertEqual(r["clase_reclasificada"], "fp_actividad_legitima")
        self.assertIsNone(r["ejecucion"])
        self.assertIsNone(r["orden"])


class TestMitigarFn(unittest.TestCase):
    def test_delega_al_agente_cuando_hay_accion(self):
        # vp con accion_final -> se llama a mitigar_fn (agente), no al conector; la traza lleva el plan
        llamadas = []
        def mitigar(decision, alerta, leer):
            llamadas.append(decision["clase"])
            return {"resultado": "mitigado", "escalado": True, "dispositivo_ejecutor": "gateway"}
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"), "prueba", CAT,
                               ejecutor_ok, "d1", "t", mitigar_fn=mitigar)
        self.assertEqual(llamadas, ["vp_intento_acceso"])          # el agente decidió
        self.assertEqual(r["mitigacion_agente"]["dispositivo_ejecutor"], "gateway")
        self.assertIsNone(r["ejecucion"])                          # no pasó por el conector

    def test_no_llama_al_agente_si_no_hay_accion(self):
        # alerta fuera de perímetro -> no_soportada -> accion_final None -> el agente NO se invoca
        a = dict(j("alerta_vp.json")); a["familia"] = "plataforma"
        llamado = []
        r = lazo.procesar_lazo(a, j("hallazgos.json"), y("perfil.yml"), "prueba", CAT, ejecutor_ok,
                               "d2", "t", mitigar_fn=lambda *args: llamado.append(1))
        self.assertEqual(llamado, [])
        self.assertNotIn("mitigacion_agente", r)


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


class TestEscaladaPorDefecto(unittest.TestCase):
    """Requisito del tutor industrial: si no se puede cortar en el host, saltar al cortafuegos."""

    def _perfil_con_topologia(self):
        p = dict(y("perfil.yml"))
        p["topologia"] = {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "gateway"},
                          "gateway": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}}
        p["ip_gestion"] = "192.168.1.100"
        return p

    class HostCaido:
        def __init__(self): self.aplicado = set()
        def __call__(self, nodo_ip, cmd):
            if nodo_ip == "192.168.1.30":
                return (255, "Connection refused")
            if "grep" in cmd:
                return (0, "DROP") if nodo_ip in self.aplicado else (1, "")
            self.aplicado.add(nodo_ip); return (0, "")

    def test_si_el_host_no_responde_escala_al_cortafuegos_y_lo_anota(self):
        preguntas = []
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), self._perfil_con_topologia(),
                               "prueba", CAT, self.HostCaido(), "d1", "t",
                               leer=lambda p: (preguntas.append(p), "s")[1])
        self.assertFalse(r["ejecucion"]["exito"])                 # el host fallo, y consta
        self.assertEqual(r["escalada"]["resultado"], "mitigado")
        self.assertEqual(r["escalada"]["dispositivo_ejecutor"], "gateway")
        self.assertEqual(r["escalada"]["orden_efectiva"]["accion_id"], "BLOQUEAR_IP_FIREWALL")
        self.assertEqual(len(preguntas), 1)                       # el perfil exige humano en el cortafuegos

    def test_sin_topologia_no_hay_a_donde_escalar(self):
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), y("perfil.yml"),
                               "prueba", CAT, self.HostCaido(), "d1", "t")
        self.assertFalse(r["ejecucion"]["exito"])
        self.assertIsNone(r["escalada"])

    def test_si_el_host_responde_y_verifica_no_se_escala(self):
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), self._perfil_con_topologia(),
                               "prueba", CAT, lazo._EjecutorAuto(), "d1", "t")
        self.assertTrue(r["ejecucion"]["exito"]); self.assertTrue(r["verificacion"]["verificado"])
        self.assertIsNone(r["escalada"])

    def test_si_el_host_ejecuta_pero_no_se_verifica_tambien_se_escala(self):
        # Contencion no verificada = no contencion: el cortafuegos entra, con la pregunta del perfil.
        preguntas = []
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), self._perfil_con_topologia(),
                               "prueba", CAT, ejecutor_ok, "d1", "t",
                               leer=lambda p: (preguntas.append(p), "n")[1])
        self.assertFalse(r["verificacion"]["verificado"])
        self.assertEqual(r["escalada"]["resultado"], "cancelado_por_humano")
        self.assertEqual(len(preguntas), 1)

    def test_la_reversion_de_una_escalada_sale_de_la_orden_efectiva(self):
        from prototipo import revertir
        ej = self.HostCaido()
        r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), self._perfil_con_topologia(),
                               "prueba", CAT, ej, "d1", "t", leer=lambda p: "s")
        llamadas = []
        def ej_rev(nodo_ip, cmd):
            llamadas.append((nodo_ip, cmd))
            if cmd.startswith("iptables -D"):
                ej.aplicado.discard(nodo_ip); return (0, "")
            return ej(nodo_ip, cmd)
        rev = revertir.revertir(r, CAT, ej_rev, "t2", motivo="prueba")
        self.assertTrue(rev["exito"]); self.assertTrue(rev.get("escalada"))
        self.assertEqual(rev["nodo"], "gateway")
        self.assertIn("iptables -D FORWARD -s 192.168.1.10 -j DROP", rev["comando_ejecutado"])
        self.assertTrue(all(ip == "192.168.1.1" for ip, _ in llamadas))   # nunca toca al host caido

