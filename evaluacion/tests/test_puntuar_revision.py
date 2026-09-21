import unittest
from evaluacion import puntuar_revision as pr


class TestRespuestas(unittest.TestCase):
    def test_si_no_tolerante(self):
        for v in ("s", "S", "si", "sí", " Sí "):
            self.assertIs(pr.si_no(v), True)
        for v in ("n", "N", "no"):
            self.assertIs(pr.si_no(v), False)
        for v in ("", "  ", "quizá"):
            self.assertIsNone(pr.si_no(v))

    def test_decision_admite_palabra_letra_o_numero(self):
        self.assertEqual(pr.decision("aprobar"), "aprobar")
        self.assertEqual(pr.decision("1"), "aprobar")
        self.assertEqual(pr.decision("R"), "rechazar")
        self.assertEqual(pr.decision("3"), "reclasificar")
        self.assertIsNone(pr.decision(""))


class TestJustificaciones(unittest.TestCase):
    def test_tasa_por_criterio_sobre_las_respondidas(self):
        filas = [
            {"clase_motor": "vp_intento_acceso", "CORRECTA (s/n)": "s", "ANCLADA (s/n)": "s", "COHERENTE (s/n)": "n"},
            {"clase_motor": "fp_admin_legitimo", "CORRECTA (s/n)": "n", "ANCLADA (s/n)": "s", "COHERENTE (s/n)": "s"},
            {"clase_motor": "vp_intento_acceso", "CORRECTA (s/n)": "", "ANCLADA (s/n)": "", "COHERENTE (s/n)": ""},
        ]
        r = pr.puntuar_justificaciones(filas)
        self.assertEqual(r["respondidas"], 2)
        self.assertEqual(r["total"], 3)
        self.assertEqual(r["criterios"]["CORRECTA"], {"si": 1, "n": 2, "tasa": 0.5})
        self.assertEqual(r["criterios"]["ANCLADA"], {"si": 2, "n": 2, "tasa": 1.0})
        self.assertEqual(r["por_clase"]["vp_intento_acceso"]["COHERENTE"]["tasa"], 0.0)


class TestEscalados(unittest.TestCase):
    VERDAD = {"1": "VP", "2": "VP", "3": "FP", "4": "FP", "5": "VP"}

    def test_cruza_la_decision_del_humano_con_la_verdad(self):
        filas = [
            {"id_alerta": "1", "DECISION": "aprobar", "PREGUNTAR_BIEN (s/n)": "s", "INFO_SUFICIENTE (s/n)": "s"},
            {"id_alerta": "2", "DECISION": "rechazar", "PREGUNTAR_BIEN (s/n)": "n", "INFO_SUFICIENTE (s/n)": "n"},
            {"id_alerta": "3", "DECISION": "rechazar", "PREGUNTAR_BIEN (s/n)": "s", "INFO_SUFICIENTE (s/n)": "s"},
            {"id_alerta": "4", "DECISION": "aprobar", "PREGUNTAR_BIEN (s/n)": "s", "INFO_SUFICIENTE (s/n)": ""},
            {"id_alerta": "5", "DECISION": "", "PREGUNTAR_BIEN (s/n)": "", "INFO_SUFICIENTE (s/n)": ""},
        ]
        r = pr.puntuar_escalados(filas, self.VERDAD)
        self.assertEqual(r["respondidas"], 4)
        self.assertEqual(r["cruce"], {"VP": {"aprobar": 1, "rechazar": 1, "reclasificar": 0},
                                      "FP": {"aprobar": 1, "rechazar": 1, "reclasificar": 0}})
        # acierto: aprobar un VP o no ejecutar (rechazar/reclasificar) un FP
        self.assertEqual(r["acierto_humano"], 0.5)
        # el sistema proponía contener en todos: coincidir con él es aprobar
        self.assertEqual(r["acuerdo_con_el_sistema"], 0.5)
        self.assertEqual(r["fp_aprobados"], 1)
        self.assertEqual(r["preguntar_bien"], {"si": 3, "n": 4, "tasa": 0.75})
        self.assertEqual(r["info_suficiente"], {"si": 2, "n": 3, "tasa": 2 / 3})

    def test_sin_respuestas_no_divide_por_cero(self):
        r = pr.puntuar_escalados([{"id_alerta": "1", "DECISION": ""}], self.VERDAD)
        self.assertEqual(r["respondidas"], 0)
        self.assertIsNone(r["acierto_humano"])


class TestLeerHoja(unittest.TestCase):
    def test_salta_la_linea_de_rubrica(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "h.csv")
            with open(ruta, "w", encoding="utf-8-sig") as f:
                f.write('"Criterios: ..."\nn;id_alerta;DECISION\n1;x;aprobar\n')
            self.assertEqual(pr.leer_hoja(ruta), [{"n": "1", "id_alerta": "x", "DECISION": "aprobar"}])


if __name__ == "__main__":
    unittest.main()
