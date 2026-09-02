import unittest
from evaluacion import campana

FILAS = [
    {"id_alerta":"1","etiqueta":"VP","nivel_wazuh":10,"activo":"objetivo-vuln","servicio":"ssh",
     "familia":"acceso_credenciales","timestamp":"t","origen_ip":"192.168.1.10","regla_id":"5763","mitre":[]},
    {"id_alerta":"2","etiqueta":"FP","nivel_wazuh":10,"activo":"objetivo-vuln","servicio":"ssh",
     "familia":"acceso_credenciales","timestamp":"t","origen_ip":"192.168.1.1","regla_id":"5763","mitre":[]},
    {"id_alerta":"3","etiqueta":"no_soportada","nivel_wazuh":3,"activo":"x","servicio":"desconocido",
     "familia":"plataforma","timestamp":"t","origen_ip":None,"regla_id":"502","mitre":[]},
]

def _procesar_falso(fila, *a, **k):
    amenaza = fila["familia"] == "acceso_credenciales"
    return {"clase":"vp_intento_acceso" if amenaza else "no_soportada",
            "prioridad":3 if amenaza else 1,"confianza":1.0,
            "accion_final":"BLOQUEAR_IP" if amenaza else "NINGUNA",
            "impacto":"localizado","requiere_humano":False}

class TestCampana(unittest.TestCase):
    def test_evaluar_produce_las_secciones(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        for k in ("clasificacion_prototipo","baseline","priorizacion","operacion","continuidad","condiciones"):
            self.assertIn(k, res)
        # el prototipo marca las 2 soportadas como amenaza -> 1 VP, 1 FP
        self.assertEqual(res["clasificacion_prototipo"]["matriz"], {"vp":1,"fp":1,"vn":1,"fn":0})

    def test_tabla_markdown_menciona_ambos(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        md = campana.tabla_markdown(res)
        self.assertIn("Prototipo", md)
        self.assertIn("Baseline", md)
