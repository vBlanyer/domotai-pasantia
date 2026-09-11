import unittest
from prototipo import revertir

CAT = {
    "BLOQUEAR_IP": {"reversion": "definida", "comando": "iptables -A INPUT -s {ip} -j DROP",
                    "reversion_cmd": "iptables -D INPUT -s {ip} -j DROP", "verificacion": "iptables -L -n | grep {ip}"},
    "MATAR_CONEXION": {"reversion": "transitoria", "comando": "ss -K dst {ip}", "verificacion": "ss -tunap | grep {ip}"},
    "OBS_PROCESOS": {"reversion": "no_aplica", "comando": "ps aux", "verificacion": "salida capturada"},
}


def _registro(accion="BLOQUEAR_IP", params=None, exito=True):
    return {"id_decision": "s7",
            "orden": {"accion_id": accion, "nodo_objetivo": "objetivo-vuln", "nodo_ip": "192.168.1.30",
                      "params": params if params is not None else {"ip": "192.168.1.10"}},
            "ejecucion": {"exito": exito, "idempotente": False}}


class EjecutorFalso:
    """Simula el nodo: la regla existe hasta que llega el -D."""
    def __init__(self, existe=True, falla_reversion=False):
        self.existe, self.falla, self.llamadas = existe, falla_reversion, []
    def __call__(self, nodo_ip, cmd):
        self.llamadas.append(cmd)
        if cmd.startswith("iptables -D"):
            if self.falla:
                return (2, "iptables: Bad rule")
            self.existe = False
            return (0, "")
        if "grep" in cmd:
            return (0, "DROP 192.168.1.10") if self.existe else (1, "")
        return (0, "")


class TestRevertir(unittest.TestCase):
    def test_revierte_desde_la_orden_de_la_traza_y_verifica_que_el_estado_desaparece(self):
        ej = EjecutorFalso()
        r = revertir.revertir(_registro(), CAT, ej, "t1", motivo="FP confirmado")
        self.assertTrue(r["exito"])
        self.assertEqual(r["comando_ejecutado"], "iptables -D INPUT -s 192.168.1.10 -j DROP")
        self.assertEqual(r["tipo"], "reversion"); self.assertEqual(r["id_decision_revertida"], "s7")
        self.assertEqual(r["motivo"], "FP confirmado")
        self.assertIn("grep 192.168.1.10", ej.llamadas[-1])      # la verificacion de la accion, que ahora falla

    def test_si_la_regla_sigue_tras_revertir_no_se_da_por_revertida(self):
        ej = EjecutorFalso(falla_reversion=True)
        r = revertir.revertir(_registro(), CAT, ej, "t1")
        self.assertFalse(r["exito"]); self.assertEqual(r["codigo_salida"], 2)

    def test_una_accion_transitoria_o_de_observacion_no_se_revierte(self):
        for accion in ("MATAR_CONEXION", "OBS_PROCESOS"):
            ej = EjecutorFalso()
            r = revertir.revertir(_registro(accion), CAT, ej, "t1")
            self.assertFalse(r["exito"]); self.assertIsNone(r["comando_ejecutado"])
            self.assertEqual(ej.llamadas, [])                      # no toca el nodo

    def test_params_inseguros_no_llegan_al_nodo(self):
        ej = EjecutorFalso()
        r = revertir.revertir(_registro(params={"ip": "1.2.3.4; rm -rf /"}), CAT, ej, "t1")
        self.assertFalse(r["exito"]); self.assertEqual(ej.llamadas, [])

    def test_una_decision_sin_orden_no_es_reversible(self):
        r = revertir.revertir({"id_decision": "s9", "orden": None, "ejecucion": None}, CAT, EjecutorFalso(), "t1")
        self.assertFalse(r["exito"]); self.assertIn("ninguna orden", r["salida"])

    def test_una_ejecucion_no_exitosa_se_revierte_igual_con_aviso(self):
        ej = EjecutorFalso()
        r = revertir.revertir(_registro(exito=False), CAT, ej, "t1")
        self.assertTrue(r["exito"]); self.assertIn("aviso", r)


if __name__ == "__main__":
    unittest.main()
