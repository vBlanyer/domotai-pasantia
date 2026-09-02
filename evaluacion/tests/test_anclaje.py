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
        self.assertAlmostEqual(r["pct_anclaje"], 1.0)
