"""Valores canónicos de la evaluación (informe, Fase 6): la campaña real sobre el dataset etiquetado,
sin modelo. Un cambio del motor que mueva recall, FP, escalado o priorización tiene que romper aquí,
no descubrirse al regenerar el informe. Se fijan las dos lecturas de la regla de ráfaga: en lote
(ventana ±60 s, la del informe) y causal (solo alertas pasadas, la que ve el daemon en vivo)."""
import json, os, unittest
from evaluacion import campana, cargar, prioridad
from prototipo.motor import perfil as perfilm
from prototipo.accion import catalogo as catm

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")


def _ruta(*partes):
    return os.path.join(RAIZ, *partes)


def _campana(particion, rafaga_causal=False):
    filas = cargar.cargar(_ruta("lab", "dataset", "etiquetado.jsonl"), particion=particion)
    return _evaluar(filas, rafaga_causal)


def _evaluar(filas, rafaga_causal=False):
    with open(_ruta("lab", "campañas", "2026-08-31-evaluacion", "hallazgos.json"), encoding="utf-8") as f:
        hallazgos = json.load(f)
    perfil = perfilm.cargar(_ruta("prototipo", "perfiles", "empresarial.yml"))
    cat = catm.cargar_catalogo(_ruta("prototipo", "catalogo.yml"))
    tabla = prioridad.cargar_esperada(_ruta("evaluacion", "prioridad_esperada.yml"))
    return campana.evaluar(filas, hallazgos, perfil, "empresarial", cat, tabla, con_llm=False,
                           rafaga_causal=rafaga_causal)


def _particion_sin(*fuera):
    filas = cargar.cargar(_ruta("lab", "dataset", "etiquetado.jsonl"), particion="evaluacion")
    return [f for f in filas if not any(x in f["campaña"] for x in fuera)]


class TestCanonicosEnLote(unittest.TestCase):
    # Partición vigente desde el 11/11/2026: n=417, 209 soportadas (ampliación R1 con los ataques lentos + R2).
    def test_particion_de_evaluacion(self):
        r = _campana("evaluacion")
        # Los 61 FN son los ataques lentos desde la IP del administrador: el punto ciego declarado.
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 122, "fp": 9, "vn": 225, "fn": 61})
        self.assertEqual(r["baseline"]["optimo"]["matriz"], {"vp": 170, "fp": 72, "vn": 162, "fn": 13})
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 104 / 417)
        # D1 de la ampliación: el técnico legítimo del proveedor (origen externo) se bloquea solo.
        self.assertEqual((r["automatizacion"]["automaticos"], r["automatizacion"]["indebidos"]), (27, 4))
        self.assertAlmostEqual(r["priorizacion"]["acierto_pm1"], 0.665, places=3)
        self.assertAlmostEqual(r["priorizacion"]["spearman"], 0.227, places=3)

    def test_sin_los_ataques_lentos(self):
        # Desglose del informe: la misma partición sin las dos campañas de ataque lento (n=356).
        filas = _particion_sin("lento")
        r = _evaluar(filas)
        self.assertEqual(len(filas), 356)
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 122, "fp": 9, "vn": 225, "fn": 0})
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 104 / 356)
        self.assertAlmostEqual(r["priorizacion"]["acierto_pm1"], 0.939, places=3)
        self.assertAlmostEqual(r["priorizacion"]["spearman"], 0.808, places=3)

    def test_las_300_alertas_anteriores_no_cambian(self):
        # El resultado de n=300 (antes de la ampliación) se conserva; R2 solo mueve su Spearman (0,935 -> 0,944).
        filas = _particion_sin("lento", "2026-11-11")
        r = _evaluar(filas)
        self.assertEqual(len(filas), 300)
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 87, "fp": 2, "vn": 211, "fn": 0})
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 89 / 300)
        self.assertEqual((r["automatizacion"]["automaticos"], r["automatizacion"]["indebidos"]), (0, 0))
        self.assertAlmostEqual(r["priorizacion"]["acierto_pm1"], 0.981, places=3)
        self.assertAlmostEqual(r["priorizacion"]["spearman"], 0.944, places=3)

    def test_dataset_completo(self):
        r = _campana(None)
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 244, "fp": 18, "vn": 450, "fn": 101})
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 208 / 813)


class TestCanonicosCausales(unittest.TestCase):
    def test_la_rafaga_contada_hacia_atras_pierde_el_arranque_de_una_fuerza_bruta(self):
        # Las 8 primeras alertas de la fuerza bruta desde el origen declarado 192.168.1.1 no llegan
        # al umbral (9) hasta la novena: en vivo salen como FP. Declarado en el informe.
        r = _campana("evaluacion", rafaga_causal=True)
        self.assertEqual(r["clasificacion_prototipo"]["matriz"], {"vp": 114, "fp": 9, "vn": 225, "fn": 69})
        self.assertAlmostEqual(r["clasificacion_prototipo"]["recall"], 0.623, places=3)
        self.assertAlmostEqual(r["operacion"]["tasa_escalado"], 96 / 417)
        self.assertAlmostEqual(r["priorizacion"]["acierto_pm1"], 0.627, places=3)
        self.assertAlmostEqual(r["priorizacion"]["spearman"], 0.182, places=3)


if __name__ == "__main__":
    unittest.main()
