import unittest
from prototipo import rafaga, arbol


def _a(origen, seg, regla="5760"):
    return {"origen_ip": origen, "timestamp": f"2026-09-11T10:00:{seg:02d}.000+0000", "regla_id": regla}


class TestLote(unittest.TestCase):
    def test_cuenta_las_del_mismo_origen_en_la_ventana_incluida_ella(self):
        lote = [_a("a", 0), _a("a", 10), _a("a", 50), _a("b", 12), _a("a", 59)]
        rafaga.contar_en_lote(lote, ventana_s=60)
        self.assertEqual([x[rafaga.CAMPO] for x in lote], [4, 4, 4, 1, 4])

    def test_fuera_de_la_ventana_no_cuenta(self):
        lote = [_a("a", 0), {"origen_ip": "a", "timestamp": "2026-09-11T10:05:00.000+0000"}]
        rafaga.contar_en_lote(lote, ventana_s=60)
        self.assertEqual([x[rafaga.CAMPO] for x in lote], [1, 1])

    def test_sin_origen_o_sin_tiempo_vale_uno(self):
        lote = [{"origen_ip": None, "timestamp": "2026-09-11T10:00:00"}, {"origen_ip": "a", "timestamp": "x"}]
        rafaga.contar_en_lote(lote)
        self.assertEqual([x[rafaga.CAMPO] for x in lote], [1, 1])


class TestVentana(unittest.TestCase):
    def test_desliza_con_el_reloj_de_las_alertas(self):
        v = rafaga.Ventana(60)
        self.assertEqual(v.registrar(_a("a", 0)), 1)
        self.assertEqual(v.registrar(_a("a", 30)), 2)
        self.assertEqual(v.registrar({"origen_ip": "a", "timestamp": "2026-09-11T10:01:29.000+0000"}), 2)  # la de :00 salio (89 s); la de :30 queda (59 s)
        self.assertEqual(v.contar("a"), 2); self.assertEqual(v.contar("b"), 0)


class TestArbol(unittest.TestCase):
    def _datos(self):
        return ([{"x": i, "c": "u", "etiqueta": "VP"} for i in range(10, 20)]
                + [{"x": i, "c": "u", "etiqueta": "FP"} for i in range(0, 10)]
                + [{"x": 100, "c": "v", "etiqueta": "FP"} for _ in range(4)])

    def test_aprende_un_umbral_y_una_categoria(self):
        m = arbol.entrenar(self._datos(), ["x", "c"], max_prof=3, min_hoja=2)
        self.assertEqual(arbol.predecir(m, {"x": 15, "c": "u"}), "VP")
        self.assertEqual(arbol.predecir(m, {"x": 3, "c": "u"}), "FP")
        self.assertEqual(arbol.predecir(m, {"x": 100, "c": "v"}), "FP")
        self.assertIn("si ", arbol.a_texto(m))

    def test_respeta_la_profundidad_y_la_hoja_minima(self):
        m = arbol.entrenar(self._datos(), ["x", "c"], max_prof=1, min_hoja=2)
        self.assertLessEqual(arbol.profundidad(m), 1)
        m2 = arbol.entrenar(self._datos(), ["x"], max_prof=5, min_hoja=30)   # no cabe ningun corte
        self.assertTrue(m2["hoja"])

    def test_un_conjunto_puro_es_una_hoja(self):
        m = arbol.entrenar([{"x": 1, "etiqueta": "VP"}] * 5, ["x"])
        self.assertTrue(m["hoja"]); self.assertEqual(m["clase"], "VP")


if __name__ == "__main__":
    unittest.main()
