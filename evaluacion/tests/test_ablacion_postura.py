import os, unittest
from evaluacion import ablacion_postura as ab
from prototipo import catalogo as catm

CAT = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "..", "prototipo", "catalogo.yml"))
PERFIL = {"origenes_legitimos": ["192.168.1.1"], "rafaga": {"umbral": 9},
          "continuidad": {"umbral_confianza": 0.7, "impacto_localizado": "automatica_si_confianza"}}
POSTURA_REAL = {"nodos": {"objetivo-vuln": [{"servicio": "ssh", "estado": "open"}]}}
SIN_POSTURA = {"nodos": {}}


def _fila(id_alerta, origen, etiqueta, ts, familia="acceso_credenciales"):
    return {"id_alerta": id_alerta, "familia": familia, "origen_ip": origen, "activo": "objetivo-vuln",
            "servicio": "ssh", "regla_id": "5760", "mitre": ["T1110.001"], "etiqueta": etiqueta,
            "timestamp": ts}


class TestGrises(unittest.TestCase):
    def setUp(self):
        self.filas = [
            _fila("atacante", "203.0.113.9", "VP", "2026-09-11T10:00:00"),   # origen no declarado
            _fila("admin", "192.168.1.1", "FP", "2026-09-11T11:00:00"),      # admin declarado, sin ráfaga
            _fila("ruido", None, "no_soportada", "2026-09-11T12:00:00", familia="plataforma"),
        ]

    def test_con_postura_real_no_hay_grises(self):
        # el auditor confirma ssh expuesto -> VP 1.0; el admin -> FP 1.0; nada queda bajo el umbral
        self.assertEqual(ab.grises(self.filas, POSTURA_REAL, PERFIL, CAT, 0.7), [])

    def test_sin_postura_el_ataque_pasa_a_gris(self):
        # sin postura del auditor el determinista duda (0.5); el admin declarado no depende de la postura
        pares = ab.grises(self.filas, SIN_POSTURA, PERFIL, CAT, 0.7)
        self.assertEqual([f["id_alerta"] for f, _ in pares], ["atacante"])
        self.assertEqual(pares[0][1]["confianza"], 0.5)

    def test_no_soportadas_nunca_cuentan_como_grises(self):
        pares = ab.grises(self.filas, SIN_POSTURA, PERFIL, CAT, 0.7)
        self.assertNotIn("ruido", [f["id_alerta"] for f, _ in pares])

    def test_calcula_la_rafaga_como_la_campana(self):
        # Regresión: sin rafaga.contar_en_lote la 6ª regla no actúa y los grises reales desaparecen
        # (así se midió por error un «escalado 0.0»). 9 alertas del admin en un minuto = ráfaga ->
        # VP 0.6 -> gris aun CON postura real.
        rafaga = [_fila(f"r{i}", "192.168.1.1", "VP", f"2026-09-11T10:00:0{i}") for i in range(9)]
        pares = ab.grises(rafaga, POSTURA_REAL, PERFIL, CAT, 0.7)
        self.assertEqual(len(pares), 9)
        self.assertTrue(all(p["confianza"] == 0.6 for _, p in pares))

    def test_no_muta_las_filas_del_llamador(self):
        ab.grises(self.filas, SIN_POSTURA, PERFIL, CAT, 0.7)
        self.assertTrue(all("rafaga_60s" not in f for f in self.filas))


class TestResumen(unittest.TestCase):
    def test_margen_es_lo_que_falla_el_fallback_todo_vp(self):
        pares = [({"etiqueta": "VP"}, {}), ({"etiqueta": "VP"}, {}), ({"etiqueta": "FP"}, {})]
        r = ab.resumen(pares)
        self.assertEqual(r["n"], 3)
        self.assertEqual(r["por_verdad"], {"VP": 2, "FP": 1})
        self.assertEqual(r["aciertos_fallback_vp"], 2)
        self.assertEqual(r["margen_max"], 1)

    def test_sin_grises(self):
        self.assertEqual(ab.resumen([]), {"n": 0, "por_verdad": {}, "aciertos_fallback_vp": 0,
                                          "margen_max": 0})
