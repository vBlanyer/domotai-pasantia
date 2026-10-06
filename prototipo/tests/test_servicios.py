import unittest
from prototipo import servicios

PERFIL = {"activos": {
    "web": {"criticidad": "alta", "servicios_prestados": [443, {"puerto": 80, "criticidad": "media"},
                                                          {"puerto": 22, "servicio": "ssh", "rol": "gestion"}]},
    "db":  {"criticidad": "critica", "servicios_prestados": [1521]},
}}
HALLAZGOS = {"nodos": {"web": [{"puerto": 443, "servicio": "https", "estado": "open"}]}}


class TestNormalizar(unittest.TestCase):
    def test_entero_hereda_criticidad_del_activo(self):
        self.assertEqual(servicios.normalizar([443], "alta"),
                         [{"puerto": 443, "servicio": None, "criticidad": "alta", "rol": None}])

    def test_dict_con_criticidad_propia_y_fallback(self):
        n = servicios.normalizar([{"puerto": 80, "criticidad": "media"}, {"puerto": 22}], "alta")
        self.assertEqual(n[0]["criticidad"], "media")
        self.assertEqual(n[1]["criticidad"], "alta")   # sin criticidad -> hereda del activo

    def test_puerto_texto_se_normaliza_a_entero(self):
        self.assertEqual(servicios.normalizar(["80"], "media")[0]["puerto"], 80)


class TestPuertosDeclarados(unittest.TestCase):
    def test_mezcla_entero_y_dict(self):
        self.assertEqual(servicios.puertos_declarados(PERFIL, "web"), {443, 80, 22})

    def test_dict_sin_puerto_se_ignora(self):
        p = {"activos": {"x": {"servicios_prestados": [443, {"criticidad": "alta"}]}}}
        self.assertEqual(servicios.puertos_declarados(p, "x"), {443})

    def test_activo_sin_servicios(self):
        self.assertEqual(servicios.puertos_declarados({"activos": {"x": {}}}, "x"), set())


class TestCriticidadServicio(unittest.TestCase):
    def test_servicio_declarado_por_nombre_usa_su_criticidad(self):
        p = {"activos": {"web": {"criticidad": "alta", "servicios_prestados": [
            {"puerto": 80, "servicio": "http", "criticidad": "media"},
            {"puerto": 443, "servicio": "https", "criticidad": "alta"}]}}}
        self.assertEqual(servicios.criticidad_servicio(p, "web", "http"), "media")
        self.assertEqual(servicios.criticidad_servicio(p, "web", "https"), "alta")

    def test_nombre_hereda_cuando_el_servicio_no_declara_criticidad(self):
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "web", "ssh"), "alta")   # ssh hereda alta

    def test_por_puerto_via_hallazgos(self):
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "web", "https", HALLAZGOS), "alta")

    def test_fallback_al_activo_si_no_empareja(self):
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "db", "desconocido"), "critica")

    def test_sin_servicio_cae_al_activo(self):
        self.assertEqual(servicios.criticidad_servicio(PERFIL, "db", None), "critica")


if __name__ == "__main__":
    unittest.main()
