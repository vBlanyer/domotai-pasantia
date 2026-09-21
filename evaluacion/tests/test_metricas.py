# evaluacion/tests/test_metricas.py
import unittest
from evaluacion import metricas as m

class TestClasificacion(unittest.TestCase):
    def test_matriz_y_derivadas(self):
        # 8 VP, 2 FP, 180 VN, 2 FN
        pred  = [True]*8 + [True]*2 + [False]*180 + [False]*2
        verd  = [True]*8 + [False]*2 + [False]*180 + [True]*2
        mat = m.matriz(pred, verd)
        self.assertEqual(mat, {"vp":8,"fp":2,"vn":180,"fn":2})
        self.assertAlmostEqual(m.precision(mat), 8/10)
        self.assertAlmostEqual(m.recall(mat), 8/10)
        self.assertAlmostEqual(m.f1(mat), 2*(0.8*0.8)/(0.8+0.8))
        self.assertAlmostEqual(m.tasa_fp(mat), 2/182)

    def test_denominador_cero_es_nd(self):
        mat = {"vp":0,"fp":0,"vn":5,"fn":0}
        self.assertEqual(m.precision(mat), "n/d")   # 0/(0+0)
        self.assertEqual(m.recall(mat), "n/d")

class TestOperacion(unittest.TestCase):
    def test_cobertura_y_tasa(self):
        self.assertAlmostEqual(m.cobertura(["vp_intento_acceso","no_soportada","fp_x"]), 2/3)
        self.assertAlmostEqual(m.tasa([True, False, True, True]), 3/4)

    def test_prioridad_pm1(self):
        self.assertAlmostEqual(m.acierto_prioridad([4,3,1],[4,4,2]), 1.0)  # todos dentro de ±1
        self.assertAlmostEqual(m.acierto_prioridad([4,1],[4,4]), 1/2)      # el segundo se pasa

    def test_spearman(self):
        self.assertAlmostEqual(m.spearman([1,2,3],[1,2,3]), 1.0)
        self.assertAlmostEqual(m.spearman([1,2,3],[3,2,1]), -1.0)
        self.assertEqual(m.spearman([5],[5]), "n/d")

class TestContinuidad(unittest.TestCase):
    def test_disruptiva_sobre_fp_y_retencion(self):
        regs = [
            {"impacto":"alcanza_servicio","etiqueta":"FP","requiere_humano":True},   # disruptiva indebida, retenida
            {"impacto":"alcanza_servicio","etiqueta":"FP","requiere_humano":False},  # disruptiva indebida, NO retenida
            {"impacto":"localizado","etiqueta":"FP","requiere_humano":True},         # no disruptiva
            {"impacto":"alcanza_servicio","etiqueta":"VP","requiere_humano":False},  # sobre VP, no cuenta
        ]
        r = m.continuidad(regs)
        self.assertEqual(r["disruptivas_indebidas"], 2)
        self.assertAlmostEqual(r["retencion_correcta"], 1/2)

class TestBloqueosAutomaticosIndebidos(unittest.TestCase):
    def test_cuenta_los_automaticos_sobre_fp_y_propia_sea_cual_sea_el_impacto(self):
        regs = [
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "FP", "impacto": "localizado"},      # indebido
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "PROPIA", "impacto": "localizado"},  # indebido
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "VP", "impacto": "localizado"},      # correcto
            {"accion_final": "BLOQUEAR_IP", "requiere_humano": True, "etiqueta": "FP", "impacto": "localizado"},       # lo retuvo el humano
            {"accion_final": None, "requiere_humano": False, "etiqueta": "FP", "impacto": "ninguno"},                  # sin acción
        ]
        self.assertEqual(m.bloqueos_automaticos_indebidos(regs),
                         {"automaticos": 3, "indebidos": 2, "tasa_indebidos": 2 / 3})

    def test_sin_automaticos_la_tasa_es_nd(self):
        self.assertEqual(m.bloqueos_automaticos_indebidos([]),
                         {"automaticos": 0, "indebidos": 0, "tasa_indebidos": "n/d"})

    def test_cubre_el_punto_ciego_de_continuidad(self):
        # un bloqueo localizado indebido no es «disruptivo» para continuidad(); para esta métrica sí cuenta
        regs = [{"accion_final": "BLOQUEAR_IP", "requiere_humano": False, "etiqueta": "FP", "impacto": "localizado"}]
        self.assertEqual(m.continuidad(regs)["disruptivas_indebidas"], 0)
        self.assertEqual(m.bloqueos_automaticos_indebidos(regs)["indebidos"], 1)
