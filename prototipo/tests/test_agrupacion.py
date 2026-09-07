import os, json, unittest
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


if __name__ == "__main__":
    unittest.main()
