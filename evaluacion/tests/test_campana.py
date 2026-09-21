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
            "accion_final":"BLOQUEAR_IP" if amenaza else None,   # como el motor real: sin acción es None
            "impacto":"localizado","requiere_humano":False}

def _procesar_router(fila, *a, **k):
    # FP cuya acción final bloquea al router: el catálogo dice «localizado», el impacto determinado
    # dice «alcanza_servicio». La continuidad debe contar lo que de verdad cortaría.
    return {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0, "accion_final": "BLOQUEAR_IP",
            "impacto": "localizado", "requiere_humano": True,
            "impacto_determinado": {"nivel": "alcanza_servicio"}}

class TestCampana(unittest.TestCase):
    def test_evaluar_produce_las_secciones(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        for k in ("clasificacion_prototipo","baseline","priorizacion","operacion","continuidad","automatizacion","condiciones"):
            self.assertIn(k, res)
        # el prototipo marca las 2 soportadas como amenaza -> 1 VP, 1 FP
        self.assertEqual(res["clasificacion_prototipo"]["matriz"], {"vp":1,"fp":1,"vn":1,"fn":0})

    def test_continuidad_usa_el_impacto_determinado(self):
        res = campana.evaluar(FILAS[1:2], {}, {}, "prueba", None, tabla_prioridad={},
                              con_llm=False, _procesar=_procesar_router)
        self.assertEqual(res["continuidad"]["disruptivas_indebidas"], 1)
        self.assertEqual(res["continuidad"]["retencion_correcta"], 1.0)

    def test_tabla_markdown_menciona_ambos(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        md = campana.tabla_markdown(res)
        self.assertIn("Prototipo", md)
        self.assertIn("Baseline", md)

    def test_automatizacion_cuenta_los_bloqueos_sin_humano(self):
        res = campana.evaluar(FILAS, {}, {}, "prueba", None,
                              tabla_prioridad={"objetivo-vuln":{"VP":4,"FP":1}},
                              con_llm=False, _procesar=_procesar_falso)
        # filas 1 (VP) y 2 (FP) se bloquean sin humano; la 2 es indebida
        self.assertEqual(res["automatizacion"], {"automaticos": 2, "indebidos": 1, "tasa_indebidos": 0.5})
        self.assertIn("Contenciones automáticas (sin humano): 2", campana.tabla_markdown(res))


class TestRafagaEnCampana(unittest.TestCase):
    def test_la_campana_calcula_la_rafaga_antes_de_clasificar(self):
        from evaluacion import campana
        filas = [{"id_alerta": str(i), "etiqueta": "VP", "familia": "acceso_credenciales", "origen_ip": "1.1.1.1",
                  "timestamp": f"2026-09-11T10:00:{i:02d}.000+0000", "activo": "a", "servicio": "ssh",
                  "regla_id": "5760", "nivel_wazuh": 5} for i in range(12)]
        vistas = []
        def _proc(alerta, *a, **k):
            vistas.append(alerta.get("rafaga_60s"))
            return {"clase": "vp_intento_acceso", "prioridad": 3, "confianza": 1.0, "accion_final": None,
                    "impacto": None, "requiere_humano": False, "resultado_filtro": "sin_accion"}
        campana.evaluar(filas, {}, {"activos": {}}, "p", {}, {}, con_llm=False, _procesar=_proc)
        self.assertEqual(vistas, [12] * 12)

