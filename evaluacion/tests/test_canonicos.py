"""Valores canónicos de la evaluación (informe, Fase 6): la campaña real sobre el dataset etiquetado,
sin modelo. Un cambio del motor que mueva recall, FP, escalado o priorización tiene que romper aquí,
no descubrirse al regenerar el informe. Se fijan las dos lecturas de la regla de ráfaga: en lote
(ventana ±60 s, la del informe) y causal (solo alertas pasadas, la que ve el daemon en vivo)."""
import json, os, unittest
from evaluacion import campana, cargar, prioridad
from prototipo import catalogo as catm, perfil as perfilm

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")


def _ruta(*partes):
    return os.path.join(RAIZ, *partes)


def _campana(particion, rafaga_causal=False):
    filas = cargar.cargar(_ruta("lab", "dataset", "etiquetado.jsonl"), particion=particion)
    with open(_ruta("lab", "campañas", "2026-08-31-evaluacion", "hallazgos.json"), encoding="utf-8") as f:
        hallazgos = json.load(f)
    perfil = perfilm.cargar(_ruta("prototipo", "perfiles", "empresarial.yml"))
    cat = catm.cargar_catalogo(_ruta("prototipo", "catalogo.yml"))
    tabla = prioridad.cargar_esperada(_ruta("evaluacion", "prioridad_esperada.yml"))
    return campana.evaluar(filas, hallazgos, perfil, "empresarial", cat, tabla, con_llm=False,
                           rafaga_causal=rafaga_causal)


class TestCanonicosEnLote(unittest.TestCase):
    def test_particion_de_evaluacion(self):
        r = _campana("evaluacion")
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 87, "fp": 2, "vn": 211, "fn": 0})
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 89 / 300)
        self.assertEqual((r["automatizacion"]["automaticos"], r["automatizacion"]["indebidos"]), (0, 0))
        self.assertAlmostEqual(r["priorizacion"]["acierto_pm1"], 0.981, places=3)
        self.assertAlmostEqual(r["priorizacion"]["spearman"], 0.935, places=3)

    def test_dataset_completo(self):
        r = _campana(None)
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 174, "fp": 4, "vn": 422, "fn": 0})
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 178 / 600)


class TestCanonicosCausales(unittest.TestCase):
    def test_la_rafaga_contada_hacia_atras_pierde_el_arranque_de_una_fuerza_bruta(self):
        # Las 8 primeras alertas de la fuerza bruta desde el origen declarado 192.168.1.1 no llegan
        # al umbral (9) hasta la novena: en vivo salen como FP. Declarado en el informe.
        r = _campana("evaluacion", rafaga_causal=True)
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 79, "fp": 2, "vn": 211, "fn": 8})
        self.assertAlmostEqual(r["clasificacion_prototipo"]["recall"], 0.908, places=3)
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 0.27, places=3)
        self.assertAlmostEqual(r["priorizacion"]["acierto_pm1"], 0.906, places=3)
        self.assertAlmostEqual(r["priorizacion"]["spearman"], 0.725, places=3)


if __name__ == "__main__":
    unittest.main()
