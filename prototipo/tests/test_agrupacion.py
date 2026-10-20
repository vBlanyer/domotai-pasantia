import os, json, unittest
from datetime import datetime
from prototipo import agrupacion

FX = os.path.join(os.path.dirname(__file__), "fixtures")

def cargar_jsonl(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

ALERTAS = cargar_jsonl("alertas_incidentes.jsonl")


class TestClaveYTS(unittest.TestCase):
    def test_clave_incidente(self):
        a = {"origen_ip": "192.168.1.10", "activo": "objetivo-vuln", "servicio": "ssh", "familia": "acceso_credenciales"}
        self.assertEqual(agrupacion.clave_incidente(a),
                         ("192.168.1.10", "objetivo-vuln", "ssh", "acceso_credenciales"))

    def test_ts_parsea_y_tolera(self):
        self.assertIsNotNone(agrupacion._ts({"timestamp": "2026-08-31T16:48:05.000+0000"}))
        self.assertIsNone(agrupacion._ts({"timestamp": None}))
        self.assertIsNone(agrupacion._ts({"timestamp": "basura"}))
        self.assertIsNone(agrupacion._ts({}))

    def test_representante_es_el_de_mayor_nivel(self):
        a5 = {"id_alerta": "x", "nivel_wazuh": 5}
        a10 = {"id_alerta": "y", "nivel_wazuh": 10}
        self.assertEqual(agrupacion.representante([a5, a10])["id_alerta"], "y")


class TestAgrupar(unittest.TestCase):
    def test_agrupa_rafaga_en_un_incidente(self):
        # ids 1,2,3: misma clave (.10) en segundos -> 1 incidente, conteo 3, representante = la 5763 (nivel 10)
        incs = agrupacion.agrupar([a for a in ALERTAS if a["id_alerta"] in ("1", "2", "3")], ventana_seg=300)
        self.assertEqual(len(incs), 1)
        inc = incs[0]
        self.assertEqual(inc["conteo"], 3)
        self.assertEqual(inc["representante"]["regla_id"], "5763")
        self.assertEqual(inc["reglas"], {"5760": 2, "5763": 1})
        self.assertEqual(inc["clave"]["origen_ip"], "192.168.1.10")

    def test_parte_por_ventana(self):
        # ids 1,2,3 (16:48) + id 4 (17:10, >300s después) -> 2 incidentes de la misma clave
        incs = agrupacion.agrupar([a for a in ALERTAS if a["id_alerta"] in ("1", "2", "3", "4")], ventana_seg=300)
        self.assertEqual(len(incs), 2)

    def test_claves_distintas_son_incidentes_distintos(self):
        # id 1 (.10) y id 5 (.1) -> 2 incidentes
        incs = agrupacion.agrupar([a for a in ALERTAS if a["id_alerta"] in ("1", "5")], ventana_seg=300)
        self.assertEqual(len(incs), 2)

    def test_tolera_alertas_sin_timestamp(self):
        # ids 5,6 misma clave, la 6 sin timestamp -> no lanza; 1 incidente
        incs = agrupacion.agrupar([a for a in ALERTAS if a["id_alerta"] in ("5", "6")], ventana_seg=300)
        self.assertEqual(len(incs), 1)
        self.assertEqual(incs[0]["conteo"], 2)

    def test_todo_el_fixture(self):
        # .10: {1,2,3} y {4} = 2 incidentes; .1: {5,6} = 1 -> 3 incidentes en total
        incs = agrupacion.agrupar(ALERTAS, ventana_seg=300)
        self.assertEqual(len(incs), 3)


class TestZonasMixtas(unittest.TestCase):
    """#7 aplicado a la agrupación: timestamps con zona y sin ella conviven en un mismo lote
    (receptor de red con SIEMs heterogéneos) sin tumbar el daemon y comparando en UTC."""

    def _a(self, ts):
        return {"origen_ip": "192.168.1.10", "activo": "srv", "servicio": "ssh",
                "familia": "acceso_credenciales", "timestamp": ts, "nivel_wazuh": 5}

    def test_ts_normaliza_la_zona_a_utc_naive(self):
        t = agrupacion._ts({"timestamp": "2026-10-20T12:00:00+02:00"})
        self.assertIsNone(t.tzinfo)
        self.assertEqual(t, datetime(2026, 10, 20, 10, 0, 0))

    def test_agrupa_aware_y_naive_sin_romper(self):
        incs = agrupacion.agrupar([self._a("2026-10-20T10:00:00+00:00"),
                                   self._a("2026-10-20T10:00:01")])
        self.assertEqual(len(incs), 1)
        self.assertEqual(incs[0]["conteo"], 2)

    def test_la_ventana_compara_en_utc_no_en_hora_de_pared(self):
        # 12:00+02:00 son las 10:00Z: a 10 s de la naive (UTC asumido) -> mismo incidente,
        # y primera_ts sale en UTC con zona explícita.
        incs = agrupacion.agrupar([self._a("2026-10-20T12:00:00+02:00"),
                                   self._a("2026-10-20T10:00:10")])
        self.assertEqual(len(incs), 1)
        self.assertEqual(incs[0]["primera_ts"], "2026-10-20T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
