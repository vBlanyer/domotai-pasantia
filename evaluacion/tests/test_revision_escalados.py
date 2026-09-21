import csv
import os
import tempfile
import unittest
from evaluacion import revision_escalados as re_


def _par(i, etiqueta, actor, confianza=1.0):
    fila = {"id_alerta": str(i), "etiqueta": etiqueta, "activo": "objetivo-vuln",
            "origen_ip": "192.168.1.10", "servicio": "ssh", "regla_id": "5760"}
    traza = {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": confianza,
             "justificacion": "texto", "accion_propuesta": "BLOQUEAR_IP", "accion_final": "BLOQUEAR_IP",
             "impacto": "localizado", "resultado_filtro": "veta", "requiere_humano": True,
             "justificacion_estructurada": {"tecnica_mitre": ["T1110.001"], "accion_sugerida": "BLOQUEAR_IP"},
             "impacto_determinado": {"actor": {"tipo": actor}, "motivo": f"bloquea a {actor}"}}
    return fila, traza


# 20 VP del router (conf 0.6), 67 VP del puesto, 2 FP: la composición real del 21/09.
POBLACION = ([_par(i, "VP", "dispositivo_red", 0.6) for i in range(20)]
             + [_par(100 + i, "VP", "activo_interno") for i in range(67)]
             + [_par(200 + i, "FP", "activo_interno") for i in range(2)])


class TestMuestra(unittest.TestCase):
    def test_incluye_todos_los_fp_y_reparte_el_resto_a_partes_iguales(self):
        m = re_.muestra_estratificada(POBLACION, n=24, semilla=1)
        self.assertEqual(len(m), 24)
        estratos = [re_.estrato(f, t) for f, t in m]
        self.assertEqual(estratos.count("FP"), 2)
        self.assertEqual(estratos.count("VP · dispositivo_red"), 11)
        self.assertEqual(estratos.count("VP · activo_interno"), 11)

    def test_estrato_pequeno_cede_su_cupo(self):
        pob = [_par(i, "VP", "dispositivo_red") for i in range(3)] + [_par(10 + i, "VP", "activo_interno") for i in range(30)]
        estratos = [re_.estrato(f, t) for f, t in re_.muestra_estratificada(pob, n=12, semilla=1)]
        self.assertEqual(estratos.count("VP · dispositivo_red"), 3)
        self.assertEqual(estratos.count("VP · activo_interno"), 9)

    def test_es_reproducible_y_sin_repetidos(self):
        a = [f["id_alerta"] for f, _ in re_.muestra_estratificada(POBLACION, n=24, semilla=7)]
        b = [f["id_alerta"] for f, _ in re_.muestra_estratificada(POBLACION, n=24, semilla=7)]
        self.assertEqual(a, b)
        self.assertEqual(len(set(a)), 24)

    def test_n_mayor_que_la_poblacion_devuelve_todo(self):
        self.assertEqual(len(re_.muestra_estratificada(POBLACION, n=500, semilla=1)), len(POBLACION))

    def test_el_orden_mezcla_los_estratos(self):
        # Si la hoja fuera por bloques, el revisor aprendería el patrón en vez de juzgar cada caso.
        estratos = [re_.estrato(f, t) for f, t in re_.muestra_estratificada(POBLACION, n=24, semilla=1)]
        self.assertNotEqual(estratos, sorted(estratos))


class TestHoja(unittest.TestCase):
    def test_la_hoja_es_ciega_y_muestra_lo_que_ve_el_analista(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "h.csv")
            re_.escribir_hoja(POBLACION[:3], ruta)
            with open(ruta, encoding="utf-8-sig") as f:
                filas = list(csv.reader(f, delimiter=";"))
        cabecera = filas[1]
        self.assertNotIn("verdad", " ".join(cabecera).lower())
        self.assertNotIn("etiqueta", " ".join(cabecera).lower())
        for col in ("DECISION", "CLASE_NUEVA", "PREGUNTAR_BIEN (s/n)", "INFO_SUFICIENTE (s/n)", "comentario"):
            self.assertIn(col, cabecera)
        texto = filas[2][cabecera.index("lo_que_ve_el_analista")]
        self.assertIn("Validación humana requerida", texto)
        self.assertIn("Consecuencia: bloquea a dispositivo_red", texto)
        self.assertEqual(len(filas), 2 + 3)


if __name__ == "__main__":
    unittest.main()
