"""Identificadores de decisión estructurados: PREFIJO-AAAAMMDD-NNNN (diseno-identificadores-estructurados.md)."""
import datetime
import threading
import unittest

from prototipo.servicio import identificador as idm

UTC = datetime.timezone.utc


def reloj(*fechas):
    it = iter(fechas)
    return lambda: next(it)


D23 = datetime.datetime(2026, 11, 23, 15, 0, tzinfo=UTC)
D24 = datetime.datetime(2026, 11, 24, 0, 5, tzinfo=UTC)


class TestFormato(unittest.TestCase):
    def test_con_prefijo_fecha_y_secuencia(self):
        n = idm.Numerador("BCO", reloj=lambda: D23)
        self.assertEqual([n.siguiente(), n.siguiente()], ["BCO-20261123-0001", "BCO-20261123-0002"])

    def test_sin_prefijo(self):
        self.assertEqual(idm.Numerador(None, reloj=lambda: D23).siguiente(), "20261123-0001")

    def test_la_actividad_propia_lleva_su_propia_secuencia(self):
        n = idm.Numerador("BCO", reloj=lambda: D23)
        self.assertEqual([n.siguiente(), n.siguiente("P"), n.siguiente()],
                         ["BCO-20261123-0001", "BCO-20261123-P0001", "BCO-20261123-0002"])

    def test_la_secuencia_vuelve_a_empezar_cada_dia(self):
        n = idm.Numerador("BCO", reloj=reloj(D23, D23, D24))
        self.assertEqual([n.siguiente(), n.siguiente(), n.siguiente()],
                         ["BCO-20261123-0001", "BCO-20261123-0002", "BCO-20261124-0001"])

    def test_pasa_de_cuatro_cifras_sin_romperse(self):
        n = idm.Numerador("BCO", reloj=lambda: D23, ultimos={("20261123", ""): 9999})
        self.assertEqual(n.siguiente(), "BCO-20261123-10000")

    def test_no_repite_con_varios_hilos(self):
        n, vistos = idm.Numerador("BCO", reloj=lambda: D23), []
        hilos = [threading.Thread(target=lambda: vistos.extend(n.siguiente() for _ in range(200))) for _ in range(5)]
        for h in hilos: h.start()
        for h in hilos: h.join()
        self.assertEqual(len(set(vistos)), 1000)


class TestPrefijo(unittest.TestCase):
    def test_valido_se_normaliza_a_mayusculas(self):
        self.assertEqual(idm.prefijo_de({"prefijo_id": "bco"}), "BCO")
        self.assertEqual(idm.prefijo_de({"prefijo_id": "CLI2"}), "CLI2")

    def test_invalido_o_ausente_queda_sin_prefijo(self):
        for p in (None, "", "BANCO-SUR", "ABCDEFGHI", "B C", "ñ", 42):
            self.assertIsNone(idm.prefijo_de({"prefijo_id": p}), p)
        self.assertIsNone(idm.prefijo_de({}))
        self.assertIsNone(idm.prefijo_de(None))


class TestDesdeLaTraza(unittest.TestCase):
    def test_sigue_desde_el_mayor_del_dia_por_tipo(self):
        regs = [{"id_decision": "BCO-20261123-0007"}, {"id_decision": "BCO-20261123-0041~sup"},
                {"id_decision": "BCO-20261123-P0003"}, {"id_decision": "BCO-20261122-0099"},
                {"id_decision": "s23"}, {"id_decision": "p4"}, {"id_decision": None}, {}]
        n = idm.desde_traza(regs, "BCO", reloj=lambda: D23)
        self.assertEqual([n.siguiente(), n.siguiente("P")], ["BCO-20261123-0042", "BCO-20261123-P0004"])

    def test_otro_dia_empieza_en_uno(self):
        n = idm.desde_traza([{"id_decision": "BCO-20261123-0041"}], "BCO", reloj=lambda: D24)
        self.assertEqual(n.siguiente(), "BCO-20261124-0001")

    def test_una_traza_antigua_con_s_empieza_en_uno(self):
        n = idm.desde_traza([{"id_decision": "s23"}, {"id_decision": "s23~sup"}], None, reloj=lambda: D23)
        self.assertEqual(n.siguiente(), "20261123-0001")

    def test_cambiar_de_prefijo_no_repite_numeros_del_mismo_dia(self):
        n = idm.desde_traza([{"id_decision": "20261123-0005"}], "BCO", reloj=lambda: D23)
        self.assertEqual(n.siguiente(), "BCO-20261123-0006")


if __name__ == "__main__":
    unittest.main()
