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


class TestRevertirConVerificacionExacta(unittest.TestCase):
    def test_revertir_una_ip_prefijo_de_otra_bloqueada_se_da_por_revertida(self):
        import os
        from prototipo import catalogo
        from prototipo.tests.iptables_falso import NodoIptables
        cat = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
        nodo = NodoIptables(drop_input=["192.168.1.11", "192.168.1.110"])
        r = revertir.revertir(_registro(params={"ip": "192.168.1.11"}), cat, nodo, "t")
        self.assertTrue(r["exito"], r)
        self.assertEqual(nodo.reglas["INPUT"], [("DROP", "192.168.1.110")])


class TestCliRevertir(unittest.TestCase):
    """La traza de varias sesiones repite id (cada sesión empieza en s1): se revierte la última
    decisión con ese id, o la que indique --indice, y la reversión se encadena bien."""
    def _traza(self, d):
        import json, os
        from prototipo import traza
        ruta = os.path.join(d, "t.jsonl")
        with open(ruta, "w", encoding="utf-8") as f:
            c = traza.Cadena(f, nombre="t.jsonl", ancla="")
            for ip in ("198.51.100.7", "198.51.100.99"):          # dos sesiones, las dos con s1
                c.escribir({**_registro(params={"ip": ip}), "id_decision": "s1"})
        return ruta

    def _correr(self, ruta, *args):
        import os
        from unittest import mock
        from prototipo import catalogo
        from prototipo.tests.iptables_falso import NodoIptables
        nodo = NodoIptables(drop_input=["198.51.100.7", "198.51.100.99"])
        with mock.patch("prototipo.conector.ejecutor_por_defecto", lambda *a, **k: nodo), \
             mock.patch("builtins.print"):
            rc = revertir._main([ruta, "s1", *args])
        return rc, nodo

    def test_se_revierte_la_ultima_decision_con_ese_id(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rc, nodo = self._correr(self._traza(d))
        self.assertEqual(rc, 0)
        self.assertEqual(nodo.reglas["INPUT"], [("DROP", "198.51.100.7")])

    def test_indice_elige_la_decision_y_ya_revertida_mira_esa(self):
        import tempfile
        from prototipo import traza
        with tempfile.TemporaryDirectory() as d:
            ruta = self._traza(d)
            self._correr(ruta)                                     # revierte la última (índice 1)
            rc, nodo = self._correr(ruta, "--indice", "0")         # la de la sesión anterior, no «ya revertida»
            regs = traza.leer_registros(ruta)
        self.assertEqual(rc, 0)
        self.assertEqual(nodo.reglas["INPUT"], [("DROP", "198.51.100.99")])
        self.assertEqual([r.get("indice_revertido") for r in regs if r.get("tipo") == "reversion"], [1, 0])
        self.assertTrue(traza.verificar(regs)["valida"])

    def test_el_ancla_de_la_reversion_lleva_el_fichero_y_el_recuento(self):
        import tempfile
        from unittest import mock
        from prototipo import traza
        capturas = []
        with tempfile.TemporaryDirectory() as d:
            ruta = self._traza(d)
            with mock.patch.object(traza, "ANCLA_DESTINO", "127.0.0.1:514"), \
                 mock.patch.object(traza, "anclar", lambda nombre, lin, n, h, destino=None, _enviar=None:
                                   capturas.append((nombre, lin, n)) or True):
                self._correr(ruta)
            linaje = traza.linaje_de(traza.leer_registros(ruta))
        self.assertEqual(capturas, [("t.jsonl", linaje, 3)])
