import unittest
from prototipo import familias

class TestRegistroFamilias(unittest.TestCase):
    def test_familia_actuar_trae_nivel_y_mitre(self):
        e = familias.registro()["acceso_credenciales"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertIn("T1110", e["mitre"])

    def test_familia_enrutada_trae_ruta(self):
        e = familias.registro()["explotacion_conocida"]
        self.assertEqual(e["nivel"], "triar_y_enrutar")
        self.assertEqual(e["ruta"], "appsec")

    def test_familia_ausente_es_none(self):
        self.assertIsNone(familias.registro().get("plataforma"))

    def test_abuso_de_cuenta_declara_su_clase_de_respuesta(self):
        # Familia nueva (escalada/manipulación de cuentas): 'actuar' y con una CLASE declarada, que es
        # como el registro extiende la taxonomía sin tocar el código del clasificador.
        e = familias.registro()["abuso_de_cuenta"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertEqual(e["clase"], "vp_abuso_cuenta")
        self.assertIn("T1548", e["mitre"])

    def test_integridad_fichero_declara_su_clase(self):
        # 6ª familia (FIM): el evento ES la amenaza (un fichero crítico cambió); 'actuar' con clase propia.
        e = familias.registro()["integridad_fichero"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertEqual(e["clase"], "vp_integridad")
        self.assertIn("T1565", e["mitre"])

    def test_denegacion_servicio_declara_su_clase(self):
        # 7ª familia (DoS/flood): el flujo volumétrico ES la amenaza; 'actuar' con clase propia.
        e = familias.registro()["denegacion_servicio"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertEqual(e["clase"], "vp_denegacion_servicio")
        self.assertIn("T1498", e["mitre"])

    def test_acceso_consumado_declara_su_clase(self):
        # 8ª familia (intrusión exitosa): el atacante ya ENTRÓ (login tras fuerza bruta); 'actuar'.
        e = familias.registro()["acceso_consumado"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertEqual(e["clase"], "vp_acceso_consumado")
        self.assertIn("T1078", e["mitre"])

    def test_exfiltracion_declara_su_clase(self):
        # 9ª familia (exfiltración/C2): un activo interno conecta a un DESTINO malicioso conocido;
        # 'actuar' con clase propia. Estrena la dirección BLOQUEAR_DESTINO (bloquear el egreso).
        e = familias.registro()["exfiltracion"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertEqual(e["clase"], "vp_exfiltracion")
        self.assertIn("T1041", e["mitre"])
        # La amenaza es el DESTINO, no el origen: lo declara el registro para que el clasificador no
        # descarte como FP un origen "legítimo" (el host interno que baliza; revisión Opus, MEDIO).
        self.assertEqual(e["amenaza_en"], "destino")

    def test_malware_declara_su_clase(self):
        # 10ª familia (malware/rootkit): Wazuh (rootcheck+VirusTotal) marca un binario malicioso;
        # 'actuar' con clase propia. Reusa AISLAR_NODO (aislar el host), sin acción nueva.
        e = familias.registro()["malware"]
        self.assertEqual(e["nivel"], "actuar")
        self.assertEqual(e["clase"], "vp_malware")
        self.assertIn("T1014", e["mitre"])

    def test_clase_declarada_debe_ser_texto(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8") as f:
            f.write("mala: { mitre: [T1], nivel: actuar, clase: 123 }\n")   # clase no es texto
            ruta = f.name
        try:
            with self.assertRaises(ValueError):
                familias.cargar_registro(ruta)
        finally:
            os.unlink(ruta)

    def test_triar_y_enrutar_sin_ruta_falla_al_cargar(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8") as f:
            f.write("mala: { mitre: [T1], nivel: triar_y_enrutar }\n")  # sin ruta
            ruta = f.name
        try:
            with self.assertRaises(ValueError):
                familias.cargar_registro(ruta)
        finally:
            os.unlink(ruta)
