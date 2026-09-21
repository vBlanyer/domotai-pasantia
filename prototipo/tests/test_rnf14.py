# prototipo/tests/test_rnf14.py
import os, unittest
from prototipo import perfil, catalogo

BASE = os.path.join(os.path.dirname(__file__), "..")
CAT = catalogo.cargar_catalogo(os.path.join(BASE, "catalogo.yml"))
RES = perfil.cargar(os.path.join(BASE, "perfiles", "residencial.yml"))
EMP = perfil.cargar(os.path.join(BASE, "perfiles", "empresarial.yml"))

class TestRNF14(unittest.TestCase):
    def test_misma_accion_alcanza_servicio_diverge_por_perfil(self):
        # BLOQUEAR_PUERTO (alcanza_servicio) contra objetivo-vuln:80, origen externo, confianza alta.
        # Residencial: impacto_alcanza_servicio=automatica_si_confianza -> permite BLOQUEAR_PUERTO.
        # Empresarial: impacto_alcanza_servicio=humano_siempre -> degrada a BLOQUEAR_IP (localizado,
        # automático con confianza alta porque el origen es externo).
        res = perfil.filtrar(RES, "BLOQUEAR_PUERTO", {"puerto":80,"ip":"203.0.113.9"}, CAT, "objetivo-vuln", "http", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_PUERTO", {"puerto":80,"ip":"203.0.113.9"}, CAT, "objetivo-vuln", "http", 1.0)
        self.assertNotEqual(
            (res["resultado"], res["accion_final"]),
            (emp["resultado"], emp["accion_final"]),
            f"los perfiles deberían divergir: res={res}, emp={emp}")

    def test_localizado_sobre_origen_externo_coincide_en_ambos(self):
        # sobre un origen externo, bloquear la IP es automático en los dos perfiles (honesto)
        res = perfil.filtrar(RES, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual(res["resultado"], emp["resultado"])

    def test_bloquear_un_activo_interno_diverge_por_perfil(self):
        # empresarial inventaria el puesto (.10) y exige humano para bloquear lo propio (C1);
        # residencial no tiene inventario con IPs: para él es un origen cualquiera y lo bloquea solo.
        res = perfil.filtrar(RES, "BLOQUEAR_IP", {"ip":"192.168.1.10"}, CAT, "objetivo-vuln", "ssh", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_IP", {"ip":"192.168.1.10"}, CAT, "objetivo-vuln", "ssh", 1.0)
        self.assertEqual((res["resultado"], res["requiere_humano"]), ("permite", False))
        self.assertEqual((emp["resultado"], emp["requiere_humano"]), ("veta", True))
