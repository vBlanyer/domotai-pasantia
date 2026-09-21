import contextlib, io, json, os, tempfile, unittest
from prototipo import inventario

PERFIL = {"activos": {
    "objetivo-vuln": {"servicios_prestados": [22, 80, 443]},
    "puesto": {"servicios_prestados": []},
    "impresora": {"servicios_prestados": [9100]},
}}
HALLAZGOS = {"nodos": {
    "objetivo-vuln": [{"puerto": 21, "servicio": "ftp", "estado": "open"},
                      {"puerto": 22, "servicio": "ssh", "estado": "open"},
                      {"puerto": 80, "servicio": "http", "estado": "open"}],
    "puesto": [],
    "camara": [{"puerto": 554, "servicio": "rtsp", "estado": "open"}],
}}


class TestReconciliar(unittest.TestCase):
    def setUp(self):
        self.r = inventario.reconciliar(PERFIL, HALLAZGOS)

    def test_abiertos_no_declarados_son_exposicion_no_reconocida(self):
        self.assertEqual(self.r["activos"]["objetivo-vuln"]["abiertos_no_declarados"],
                         [{"puerto": 21, "servicio": "ftp"}])

    def test_declarados_no_abiertos(self):
        self.assertEqual(self.r["activos"]["objetivo-vuln"]["declarados_no_abiertos"], [443])

    def test_escaneado_y_no_inventariado(self):
        self.assertEqual(self.r["no_inventariados"], ["camara"])

    def test_inventariado_y_no_escaneado_no_se_compara(self):   # RNF-07
        self.assertEqual(self.r["no_escaneados"], ["impresora"])
        self.assertNotIn("impresora", self.r["activos"])

    def test_un_activo_que_coincide_no_tiene_discrepancias(self):
        self.assertEqual(self.r["activos"]["puesto"],
                         {"abiertos_no_declarados": [], "declarados_no_abiertos": []})

    def test_puerto_declarado_como_texto_coincide_con_el_abierto(self):   # F6
        # "80" (texto, como puede llegar de un YAML mal tipado) debe cruzar con el 80 (entero)
        # que ve el auditor, igual que ya hace impacto.determinar con servicios_prestados.
        perfil = {"activos": {"objetivo-vuln": {"servicios_prestados": ["22", "80"]}}}
        r = inventario.reconciliar(perfil, HALLAZGOS)
        abiertos_no_declarados = [s["puerto"] for s in r["activos"]["objetivo-vuln"]["abiertos_no_declarados"]]
        self.assertNotIn(80, abiertos_no_declarados)
        self.assertNotIn(22, abiertos_no_declarados)
        self.assertEqual(r["activos"]["objetivo-vuln"]["declarados_no_abiertos"], [])


class TestCLI(unittest.TestCase):
    def test_imprime_el_informe(self):
        with tempfile.TemporaryDirectory() as d:
            rp, rh = os.path.join(d, "p.yml"), os.path.join(d, "h.json")
            with open(rp, "w", encoding="utf-8") as f:
                f.write("activos:\n  objetivo-vuln: { servicios_prestados: [22] }\n")
            with open(rh, "w", encoding="utf-8") as f:
                json.dump(HALLAZGOS, f)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = inventario.main([rp, rh])
        self.assertEqual(rc, 0)
        self.assertIn("objetivo-vuln: 2 abierto(s) no declarado(s)", out.getvalue())
        self.assertIn("ftp/21", out.getvalue())
        self.assertIn("escaneados y no inventariados: camara, puesto", out.getvalue())

    def test_uso_sin_argumentos(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inventario.main([]), 2)


if __name__ == "__main__":
    unittest.main()
