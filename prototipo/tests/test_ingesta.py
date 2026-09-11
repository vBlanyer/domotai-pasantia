import os, json, unittest
from prototipo import ingesta, adaptador_wazuh

FX = os.path.join(os.path.dirname(__file__), "fixtures")

def j(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read().strip())

CAMPOS = {"id_alerta", "timestamp", "campaña", "fuente", "activo", "servicio",
          "familia", "origen_ip", "mitre", "evento_crudo", "nivel_wazuh", "regla_id"}


class TestNormalizarWazuh(unittest.TestCase):
    def test_alerta_wazuh_normaliza(self):
        reg = ingesta.normalizar(j("alerta_cruda_wazuh.json"), adaptador_wazuh.adaptador("c"))
        self.assertEqual(set(reg), CAMPOS)
        self.assertEqual(reg["activo"], "objetivo-vuln")
        self.assertEqual(reg["servicio"], "ssh")
        self.assertEqual(reg["familia"], "acceso_credenciales")
        self.assertIsInstance(reg["mitre"], list)
        self.assertEqual(reg["nivel_wazuh"], 5)
        self.assertIn("Failed password", reg["evento_crudo"])
        self.assertEqual(reg["campaña"], "c")

    def test_resuelve_activo_sin_agente(self):
        # RF-16: el activo sale de predecoder.hostname / location, nunca del agent.id 000
        reg = ingesta.normalizar(j("alerta_cruda_wazuh.json"), adaptador_wazuh.adaptador())
        self.assertEqual(reg["activo"], "objetivo-vuln")
        self.assertNotEqual(reg["activo"], "000")


class TestTolerancia(unittest.TestCase):
    def test_campos_ausentes_no_rompe_ni_infiere(self):
        # RNF-07: tolera campos ausentes, no lanza, no inventa
        reg = ingesta.normalizar({}, adaptador_wazuh.adaptador())
        self.assertEqual(reg["mitre"], [])
        self.assertIsNone(reg["origen_ip"])
        self.assertIsNone(reg["regla_id"])
        self.assertIsNone(reg["id_alerta"])
        faltan = ingesta.campos_ausentes(reg)
        self.assertIn("origen_ip", faltan)
        self.assertIn("regla_id", faltan)
        self.assertIn("id_alerta", faltan)

    def test_campos_ausentes_vacio_cuando_completo(self):
        reg = ingesta.normalizar(j("alerta_cruda_wazuh.json"), adaptador_wazuh.adaptador())
        self.assertEqual(ingesta.campos_ausentes(reg), [])


class TestIngerirFichero(unittest.TestCase):
    def test_linea_corrupta_se_salta(self):
        regs = ingesta.ingerir_fichero(os.path.join(FX, "alertas_crudas.jsonl"),
                                       adaptador_wazuh.adaptador("lote"))
        self.assertEqual(len(regs), 1)          # solo la válida; vacía y corrupta se saltan
        self.assertEqual(regs[0]["activo"], "objetivo-vuln")


class TestAgnostico(unittest.TestCase):
    def test_adaptador_intercambiable(self):
        # RNF-06: el núcleo no sabe de Wazuh; un adaptador de otra fuente funciona igual
        def adaptador_falso(cruda):
            return {"id_alerta": cruda.get("uuid"), "activo": cruda.get("host"),
                    "fuente": "empresa-x"}
        reg = ingesta.normalizar({"uuid": "9", "host": "srv1"}, adaptador_falso)
        self.assertEqual(reg, {"id_alerta": "9", "activo": "srv1", "fuente": "empresa-x"})


if __name__ == "__main__":
    unittest.main()


class TestTelemetriaPropia(unittest.TestCase):
    def test_las_anclas_de_la_traza_no_son_alertas(self):
        # Sin esto: ancla -> alerta -> decision -> ancla -> ... (medido: 14 registros por un ataque).
        from prototipo import adaptador_wazuh
        cruda = {"id": "x", "rule": {"id": "100100", "level": 3, "groups": ["triaje"]},
                 "predecoder": {"hostname": "triaje", "program_name": "triaje-ancla"},
                 "full_log": "fichero=t.jsonl registros=3 hash=abc"}
        self.assertIsNone(ingesta.normalizar(cruda, adaptador_wazuh.adaptador("c")))

    def test_ingerir_fichero_salta_la_telemetria_propia(self):
        import json, os, tempfile
        from prototipo import adaptador_wazuh
        ruta = tempfile.mktemp(suffix=".json")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "1", "rule": {"id": "100100", "groups": ["triaje"]}}) + "\n")
            f.write(json.dumps({"id": "2", "rule": {"id": "5760", "groups": ["sshd", "authentication_failed"]},
                                "data": {"srcip": "1.2.3.4"}}) + "\n")
        try:
            regs = ingesta.ingerir_fichero(ruta, adaptador_wazuh.adaptador("c"))
        finally:
            os.unlink(ruta)
        self.assertEqual([r["id_alerta"] for r in regs], ["2"])

