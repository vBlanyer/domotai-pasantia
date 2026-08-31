# prototipo/tests/test_rnf14.py
import os, unittest
from prototipo import perfil, catalogo

BASE = os.path.join(os.path.dirname(__file__), "..")
CAT = catalogo.cargar_catalogo(os.path.join(BASE, "catalogo.yml"))
RES = perfil.cargar(os.path.join(BASE, "perfiles", "residencial.yml"))
EMP = perfil.cargar(os.path.join(BASE, "perfiles", "empresarial.yml"))

class TestRNF14(unittest.TestCase):
    def test_misma_accion_alcanza_servicio_diverge_por_perfil(self):
        # BLOQUEAR_PUERTO (alcanza_servicio) contra servidor-web:443, confianza alta.
        # Residencial: impacto_alcanza_servicio=automatica_si_confianza -> permite BLOQUEAR_PUERTO.
        # Empresarial: excepción 443 nunca_automatica -> degrada a BLOQUEAR_IP.
        res = perfil.filtrar(RES, "BLOQUEAR_PUERTO", {"puerto":443,"ip":"203.0.113.9"}, CAT, "servidor-web", "https", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_PUERTO", {"puerto":443,"ip":"203.0.113.9"}, CAT, "servidor-web", "https", 1.0)
        self.assertNotEqual(
            (res["resultado"], res["accion_final"]),
            (emp["resultado"], emp["accion_final"]),
            f"los perfiles deberían divergir: res={res}, emp={emp}")

    def test_localizado_coincide_en_ambos(self):
        # sobre la acción localizada del laboratorio real, los perfiles COINCIDEN (honesto)
        res = perfil.filtrar(RES, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "servidor-web", "ssh", 1.0)
        emp = perfil.filtrar(EMP, "BLOQUEAR_IP", {"ip":"1.2.3.4"}, CAT, "servidor-web", "ssh", 1.0)
        self.assertEqual(res["resultado"], emp["resultado"])
