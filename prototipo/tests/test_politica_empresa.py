"""politica.yml: la política de la empresa en términos de negocio, traducida a las claves del perfil
(plan: documentacion/05-fase5-implementacion-del-prototipo/plan-politica-empresa.md, tarea 1)."""
import os
import unittest

from prototipo.accion import catalogo as catm
from prototipo.motor import politica_empresa as pe

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = catm.cargar_catalogo(os.path.join(RAIZ, "prototipo", "catalogo.yml"))

PERFIL = {
    "activos": {"web01": {"ip": "192.0.2.10"}, "db01": {"ip": "10.20.0.20"}},
    "ip_gestion": "10.99.0.10",
    "red": {"zonas": {"DMZ": ["web01"], "Interna": ["db01"]}},
}

POLITICA = {
    "politica": {"version": 3, "aprobada_por": "Dirección de Seguridad", "fecha": "2026-11-10"},
    "confianza": {"administradores": ["10.99.0.10"], "socios_criticos": ["203.0.113.7", "198.51.100.0/24"],
                  "sospechar_si_rafaga": {"alertas": 9, "en_segundos": 60}},
    "respuesta_automatica": {
        "certeza_minima": 0.9, "por_defecto": "si_hay_certeza", "si_afecta_a_un_servicio": "con_analista",
        "solo_observar": "sola", "equipos_propios": "con_analista", "externos_desconocidos": "con_analista",
        "origenes_vigilados": "con_analista",
        "por_tipo_de_ataque": {"acceso_credenciales": "si_hay_certeza", "integridad_fichero": "con_analista"},
        "por_zona": {"Interna": "con_analista"},
        "por_equipo": {"db01": "con_analista"},
    },
    "nunca_tocar_en_automatico": [{"equipo": "db01", "servicio": 5432}],
    "desconocidos_graves": {"revisar_desde_nivel": 10},
}


class TestTraducir(unittest.TestCase):
    def setUp(self):
        self.t = pe.traducir_politica(POLITICA)

    def test_confianza(self):
        self.assertEqual(self.t["origenes_legitimos"], ["10.99.0.10"])
        self.assertEqual(self.t["terceros_confiables"], ["203.0.113.7", "198.51.100.0/24"])
        self.assertEqual(self.t["rafaga"], {"umbral": 9, "ventana_s": 60})

    def test_continuidad(self):
        c = self.t["continuidad"]
        self.assertEqual(c["umbral_confianza"], 0.9)
        self.assertEqual(c["impacto_localizado"], "automatica_si_confianza")
        self.assertEqual(c["impacto_alcanza_servicio"], "humano_siempre")
        self.assertEqual(c["impacto_ninguno"], "automatica")
        self.assertEqual(c["actores"], {"activo_interno": "humano_siempre", "dispositivo_red": "humano_siempre"})
        self.assertEqual(c["contener_externos_desconocidos"], "humano_siempre")
        self.assertEqual(c["vigilados"], "humano_siempre")
        self.assertEqual(c["revisar_no_soportada_nivel"], 10)

    def test_dimensiones(self):
        self.assertEqual(self.t["automatizacion_por_familia"],
                         {"acceso_credenciales": {"automatizacion": "automatica_si_confianza"},
                          "integridad_fichero": {"automatizacion": "humano_siempre"}})
        self.assertEqual(self.t["politicas_por_zona"], {"Interna": {"automatizacion": "humano_siempre"}})
        self.assertEqual(self.t["overrides_por_activo"], {"db01": {"automatizacion": "humano_siempre"}})

    def test_intocables(self):
        self.assertEqual(self.t["excepciones"], [{"activo": "db01", "servicio": 5432, "regla": "nunca_automatica"}])

    def test_la_cabecera_no_entra_en_el_perfil(self):
        self.assertNotIn("politica", self.t)
        self.assertEqual(pe.cabecera(POLITICA)["version"], 3)

    def test_politica_parcial_solo_traduce_lo_que_declara(self):
        self.assertEqual(pe.traducir_politica({"confianza": {"administradores": ["10.0.0.1"]}}),
                         {"origenes_legitimos": ["10.0.0.1"]})


class TestFusionar(unittest.TestCase):
    def test_sin_politica_el_perfil_no_cambia(self):
        self.assertEqual(pe.fusionar_perfil_y_politica(PERFIL, None), PERFIL)

    def test_con_politica_suma_las_claves_y_fija_los_frenos(self):
        f = pe.fusionar_perfil_y_politica(PERFIL, POLITICA)
        self.assertEqual(f["activos"], PERFIL["activos"])
        self.assertEqual(f["origenes_legitimos"], ["10.99.0.10"])
        self.assertTrue(f["continuidad"]["reversibilidad_obligatoria"])
        self.assertTrue(f["continuidad"]["no_cortar_gestion"])
        self.assertNotIn("origenes_legitimos", PERFIL)          # no muta el perfil

    def test_una_regla_en_los_dos_ficheros_es_error(self):
        perfil = {**PERFIL, "origenes_legitimos": ["10.99.0.10"], "continuidad": {"umbral_confianza": 0.7}}
        with self.assertRaises(ValueError) as e:
            pe.fusionar_perfil_y_politica(perfil, POLITICA)
        self.assertIn("origenes_legitimos", str(e.exception))
        self.assertIn("continuidad.umbral_confianza", str(e.exception))


class TestValidar(unittest.TestCase):
    def avisos(self, pol, perfil=PERFIL):
        return pe.validar_politica(pol, perfil, CAT)

    def test_la_politica_de_ejemplo_es_valida(self):
        self.assertEqual(self.avisos(POLITICA), [])

    def test_clave_desconocida(self):
        self.assertTrue(any("clave desconocida" in a and "respuesta" in a for a in self.avisos({"respuesta": {}})))
        self.assertTrue(any("por_familia" in a for a in self.avisos({"respuesta_automatica": {"por_familia": {}}})))

    def test_equipo_zona_y_familia_desconocidos(self):
        avisos = self.avisos({"respuesta_automatica": {"por_equipo": {"web99": "con_analista"},
                                                       "por_zona": {"Marte": "con_analista"},
                                                       "por_tipo_de_ataque": {"teleportacion": "con_analista"}},
                              "nunca_tocar_en_automatico": [{"equipo": "db99", "servicio": 5432}]})
        for nombre in ("web99", "Marte", "teleportacion", "db99"):
            self.assertTrue(any(nombre in a for a in avisos), nombre)

    def test_valor_fuera_de_la_tabla(self):
        self.assertTrue(any("siempre" in a for a in self.avisos({"respuesta_automatica": {"por_defecto": "siempre"}})))
        # en familia, zona y equipo solo valen si_hay_certeza y con_analista (como hoy)
        self.assertTrue(any("sola" in a for a in self.avisos({"respuesta_automatica": {"por_zona": {"DMZ": "sola"}}})))

    def test_un_freno_duro_no_se_puede_abrir(self):
        frenos = pe.familias_freno_duro(CAT)
        self.assertIn("integridad_fichero", frenos)
        self.assertNotIn("acceso_credenciales", frenos)
        self.assertEqual(self.avisos({"respuesta_automatica": {"por_tipo_de_ataque": {"integridad_fichero": "con_analista"}}}), [])
        self.assertTrue(any("freno duro" in a for a in
                            self.avisos({"respuesta_automatica": {"por_tipo_de_ataque": {"integridad_fichero": "si_hay_certeza"}}})))

    def test_direcciones_y_numeros(self):
        avisos = self.avisos({"confianza": {"administradores": ["10.99.0"], "socios_criticos": ["nope/24"],
                                            "sospechar_si_rafaga": {"alertas": 0, "en_segundos": 60}},
                              "respuesta_automatica": {"certeza_minima": 1.5},
                              "desconocidos_graves": {"revisar_desde_nivel": -1}})
        for trozo in ("10.99.0", "nope/24", "alertas", "certeza_minima", "revisar_desde_nivel"):
            self.assertTrue(any(trozo in a for a in avisos), trozo)

    def test_la_regla_repetida_en_el_perfil_se_avisa(self):
        avisos = self.avisos({"confianza": {"administradores": ["10.99.0.10"]}}, {**PERFIL, "origenes_legitimos": ["x"]})
        self.assertTrue(any("en el perfil y en la política" in a for a in avisos))


if __name__ == "__main__":
    unittest.main()


class TestExplicar(unittest.TestCase):
    def setUp(self):
        self.frases = pe.explicar(pe.fusionar_perfil_y_politica(PERFIL, POLITICA), CAT)
        self.texto = "\n".join(self.frases)

    def test_cuenta_la_confianza(self):
        self.assertIn("10.99.0.10", self.texto)
        self.assertIn("203.0.113.7", self.texto)
        self.assertIn("9 alertas en 60 s", self.texto)

    def test_cuenta_la_automatizacion_por_capas(self):
        self.assertIn("0,90", self.texto)
        # por tipo de ataque, zona o equipo solo se endurece: si_hay_certeza no promete automatizar nada
        frase = next(f for f in self.frases if "acceso_credenciales" in f)
        self.assertIn("regla general", frase)
        self.assertNotIn("se ejecuta sola", frase)
        self.assertTrue(any("Interna" in f and "db01" in f and "analista" in f for f in self.frases))
        self.assertTrue(any("db01" in f and "5432" in f for f in self.frases))

    def test_nombra_los_frenos_duros_del_codigo(self):
        frase = next(f for f in self.frases if "nunca se contienen solos" in f)
        self.assertIn("integridad_fichero", frase)

    def test_sin_politica_explica_el_perfil(self):
        self.assertTrue(pe.explicar(PERFIL, CAT))          # nunca vacío: al menos los frenos del código


class TestExtraer(unittest.TestCase):
    def test_ida_y_vuelta(self):
        perfil = pe.fusionar_perfil_y_politica(PERFIL, POLITICA)
        pol, resto = pe.extraer_politica(perfil)
        self.assertNotIn("origenes_legitimos", resto)
        self.assertEqual(pe.fusionar_perfil_y_politica(resto, pol), perfil)
        self.assertEqual(pol["respuesta_automatica"]["por_defecto"], "si_hay_certeza")
        self.assertEqual(pol["nunca_tocar_en_automatico"], [{"equipo": "db01", "servicio": 5432}])

    def test_lo_tecnico_se_queda_en_el_perfil(self):
        perfil = {**PERFIL, "rafaga": {"umbral": 9, "ventana_s": 60, "umbral_largo": 15}}
        pol, resto = pe.extraer_politica(perfil)
        self.assertEqual(resto["rafaga"], {"umbral_largo": 15})
        self.assertEqual(resto["activos"], PERFIL["activos"])

    def test_actores_distintos_se_quedan_en_el_perfil(self):
        perfil = {**PERFIL, "continuidad": {"actores": {"activo_interno": "humano_siempre", "dispositivo_red": "automatica"}}}
        pol, resto = pe.extraer_politica(perfil)
        self.assertNotIn("equipos_propios", pol.get("respuesta_automatica") or {})
        self.assertEqual(resto["continuidad"]["actores"], perfil["continuidad"]["actores"])


class TestPropuesta(unittest.TestCase):
    def test_aplica_los_cambios_de_consola_y_sube_la_version(self):
        overlay = {"overrides_por_activo": {"web01": {"automatizacion": "humano_siempre"}},
                   "automatizacion_por_familia": {"acceso_credenciales": {"automatizacion": "humano_siempre"}}}
        p = pe.propuesta(POLITICA, overlay)
        self.assertEqual(p["politica"]["version"], 4)
        self.assertEqual(p["politica"]["basada_en"], 3)
        self.assertIn("pendiente", p["politica"]["aprobada_por"])
        self.assertEqual(p["respuesta_automatica"]["por_equipo"], {"db01": "con_analista", "web01": "con_analista"})
        self.assertEqual(p["respuesta_automatica"]["por_tipo_de_ataque"]["acceso_credenciales"], "con_analista")
        self.assertEqual(POLITICA["politica"]["version"], 3)            # no muta la vigente

    def test_sin_politica_previa_es_la_version_1(self):
        p = pe.propuesta({}, {"politicas_por_zona": {"DMZ": {"automatizacion": "humano_siempre"}}})
        self.assertEqual(p["politica"]["version"], 1)
        self.assertEqual(p["respuesta_automatica"]["por_zona"], {"DMZ": "con_analista"})


MAL_FORMADAS = [
    {"confianza": ["10.99.0.10"]},
    {"respuesta_automatica": ["sola"]},
    {"confianza": {"sospechar_si_rafaga": [9, 60]}},
    {"respuesta_automatica": {"por_defecto": ["sola"]}},
    {"respuesta_automatica": {"por_tipo_de_ataque": {"acceso_credenciales": {"a": 1}}}},
    {"respuesta_automatica": {"por_tipo_de_ataque": ["acceso_credenciales"]}},
    {"nunca_tocar_en_automatico": "db01"},
    {"nunca_tocar_en_automatico": {"equipo": "db01", "servicio": 5432}},
    {"confianza": {"administradores": 5}},
    {"confianza": {"socios_criticos": "203.0.113.7"}},
    {"desconocidos_graves": 10},
    {"desconocidos_graves": ["x"]},
    {"politica": [1]},
    {"politica": {"version": "1.2"}},
    {"politica": {"version": 0}},
    {"politica": {"aprobada_por": 4711}},
    {"politica": {"clave_rara": 1}},
]


class TestValidarEsTotal(unittest.TestCase):
    """I1/I2 de la revisión: cualquier cosa que devuelva yaml.safe_load da avisos, nunca una excepción."""
    def test_las_formas_incorrectas_dan_avisos(self):
        for pol in MAL_FORMADAS:
            with self.subTest(pol=pol):
                self.assertTrue(pe.validar_politica(pol, PERFIL, CAT))

    def test_la_cabecera_correcta_no_avisa(self):
        self.assertEqual(pe.validar_politica({"politica": {"version": 2, "aprobada_por": "Seguridad",
                                                            "fecha": __import__("datetime").date(2026, 11, 11)}},
                                             PERFIL, CAT), [])

    def test_secciones_vacias_son_validas(self):
        self.assertEqual(pe.validar_politica({"confianza": None, "respuesta_automatica": None,
                                              "nunca_tocar_en_automatico": None}, PERFIL, CAT), [])


class TestSemanticaReal(unittest.TestCase):
    """I3 de la revisión: lo que se firma debe ser lo que el motor hace."""
    def test_equipos_propios_no_admite_sola(self):
        avisos = pe.validar_politica({"respuesta_automatica": {"equipos_propios": "sola"}}, PERFIL, CAT)
        self.assertTrue(any("equipos_propios" in a for a in avisos))

    def test_una_excepcion_si_hay_certeza_no_se_cuenta_como_automatizacion(self):
        pol = {"respuesta_automatica": {"por_defecto": "con_analista",
                                        "por_tipo_de_ataque": {"acceso_credenciales": "si_hay_certeza"},
                                        "por_zona": {"DMZ": "si_hay_certeza"}, "por_equipo": {"web01": "si_hay_certeza"}}}
        frases = pe.explicar(pe.fusionar_perfil_y_politica(PERFIL, pol), CAT)
        for nombre in ("acceso_credenciales", "DMZ", "web01"):
            frase = next(f for f in frases if nombre in f)
            self.assertNotIn("se ejecuta sola", frase, frase)



class TestOrigenesVigilados(unittest.TestCase):
    def test_se_explica_y_vuelve_a_la_propuesta(self):
        perfil = pe.fusionar_perfil_y_politica({"activos": {}}, {"respuesta_automatica": {"origenes_vigilados": "con_analista"}})
        self.assertEqual(perfil["continuidad"]["vigilados"], "humano_siempre")
        frases = " ".join(pe.explicar(perfil, {}))
        self.assertIn("origen en vigilancia", frases)

    def test_un_valor_raro_avisa(self):
        avisos = pe.validar_politica({"respuesta_automatica": {"origenes_vigilados": "a_veces"}}, PERFIL, CAT)
        self.assertTrue(any("origenes_vigilados" in a for a in avisos))
