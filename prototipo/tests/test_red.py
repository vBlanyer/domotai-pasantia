import unittest
from prototipo import red

BANCO = {
    "activos": {"web-banking": {"ip": "10.10.0.10", "funcion": "banca", "criticidad": "alta",
                                "servicios_prestados": [443], "depende_de": ["middleware"]},
                "middleware": {"ip": "10.40.0.10", "servicios_prestados": [8443]},
                "taquilla": {"ip": "10.200.0.10", "funcion": "puesto de taquilla", "servicios_prestados": []},
                "mdr-siem": {"ip": "10.100.0.10", "funcion": "consola SOC/MDR", "servicios_prestados": []}},
    "topologia": {"web-banking": {"rol": "host_victima", "ip": "10.10.0.10", "gateway": "fw-core"},
                  "fw-core": {"rol": "firewall_perimetral", "ip": "10.0.0.1", "gateway": "fw-edge"},
                  "fw-edge": {"rol": "firewall_perimetral", "ip": "10.0.0.254"}},
    "red": {"nodos": {"internet": {"tipo": "externo"}, "sw-soc": {"tipo": "switch"}},
            "enlaces": {"fw-edge": "internet", "fw-core": "fw-edge", "web-banking": "fw-core",
                        "middleware": "fw-core", "taquilla": "fw-core", "sw-soc": "fw-core", "mdr-siem": "sw-soc"},
            "zonas": {"DMZ": ["web-banking"], "Core": ["middleware"], "Sucursal": ["taquilla"],
                      "SOC": ["sw-soc", "mdr-siem"]}},
}


class TestRedDelPerfil(unittest.TestCase):
    def test_nodos_de_activos_topologia_y_red(self):
        r = red.red_de(BANCO)
        self.assertEqual(set(r["nodos"]), {"web-banking", "middleware", "taquilla", "mdr-siem",
                                           "fw-core", "fw-edge", "internet", "sw-soc"})
        tipos = {n: v["tipo"] for n, v in r["nodos"].items()}
        self.assertEqual(tipos["internet"], "externo")
        self.assertEqual(tipos["fw-core"], "cortafuegos")
        self.assertEqual(tipos["sw-soc"], "switch")
        self.assertEqual(tipos["web-banking"], "servidor")
        self.assertEqual(tipos["taquilla"], "puesto")
        self.assertEqual(tipos["mdr-siem"], "gestion")
        self.assertEqual(r["nodos"]["web-banking"]["depende_de"], ["middleware"])

    def test_enlaces_y_zonas_en_el_orden_declarado(self):
        r = red.red_de(BANCO)
        self.assertEqual(r["enlaces"]["mdr-siem"], "sw-soc")
        self.assertEqual([z for z, _ in r["zonas"]], ["DMZ", "Core", "Sucursal", "SOC"])
        self.assertEqual(r["nodos"]["web-banking"]["zona"], "DMZ")
        self.assertIsNone(r["nodos"]["fw-core"]["zona"])           # troncal: fuera de las zonas
        self.assertEqual(r["avisos"], [])

    def test_sin_seccion_red_se_reconstruye_desde_la_topologia(self):
        p = {k: v for k, v in BANCO.items() if k != "red"}
        r = red.red_de(p)
        self.assertEqual(r["enlaces"], {"web-banking": "fw-core", "fw-core": "fw-edge"})
        self.assertEqual(r["zonas"], [["Red", ["mdr-siem", "middleware", "taquilla", "web-banking"]]])

    def test_perfil_vacio_da_una_red_vacia(self):
        self.assertEqual(red.red_de({}), {"nodos": {}, "enlaces": {}, "zonas": [["Red", []]], "avisos": []})

    def test_nodo_desconocido_se_avisa_y_se_ignora(self):
        p = {**BANCO, "red": {**BANCO["red"], "enlaces": {**BANCO["red"]["enlaces"], "fantasma": "fw-core"},
                              "zonas": {**BANCO["red"]["zonas"], "DMZ": ["web-banking", "otro"]}}}
        r = red.red_de(p)
        self.assertNotIn("fantasma", r["enlaces"])
        self.assertEqual(dict(r["zonas"])["DMZ"], ["web-banking"])
        self.assertEqual(len(r["avisos"]), 2)

    def test_un_ciclo_se_corta(self):
        p = {**BANCO, "red": {**BANCO["red"], "enlaces": {"fw-edge": "fw-core", "fw-core": "fw-edge"}}}
        r = red.red_de(p)
        self.assertEqual(len(r["enlaces"]), 1)
        self.assertTrue(any("ciclo" in a for a in r["avisos"]))

    def test_nodo_sin_enlace_ni_zona_va_a_sin_ubicar(self):
        p = {**BANCO, "activos": {**BANCO["activos"], "suelto": {"ip": "10.9.9.9"}}}
        r = red.red_de(p)
        self.assertEqual(r["zonas"][-1], [red.SIN_UBICAR, ["suelto"]])
        self.assertEqual(r["nodos"]["suelto"]["zona"], red.SIN_UBICAR)

    def test_nodo_en_dos_zonas_se_avisa_y_solo_en_la_primera(self):
        p = {**BANCO, "red": {**BANCO["red"], "zonas": {"DMZ": ["web-banking"], "Core": ["web-banking", "middleware"]}}}
        r = red.red_de(p)
        self.assertEqual(r["nodos"]["web-banking"]["zona"], "DMZ")
        self.assertEqual(dict(r["zonas"])["DMZ"], ["web-banking"])
        self.assertEqual(dict(r["zonas"])["Core"], ["middleware"])
        self.assertEqual(len(r["avisos"]), 1)
        self.assertTrue(any("ya está en la zona" in a for a in r["avisos"]))


class TestRedMalFormada(unittest.TestCase):
    def _ok(self, seccion):
        perfil = {**{k: v for k, v in BANCO.items() if k != "red"}, "red": seccion}
        r = red.red_de(perfil)
        self.assertTrue(r["avisos"], seccion)
        self.assertIn("web-banking", r["nodos"])
        self.assertIsInstance(r["enlaces"], dict)
        for _, ms in r["zonas"]:
            self.assertTrue(all(isinstance(m, str) for m in ms))
        return r

    def test_seccion_escalar(self):
        r = self._ok("si")
        self.assertEqual(r["enlaces"], {"web-banking": "fw-core", "fw-core": "fw-edge"})   # reconstrucción

    def test_nodos_enlaces_zonas_como_lista(self):
        for clave in ("nodos", "enlaces", "zonas"):
            self._ok({clave: ["a", "b"]})

    def test_nodo_escalar(self):
        self._ok({"nodos": {"internet": "externo"}})

    def test_enlace_con_destino_o_origen_no_hashable(self):
        self._ok({"enlaces": {"web-banking": {"x": 1}}})
        self._ok({"enlaces": {"web-banking": ["fw-core"]}})
        self._ok({"enlaces": {"fw-core": 5}})

    def test_zona_con_valor_escalar_o_miembro_no_str(self):
        self._ok({"zonas": {"DMZ": 7}})
        self._ok({"zonas": {"DMZ": [{"a": 1}, ["b"]]}})

    def test_activo_escalar_y_servicios_normalizados(self):
        perfil = {"activos": {"a": "x", "b": {"servicios_prestados": 443}, "c": {"servicios_prestados": [80, "ssh", {"z": 1}]}}}
        r = red.red_de(perfil)
        self.assertEqual(r["nodos"]["b"]["servicios_prestados"], [443])
        self.assertEqual(r["nodos"]["c"]["servicios_prestados"], [80, "ssh"])
        self.assertIn("a", r["nodos"])

    def test_depende_de_con_entradas_no_hashables(self):
        from prototipo import tablero
        seccion = {"nodos": {"internet": {"tipo": "externo", "depende_de": [["b"], {"x": 1}, "web-banking"]}}}
        r = self._ok(seccion)
        self.assertEqual(r["nodos"]["internet"]["depende_de"], ["web-banking"])
        perfil = {**{k: v for k, v in BANCO.items() if k != "red"}, "red": seccion}
        self.assertIn(["internet", "web-banking"], tablero.estado_red(perfil, [])["dependencias"])

    def test_nombres_de_nodo_y_zona_no_str(self):
        r = self._ok({"nodos": {7: {"tipo": "switch"}}, "zonas": {1: ["web-banking"]}})
        self.assertNotIn(7, r["nodos"])
        self.assertEqual(r["zonas"][0], ["1", ["web-banking"]])
        self.assertEqual(r["nodos"]["web-banking"]["zona"], "1")


if __name__ == "__main__":
    unittest.main()
