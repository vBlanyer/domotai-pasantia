import json, os, unittest, yaml
from prototipo import analisis

FX = os.path.join(os.path.dirname(__file__), "fixtures")
def cargar_json(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.loads(f.read().strip())
def cargar_yaml(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return yaml.safe_load(f)

class TestEnriquecer(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")
        self.hallazgos = cargar_json("hallazgos.json")
        self.perfil = cargar_yaml("perfil.yml")

    def test_postura_expuesta_para_ssh_en_objetivo(self):
        ctx = analisis.enriquecer(self.alerta, self.hallazgos, self.perfil)
        self.assertTrue(ctx["postura"]["expuesto"])

    def test_criticidad_del_perfil(self):
        ctx = analisis.enriquecer(self.alerta, self.hallazgos, self.perfil)
        self.assertEqual(ctx["criticidad"], "alta")

    def test_activo_desconocido_criticidad_media(self):
        a = dict(self.alerta); a["activo"] = "fantasma"
        ctx = analisis.enriquecer(a, self.hallazgos, self.perfil)
        self.assertEqual(ctx["criticidad"], "media")

    def test_marca_origen_legitimo_segun_el_perfil(self):
        perfil = dict(self.perfil); perfil["origenes_legitimos"] = ["192.168.1.1"]
        a = dict(self.alerta); a["origen_ip"] = "192.168.1.1"
        self.assertTrue(analisis.enriquecer(a, self.hallazgos, perfil)["origen_legitimo"])
        a2 = dict(self.alerta); a2["origen_ip"] = "192.168.1.10"
        self.assertFalse(analisis.enriquecer(a2, self.hallazgos, perfil)["origen_legitimo"])

    def test_sin_origenes_legitimos_el_flag_es_falso(self):
        ctx = analisis.enriquecer(self.alerta, self.hallazgos, self.perfil)
        self.assertFalse(ctx["origen_legitimo"])

class TestClasificar(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")

    def test_servicio_expuesto_es_vp_intento_confianza_alta(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 1.0)

    def test_servicio_no_expuesto_es_fp_exposicion_inexistente(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": False}, "criticidad": "media"})
        self.assertEqual(r["clase"], "fp_exposicion_inexistente")

    def test_postura_gris_es_vp_intento_confianza_baja(self):
        r = analisis.clasificar(self.alerta, {"postura": None, "criticidad": "media"})
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 0.5)

    def test_familia_plataforma_es_no_soportada(self):
        a = dict(self.alerta); a["familia"] = "plataforma"
        r = analisis.clasificar(a, {"postura": None, "criticidad": "media"})
        self.assertEqual(r["clase"], "no_soportada")

    def test_origen_legitimo_es_fp_actividad_legitima(self):
        # RF-03: un admin legítimo es FP aunque el servicio esté expuesto (precede a la postura)
        r = analisis.clasificar(self.alerta, {"origen_legitimo": True,
                                              "postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertEqual(r["clase"], "fp_actividad_legitima")
        self.assertEqual(r["confianza"], 1.0)

    def test_sin_flag_legitimo_no_cambia(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertEqual(r["clase"], "vp_intento_acceso")

    def test_prioridad_es_entero_1_a_4(self):
        r = analisis.clasificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"})
        self.assertIn(r["prioridad"], (1, 2, 3, 4))

class TestJustificar(unittest.TestCase):
    def setUp(self):
        self.alerta = cargar_json("alerta_vp.json")

    def test_cita_campos_reales(self):
        txt = analisis.justificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"}, "vp_intento_acceso")
        self.assertIn("5760", txt)            # regla_id
        self.assertIn("192.168.1.10", txt)     # origen_ip
        self.assertIn("objetivo-vuln", txt)    # activo
        self.assertIn("ssh", txt)              # servicio

    def test_menciona_confirmacion_del_auditor(self):
        txt = analisis.justificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"}, "vp_intento_acceso")
        self.assertIn("confirma", txt.lower())

    def test_enriquece_con_otros_servicios_expuestos(self):
        ctx = {"postura": {"expuesto": True, "servicios_abiertos": ["ssh", "telnet"]}, "criticidad": "alta"}
        txt = analisis.justificar(self.alerta, ctx, "vp_intento_acceso")
        self.assertIn("también expone", txt)
        self.assertIn("telnet", txt)

    def test_sin_otros_servicios_no_anade_ruido(self):
        txt = analisis.justificar(self.alerta, {"postura": {"expuesto": True}, "criticidad": "alta"}, "vp_intento_acceso")
        self.assertNotIn("también expone", txt)


class TestRafaga(unittest.TestCase):
    """Sexta regla: una rafaga es ataque venga de donde venga; desde el origen declarado, con
    confianza reducida para que un humano confirme. Sin umbral en el perfil no actua."""
    ALERTA = {"familia": "acceso_credenciales", "origen_ip": "192.168.1.1", "activo": "objetivo-vuln",
              "servicio": "ssh", "regla_id": "5760"}
    HALL = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
    PERFIL = {"origenes_legitimos": ["192.168.1.1"], "rafaga": {"umbral": 9}, "activos": {}}

    def test_rafaga_desde_el_origen_declarado_es_amenaza_con_confianza_baja(self):
        a = dict(self.ALERTA, rafaga_60s=12)
        r = analisis.clasificar(a, analisis.enriquecer(a, self.HALL, self.PERFIL))
        self.assertEqual(r["clase"], "vp_intento_acceso"); self.assertEqual(r["confianza"], 0.6)

    def test_sin_rafaga_el_origen_declarado_sigue_siendo_fp(self):
        a = dict(self.ALERTA, rafaga_60s=3)
        r = analisis.clasificar(a, analisis.enriquecer(a, self.HALL, self.PERFIL))
        self.assertEqual(r["clase"], "fp_actividad_legitima")

    def test_sin_umbral_en_el_perfil_la_regla_no_actua(self):
        a = dict(self.ALERTA, rafaga_60s=50)
        perfil = {"origenes_legitimos": ["192.168.1.1"], "activos": {}}
        r = analisis.clasificar(a, analisis.enriquecer(a, self.HALL, perfil))
        self.assertEqual(r["clase"], "fp_actividad_legitima")

    def test_la_rafaga_no_cambia_un_origen_no_declarado(self):
        a = dict(self.ALERTA, origen_ip="192.168.1.10", rafaga_60s=12)
        r = analisis.clasificar(a, analisis.enriquecer(a, self.HALL, self.PERFIL))
        self.assertEqual(r["clase"], "vp_intento_acceso"); self.assertEqual(r["confianza"], 1.0)

    def test_la_plantilla_y_el_prompt_mencionan_la_rafaga(self):
        from prototipo import justificador_llm as jl
        a = dict(self.ALERTA, rafaga_60s=12)
        ctx = analisis.enriquecer(a, self.HALL, self.PERFIL)
        self.assertIn("ráfaga de 12", analisis.justificar(a, ctx, "vp_intento_acceso"))
        self.assertIn("rafaga de 12", jl.construir_prompt(a, ctx, "vp_intento_acceso"))

class TestClasificarRegistro(unittest.TestCase):
    def _ctx(self, **kw):
        base = {"postura": None, "criticidad": "media", "origen_legitimo": False,
                "rafaga": 0, "umbral_rafaga": 9}
        base.update(kw); return base

    def test_familia_ausente_es_no_soportada(self):
        r = analisis.clasificar({"familia": "plataforma"}, self._ctx())
        self.assertEqual(r["clase"], "no_soportada")

    def test_familia_enrutada_produce_amenaza_enrutada_con_ruta(self):
        r = analisis.clasificar({"familia": "explotacion_conocida"}, self._ctx())
        self.assertEqual(r["clase"], "amenaza_enrutada")
        self.assertEqual(r["ruta"], "appsec")

    def test_familia_actuar_conserva_la_logica_vp(self):
        # postura None + familia de ataque -> vp_intento_acceso 0.5 (sin cambios)
        r = analisis.clasificar({"familia": "acceso_credenciales"}, self._ctx())
        self.assertEqual(r["clase"], "vp_intento_acceso")
        self.assertEqual(r["confianza"], 0.5)
        self.assertNotIn("ruta", r)

