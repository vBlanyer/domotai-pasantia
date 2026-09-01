import os, unittest
from prototipo import conector, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
ORDEN = {"decision_id": "d1", "accion_id": "BLOQUEAR_IP", "nodo_objetivo": "objetivo-vuln",
         "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}, "impacto": "localizado"}

class EjecutorFalso:
    """Simula iptables: la regla no existe hasta que se aplica."""
    def __init__(self): self.aplicada = False; self.llamadas = []
    def __call__(self, nodo_ip, comando):
        self.llamadas.append(comando)
        if "grep" in comando:                       # verificación
            return (0, "DROP ... 192.168.1.10") if self.aplicada else (1, "")
        if "-A INPUT" in comando:                    # aplicar
            self.aplicada = True; return (0, "")
        return (0, "")

class TestConector(unittest.TestCase):
    def test_render_rellena_params(self):
        cmd = conector.render_comando(CAT, "BLOQUEAR_IP", {"ip": "1.2.3.4"})
        self.assertEqual(cmd, "iptables -A INPUT -s 1.2.3.4 -j DROP")

    def test_ejecuta_y_verifica(self):
        ej = EjecutorFalso()
        r = conector.ejecutar_orden(ORDEN, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["exito"])
        self.assertFalse(r["idempotente"])
        self.assertEqual(r["comando_ejecutado"], "iptables -A INPUT -s 192.168.1.10 -j DROP")

    def test_idempotente_si_ya_aplicada(self):
        ej = EjecutorFalso(); ej.aplicada = True     # ya está
        r = conector.ejecutar_orden(ORDEN, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["idempotente"])
        self.assertTrue(r["exito"])
        self.assertNotIn("-A INPUT", " ".join(ej.llamadas))   # NO reejecutó la acción

    def test_params_con_inyeccion_se_rechazan_sin_ejecutar(self):
        ej = EjecutorFalso()
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "1.2.3.4; rm -rf /"}
        r = conector.ejecutar_orden(orden_mala, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertFalse(r["exito"])
        self.assertEqual(ej.llamadas, [])   # el ejecutor NUNCA se llamó
