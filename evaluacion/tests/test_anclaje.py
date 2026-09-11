import unittest
from evaluacion import anclaje

FILAS = [
    {"id_alerta":"1","etiqueta":"VP","activo":"objetivo-vuln","servicio":"ssh",
     "familia":"acceso_credenciales","origen_ip":"192.168.1.10","regla_id":"5763","mitre":["T1110"]},
    {"id_alerta":"2","etiqueta":"no_soportada","activo":"x","servicio":"y","familia":"plataforma"},
]

class TestAnclaje(unittest.TestCase):
    def test_soportadas(self):
        self.assertEqual([f["id_alerta"] for f in anclaje.soportadas(FILAS)], ["1"])

    def test_medir_con_generador_falso_anclado(self):
        gen = lambda prompt: "Fuerza bruta SSH desde 192.168.1.10 contra objetivo-vuln."
        res = anclaje.medir(FILAS, {}, {}, generador=gen)
        self.assertEqual(len(res), 1)          # solo la soportada
        self.assertEqual(res[0]["justificador"], "llm")
        self.assertTrue(res[0]["anclaje_verificado"])

    def test_resumen_cuenta_anclados(self):
        res = [{"justificador":"llm","anclaje_verificado":True},
               {"justificador":"plantilla","anclaje_verificado":True}]
        r = anclaje.resumen(res)
        self.assertEqual(r["llm_total"], 1)
        self.assertEqual(r["anclados"], 1)
        self.assertEqual(r["degradados"], 1)
        self.assertAlmostEqual(r["pct_anclaje"], 0.5)
        # Test case with only LLM (no degraded) should yield 1.0
        res_solo_llm = [{"justificador":"llm","anclaje_verificado":True}]
        r_solo = anclaje.resumen(res_solo_llm)
        self.assertAlmostEqual(r_solo["pct_anclaje"], 1.0)

class TestAnclajeRAG(unittest.TestCase):
    def test_medir_con_rag_usa_recuperar_fn(self):
        from evaluacion import anclaje
        filas = [{"id_alerta":"1","etiqueta":"VP","activo":"objetivo-vuln","servicio":"ssh",
                  "familia":"acceso_credenciales","origen_ip":"192.168.1.10","regla_id":"5760","mitre":["T1110.001"]}]
        gen = lambda prompt: "Fuerza bruta SSH desde 192.168.1.10 contra objetivo-vuln regla 5760."
        recuperar_fn = lambda alerta, clase: [{"id":"regla-5760","titulo":"5760","texto":"fallo SSH"}]
        res = anclaje.medir(filas, {}, {}, generador=gen, recuperar_fn=recuperar_fn)
        self.assertEqual(res[0]["justificador"], "llm")
        self.assertEqual(res[0]["pasajes_usados"], ["regla-5760"])


class TestAnclajePorClase(unittest.TestCase):
    def test_desglosa_el_anclaje_por_clase(self):
        # La tasa global esconde el caso que importa: aqui el descarte degrada y la amenaza no.
        from evaluacion import anclaje
        res = [{"clase": "vp_intento_acceso", "justificador": "llm"},
               {"clase": "vp_intento_acceso", "justificador": "llm"},
               {"clase": "fp_actividad_legitima", "justificador": "plantilla"},
               {"clase": "fp_actividad_legitima", "justificador": "llm"}]
        d = anclaje.por_clase(res)
        self.assertEqual(d["vp_intento_acceso"]["pct_anclaje"], 1.0)
        self.assertEqual(d["fp_actividad_legitima"]["pct_anclaje"], 0.5)
        self.assertEqual(d["fp_actividad_legitima"]["plantilla"], 1)

    def test_el_resumen_incluye_el_desglose(self):
        from evaluacion import anclaje
        res = [{"clase": "vp_intento_acceso", "justificador": "llm",
                "anclaje_verificado": True, "version_justificador": "llm-3:m"}]
        self.assertIn("por_clase", anclaje.resumen(res))
