import unittest
from evaluacion import barrido_umbral


def _stub(filas, hall, perfil, nombre, cat, tabla, con_llm=True, **kw):
    # Devuelve métricas canned que dependen del umbral, para comprobar que el barrido lo varía y
    # extrae las columnas correctas. La clasificación (recall/fp) NO depende del umbral.
    u = perfil["continuidad"]["umbral_confianza"]
    return {"operacion": {"tasa_escalado": u},                       # escalado sube con el umbral (modelo de juguete)
            "automatizacion": {"automaticos": int((1 - u) * 100), "indebidos": 5 if u < 0.5 else 0},
            "clasificacion_prototipo": {"recall": 1.0, "tasa_fp": 0.009}}


class TestBarridoUmbral(unittest.TestCase):
    def test_varia_el_umbral_y_recoge_la_curva(self):
        pts = barrido_umbral.barrido([], {}, {"continuidad": {"umbral_confianza": 0.7}}, "p", {}, {},
                                     umbrales=[0.5, 0.9], _evaluar=_stub)
        self.assertEqual([p["umbral"] for p in pts], [0.5, 0.9])
        self.assertEqual(pts[0]["escalado"], 0.5)          # extrae tasa_escalado
        self.assertEqual(pts[1]["escalado"], 0.9)
        self.assertEqual(pts[0]["automaticos"], 50)        # extrae automatizacion
        self.assertIn("indebidos", pts[0])
        self.assertEqual(pts[0]["recall"], 1.0)            # arrastra la clasificación (constante)

    def test_muestra_el_compromiso_mas_auto_mas_indebidos_al_bajar_el_umbral(self):
        pts = barrido_umbral.barrido([], {}, {"continuidad": {"umbral_confianza": 0.7}}, "p", {}, {},
                                     umbrales=[0.2, 0.9], _evaluar=_stub)
        # umbral bajo -> más contención automática, pero aparecen indebidos (el compromiso que mide RF-07)
        self.assertGreater(pts[0]["automaticos"], pts[1]["automaticos"])
        self.assertGreater(pts[0]["indebidos"], pts[1]["indebidos"])

    def test_no_muta_el_perfil_original(self):
        perfil = {"continuidad": {"umbral_confianza": 0.7, "impacto_localizado": "automatica_si_confianza"}}
        barrido_umbral.barrido([], {}, perfil, "p", {}, {}, umbrales=[0.1, 0.9], _evaluar=_stub)
        self.assertEqual(perfil["continuidad"]["umbral_confianza"], 0.7)            # intacto
        self.assertEqual(perfil["continuidad"]["impacto_localizado"], "automatica_si_confianza")  # resto intacto

    def test_tabla_markdown_lista_los_puntos(self):
        pts = [{"umbral": 0.7, "escalado": 0.297, "automaticos": 0, "indebidos": 0, "recall": 1.0, "tasa_fp": 0.009}]
        md = barrido_umbral.tabla_markdown(pts, perfil="empresarial", n=300)
        self.assertIn("0.7", md)
        self.assertIn("umbral", md.lower())
        self.assertIn("indebidos", md.lower())


if __name__ == "__main__":
    unittest.main()
