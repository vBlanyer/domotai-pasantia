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
