import os, unittest, yaml
from prototipo import perfil, catalogo

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
def perfil_fx():
    with open(os.path.join(FX, "perfil.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)

class TestFiltro(unittest.TestCase):
    def setUp(self):
        self.p = perfil_fx()

    def test_sin_accion(self):
        r = perfil.filtrar(self.p, None, {}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "sin_accion")

    def test_localizado_confianza_alta_permite(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "permite")

    def test_umbral_configurable_por_perfil(self):
        # RF-07: el umbral de escalado sale del perfil, no del código
        p = perfil_fx(); p["continuidad"]["umbral_confianza"] = 0.9
        r = perfil.filtrar(p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 0.8)
        self.assertEqual(r["resultado"], "veta")            # 0.8 < 0.9 -> escala
        self.assertTrue(r["requiere_humano"])
        p["continuidad"]["umbral_confianza"] = 0.5
        r2 = perfil.filtrar(p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 0.8)
        self.assertEqual(r2["resultado"], "permite")        # 0.8 >= 0.5 -> automatica

    def test_umbral_por_defecto_es_0_7(self):
        # sin la clave en el perfil, el default 0.7 y el borde >=
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 0.7)
        self.assertEqual(r["resultado"], "permite")         # 0.7 >= 0.7
        r2 = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 0.69)
        self.assertEqual(r2["resultado"], "veta")           # 0.69 < 0.7
        self.assertFalse(r["requiere_humano"])

    def test_localizado_confianza_baja_veta(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 0.5)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])

    def test_alcanza_servicio_sin_alternativa_veta(self):
        r = perfil.filtrar(self.p, "AISLAR_NODO", {"ip_nodo":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])

    def test_bloquear_puerto_degrada_a_bloquear_ip(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_PUERTO", {"puerto":443,"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "degrada")
        self.assertEqual(r["accion_final"], "BLOQUEAR_IP")

    def test_no_cortar_gestion_veta_cerrar_ssh(self):
        r = perfil.filtrar(self.p, "CERRAR_SERVICIO", {"servicio":"ssh"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])

    def test_accion_inexistente_veta(self):
        r = perfil.filtrar(self.p, "ACCION_INEXISTENTE", {}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])

    def test_bloquear_puerto_confianza_baja_degradacion_con_humano(self):
        r = perfil.filtrar(self.p, "BLOQUEAR_PUERTO", {"puerto":443,"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 0.3)
        self.assertEqual(r["resultado"], "degrada")
        self.assertEqual(r["accion_final"], "BLOQUEAR_IP")
        self.assertTrue(r["requiere_humano"])

    def test_excepcion_nunca_automatica_degrada(self):
        p = {"activos": {"servidor-web": {"criticidad": "alta"}},
             "continuidad": {"impacto_localizado": "automatica_si_confianza",
                             "impacto_alcanza_servicio": "automatica_si_confianza"},
             "excepciones": [{"servicio": 443, "activo": "servidor-web", "regla": "nunca_automatica"}]}
        r = perfil.filtrar(p, "BLOQUEAR_PUERTO", {"puerto": 443, "ip": "1.2.3.4"}, CAT, "servidor-web", "https", 1.0)
        self.assertEqual(r["resultado"], "degrada")
        self.assertEqual(r["accion_final"], "BLOQUEAR_IP")


class TestPerfilBancario(unittest.TestCase):
    """Garantías de continuidad del perfil de cliente bancario (perfiles/bancario.yml, Opción A):
    ningún servicio ni joya de la corona se corta automáticamente; el plano de gestión es intocable;
    el único automatismo es bloquear la IP del atacante externo evidente (localizado y reversible)."""
    def setUp(self):
        with open(os.path.join(FX, "..", "..", "perfiles", "bancario.yml"), encoding="utf-8") as f:
            self.p = yaml.safe_load(f)

    def test_umbral_de_automatismo_es_alto_0_9(self):
        # RF-07: un bloqueo de IP a 0.85 no basta; a 0.95 sí.
        veta = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, CAT, "web-banking", "443", 0.85)
        self.assertEqual(veta["resultado"], "veta")
        self.assertTrue(veta["requiere_humano"])
        auto = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, CAT, "web-banking", "443", 0.95)
        self.assertEqual(auto["resultado"], "permite")
        self.assertFalse(auto["requiere_humano"])

    def test_joya_de_la_corona_nunca_corta_su_servicio(self):
        # core-db: el corte de puerto (mataría la DB, 1521) degrada a bloquear la IP atacante.
        r = perfil.filtrar(self.p, "BLOQUEAR_PUERTO", {"puerto": 1521, "ip": "203.0.113.9"},
                           CAT, "core-db", "1521", 0.99)
        self.assertEqual(r["resultado"], "degrada")
        self.assertEqual(r["accion_final"], "BLOQUEAR_IP")   # nunca CERRAR/BLOQUEAR el servicio 1521

    def test_cortar_un_servicio_del_banco_exige_humano(self):
        # cerrar el servicio de banca online no es automático jamás (impacto alcanza_servicio).
        r = perfil.filtrar(self.p, "CERRAR_SERVICIO", {"servicio": "https"}, CAT, "web-banking", "443", 0.99)
        self.assertEqual(r["resultado"], "veta")
        self.assertTrue(r["requiere_humano"])

    def test_plano_de_gestion_es_intocable(self):
        # RF-19: el MDR no corta el plano SOC/gestión ni con humano (accion_final None).
        r = perfil.filtrar(self.p, "CERRAR_SERVICIO", {"servicio": "ssh"}, CAT, "mdr-siem", "ssh", 0.99)
        self.assertEqual(r["resultado"], "veta")
        self.assertIsNone(r["accion_final"])

    def test_bloquear_ip_del_atacante_a_una_joya_es_reversible_y_auto(self):
        # bloquear la IP que ataca al HSM es seguro (no toca el HSM) -> auto con confianza alta.
        r = perfil.filtrar(self.p, "BLOQUEAR_IP", {"ip": "203.0.113.9"}, CAT, "hsm", "9000", 0.99)
        self.assertEqual(r["resultado"], "permite")

    def test_ruta_de_resuelve_con_binding_y_cae_al_rol(self):
        p = {"rutas": {"appsec": "cola-appsec-banco"}}
        self.assertEqual(perfil.ruta_de(p, "appsec"), "cola-appsec-banco")
        self.assertEqual(perfil.ruta_de({}, "appsec"), "appsec")   # sin binding -> rol logico
        self.assertIsNone(perfil.ruta_de(p, None))


PERFIL_INV = {
    "ip_gestion": "172.20.20.4",
    "activos": {"puesto": {"ip": "192.168.1.10", "funcion": "puesto de trabajo de un empleado"},
                "borde": {"ip": "192.168.1.1", "funcion": "equipo de borde"}},
    "topologia": {"objetivo-vuln": {"rol": "host_victima", "ip": "192.168.1.30", "gateway": "borde"},
                  "borde": {"rol": "firewall_perimetral", "ip": "192.168.1.1"}},
    "continuidad": {"impacto_ninguno": "automatica", "impacto_localizado": "automatica_si_confianza",
                    "impacto_alcanza_servicio": "humano_siempre", "reversibilidad_obligatoria": True,
                    "no_cortar_gestion": True},
}


class TestConcienciaDeActores(unittest.TestCase):
    """Spec de conciencia de impacto §4.4: a quién bloquea la acción FINAL gobierna el filtro."""

    def _filtrar(self, accion, params, p=PERFIL_INV, **kw):
        return perfil.filtrar(p, accion, params, CAT, "objetivo-vuln", "ssh", 1.0, **kw)

    def test_bloquear_la_gestion_es_veto_duro(self):   # RF-19, C4
        r = self._filtrar("BLOQUEAR_IP", {"ip": "172.20.20.4"})
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]), ("veta", None, True))

    def test_bloquear_un_activo_interno_se_retiene_para_el_humano(self):   # C1
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.10"})
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]), ("veta", "BLOQUEAR_IP", True))

    def test_bloquear_un_dispositivo_de_red_se_retiene(self):
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.1"})
        self.assertEqual((r["accion_final"], r["requiere_humano"]), ("BLOQUEAR_IP", True))
        self.assertEqual(r["impacto"]["nivel"], "alcanza_servicio")

    def test_un_origen_externo_sigue_automatico(self):
        r = self._filtrar("BLOQUEAR_IP", {"ip": "203.0.113.9"})
        self.assertEqual((r["resultado"], r["requiere_humano"]), ("permite", False))

    def test_la_politica_por_actor_es_configurable(self):
        p = {**PERFIL_INV, "continuidad": {**PERFIL_INV["continuidad"],
                                            "actores": {"activo_interno": "automatica_si_confianza"}}}
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.10"}, p=p)
        self.assertEqual((r["resultado"], r["requiere_humano"]), ("permite", False))

    def test_con_politica_permisiva_el_dispositivo_de_red_sigue_protegido_por_su_nivel(self):   # C2
        p = {**PERFIL_INV, "continuidad": {**PERFIL_INV["continuidad"],
                                            "actores": {"dispositivo_red": "automatica_si_confianza"}}}
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.1"}, p=p)
        self.assertTrue(r["requiere_humano"])      # alcanza_servicio -> humano_siempre en este perfil

    def test_la_retencion_mira_la_accion_final_tras_degradar(self):
        # BLOQUEAR_PUERTO degrada a BLOQUEAR_IP; si esa IP es un activo interno, pide humano
        r = self._filtrar("BLOQUEAR_PUERTO", {"puerto": 22, "ip": "192.168.1.10"})
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]),
                         ("degrada", "BLOQUEAR_IP", True))
        self.assertEqual(r["impacto"]["accion_id"], "BLOQUEAR_IP")

    def test_el_resultado_lleva_el_impacto_determinado(self):
        r = self._filtrar("BLOQUEAR_IP", {"ip": "192.168.1.10"})
        self.assertEqual(r["impacto"]["actor"]["nombre"], "puesto")
        self.assertIn("puesto", r["impacto"]["motivo"])

    def test_los_hallazgos_llegan_al_impacto(self):
        h = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        r = self._filtrar("CERRAR_SERVICIO", {"servicio": "ssh"}, hallazgos=h)
        self.assertIsNone(r["accion_final"])       # corta_gestion_si: ssh -> veto duro (RF-19), como siempre
        self.assertTrue(r["impacto"]["servicios_afectados"][0]["abierto"])

    def test_perfil_sin_ips_se_comporta_como_antes(self):   # regresión: las fixtures no declaran IPs
        r = perfil.filtrar(perfil_fx(), "BLOQUEAR_IP", {"ip": "192.168.1.10"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual((r["resultado"], r["accion_final"], r["requiere_humano"]), ("permite", "BLOQUEAR_IP", False))
        self.assertEqual(r["impacto"]["actor"]["tipo"], "desconocido")

    def test_sin_accion_no_lleva_impacto(self):
        self.assertNotIn("impacto", self._filtrar(None, {}))
