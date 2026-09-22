import unittest
from lab.banco import pruebas as rg


class TestReglasExtra(unittest.TestCase):
    def test_ignora_politicas_y_la_regla_de_aislamiento_de_eth0(self):
        salida = ("-P INPUT ACCEPT\n-P FORWARD ACCEPT\n-P OUTPUT ACCEPT\n"
                  "-A INPUT -i eth0 -p tcp -j DROP\n-A INPUT -s 10.40.0.10/32 -j DROP\n")
        self.assertEqual(rg.reglas_extra(salida), ["-A INPUT -s 10.40.0.10/32 -j DROP"])

    def test_estado_base_sin_reglas(self):
        self.assertEqual(rg.reglas_extra("-P INPUT ACCEPT\n-A INPUT -i eth0 -p tcp -j DROP\n"), [])


class TestCaidos(unittest.TestCase):
    def test_conjunto_de_caidos(self):
        m = {"t": "x", "estados": {"core-db": "ok", "middleware": "caido", "atm": "caido"}}
        self.assertEqual(rg.caidos(m), {"middleware", "atm"})

    def test_sin_muestra_es_none(self):
        self.assertIsNone(rg.caidos(None))


class TestLector(unittest.TestCase):
    def test_contesta_menu_y_escalada_por_separado(self):
        leer = rg.Lector(menu="1", escalada="s")
        self.assertEqual(leer("Elige [1-3]: "), "1")
        self.assertEqual(leer("¿aprobar la ejecución? [s/N] "), "s")
        self.assertEqual([p for p, _ in leer.preguntas], ["menu", "escalada"])

    def test_pregunta_no_prevista_se_rechaza_y_se_anota(self):
        leer = rg.Lector()
        self.assertEqual(leer("Elige [1-3]: "), "")          # vacio = rechazar, lo seguro
        self.assertEqual(leer.preguntas, [("menu", "")])


class TestFuente(unittest.TestCase):
    def test_filtra_por_ip_del_atacante_y_para(self):
        lineas = ['{"data":{"srcip":"198.51.100.10"}}', '{"data":{"srcip":"10.0.0.9"}}', None,
                  '{"data":{"srcip":"198.51.100.10"}}']
        vistas = []
        for l in rg.fuente_filtrada(iter(lineas), "198.51.100.10", parar=lambda: len(vistas) >= 2):
            vistas.append(l)
        self.assertEqual(vistas, ['{"data":{"srcip":"198.51.100.10"}}', None])


REG_K1 = {"requiere_humano": True, "accion_final": "BLOQUEAR_IP", "veredicto_humano": "aprobar",
          "impacto_determinado": {"activos_afectados_en_cascada": []}, "escalada": None}


class TestEvaluar(unittest.TestCase):
    def test_k1_reproduce_el_fallo_conocido(self):
        esperado = {"requiere_humano": True, "veredicto": "aprobar", "prediccion_cascada": [],
                    "regla": ("core-db", "-A INPUT -s 10.40.0.10/32 -j DROP"),
                    "caen": {"middleware", "web-banking", "api-movil", "atm"}, "preguntas": 1}
        fallos = rg.evaluar(esperado, REG_K1, {"core-db": ["-A INPUT -s 10.40.0.10/32 -j DROP"]},
                            {"middleware", "web-banking", "api-movil", "atm"}, [("menu", "1")])
        self.assertEqual(fallos, [])

    def test_detecta_cada_diferencia(self):
        esperado = {"requiere_humano": False, "accion_final": "BLOQUEAR_IP", "preguntas": 0,
                    "regla": ("web-banking", "-A INPUT -s 198.51.100.10/32 -j DROP"), "caen": set()}
        fallos = rg.evaluar(esperado, REG_K1, {"web-banking": []}, {"atm"}, [("menu", "")])
        texto = " | ".join(fallos)
        self.assertIn("requiere_humano", texto)
        self.assertIn("preguntas", texto)
        self.assertIn("regla", texto)
        self.assertIn("atm", texto)

    def test_escalada(self):
        reg = dict(REG_K1, escalada={"escalado": True, "dispositivo_ejecutor": "fw-core"})
        esperado = {"escalado": True, "dispositivo_ejecutor": "fw-core"}
        self.assertEqual(rg.evaluar(esperado, reg, {}, set(), []), [])
        self.assertTrue(rg.evaluar({"dispositivo_ejecutor": "fw-edge"}, reg, {}, set(), []))

    def test_sin_registro_es_un_fallo(self):
        self.assertEqual(rg.evaluar({"requiere_humano": True}, None, {}, set(), []),
                         ["el prototipo no produjo ninguna decision (sin alerta de Wazuh o sin incidente)"])


class TestFalloEsperado(unittest.TestCase):
    def test_fallo_esperado_presente_es_ok(self):
        # el prototipo NO predice la cascada (fallo K1): con fallo_esperado, eso es OK
        r = rg.veredicto_caso({"fallo_esperado": "K1: no predice la cascada"}, ["prediccion_cascada: ..."])
        self.assertEqual(r, ("OK", ["fallo conocido reproducido: K1: no predice la cascada"]))

    def test_fallo_esperado_ausente_es_fallo(self):
        r = rg.veredicto_caso({"fallo_esperado": "K1: no predice la cascada"}, [])
        self.assertEqual(r[0], "FALLO")
        self.assertIn("ya no ocurre", r[1][0])

    def test_sin_fallo_esperado_los_fallos_son_fallo(self):
        self.assertEqual(rg.veredicto_caso({}, ["x"]), ("FALLO", ["x"]))
        self.assertEqual(rg.veredicto_caso({}, []), ("OK", []))


class TestNivelDecision(unittest.TestCase):
    def setUp(self):
        import os
        from prototipo import perfil, catalogo
        raiz = rg.RAIZ
        self.p = perfil.cargar(os.path.join(raiz, "prototipo/perfiles/bancario.yml"))
        self.c = catalogo.cargar_catalogo(os.path.join(raiz, "prototipo/catalogo.yml"))
        import json
        with open(rg.HALLAZGOS, encoding="utf-8") as f:
            self.h = json.load(f)

    def _correr(self, caso):
        return rg.correr_decision(caso, self.p, self.h, self.c)

    def test_d1_externo_automatico(self):
        caso = {"id": "D1d", "titulo": "x", "nivel": "decision",
                "alerta": {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "ssh",
                           "familia": "acceso_credenciales", "regla_id": "5763"},
                "esperado": {"clase": "vp_intento_acceso", "requiere_humano": False, "accion_final": "BLOQUEAR_IP"}}
        self.assertEqual(self._correr(caso)["resultado"], "OK")

    def test_a3_gestion_es_veto(self):
        # Sin ráfaga, el origen de gestión con una sola alerta es fp_actividad_legitima SIN acción
        # propuesta (nada que vetar). El veto duro (RF-19) solo entra en juego cuando SÍ hay una
        # acción propuesta contra la IP de gestión, que aquí exige ráfaga (>= umbral del perfil,
        # ver bancario.yml rafaga.umbral=9) para clasificar como vp_intento_acceso — el mismo
        # escenario que el caso A3 de casos.py. Sin este campo el caso no ejercita ningún veto.
        caso = {"id": "A3d", "titulo": "x", "nivel": "decision",
                "alerta": {"origen_ip": "10.100.0.10", "activo": "web-banking", "servicio": "ssh",
                           "familia": "acceso_credenciales", "regla_id": "5763"},
                "rafaga_60s": 12,
                "esperado": {"requiere_humano": True, "accion_final": None}}
        self.assertEqual(self._correr(caso)["resultado"], "OK")

    def test_detecta_diferencia(self):
        caso = {"id": "Xd", "titulo": "x", "nivel": "decision",
                "alerta": {"origen_ip": "203.0.113.9", "activo": "web-banking", "servicio": "ssh",
                           "familia": "acceso_credenciales", "regla_id": "5763"},
                "esperado": {"requiere_humano": True}}   # es automatico, no humano
        r = self._correr(caso)
        self.assertEqual(r["resultado"], "FALLO")
        self.assertIn("requiere_humano", r["detalle"][0])


class TestNivelInyectadaPerfil(unittest.TestCase):
    def setUp(self):
        import os
        from prototipo import perfil, catalogo
        self.p = perfil.cargar(os.path.join(rg.RAIZ, "prototipo/perfiles/bancario.yml"))
        self.c = catalogo.cargar_catalogo(os.path.join(rg.RAIZ, "prototipo/catalogo.yml"))

    def test_c1_bloquear_puerto_core_db_degrada(self):
        caso = {"id": "C1", "titulo": "x", "nivel": "inyectada", "accion": "BLOQUEAR_PUERTO",
                "params": {"puerto": 1521, "ip": "203.0.113.9"}, "activo": "core-db", "servicio": "sql",
                "confianza": 0.99, "esperado": {"filtro_resultado": "degrada", "accion_final": "BLOQUEAR_IP"}}
        self.assertEqual(rg.correr_inyectada(caso, self.p, self.c)["resultado"], "OK")

    def test_k2_aislar_core_db_predice_cascada(self):
        caso = {"id": "K2", "titulo": "x", "nivel": "inyectada", "accion": "AISLAR_NODO", "params": {},
                "activo": "core-db", "servicio": "sql", "confianza": 0.99,
                "esperado": {"requiere_humano": True,
                             "prediccion_cascada": ["api-movil", "middleware", "web-banking"]}}
        self.assertEqual(rg.correr_inyectada(caso, self.p, self.c)["resultado"], "OK")

    def test_c5_sin_reversion_es_veto(self):
        caso = {"id": "C5", "titulo": "x", "nivel": "perfil",
                "comprobacion": "sin_reversion", "accion": "OBS_PROCESOS", "activo": "core-db",
                "esperado": {"filtro_resultado": "veta"}}
        self.assertEqual(rg.correr_perfil(caso, self.p, self.c)["resultado"], "OK")

    def test_k4_ciclo_termina(self):
        caso = {"id": "K4", "titulo": "x", "nivel": "perfil", "comprobacion": "ciclo_depende_de",
                "activo": "core-db", "esperado": {"termina": True}}
        self.assertEqual(rg.correr_perfil(caso, self.p, self.c)["resultado"], "OK")

    def test_k4_ciclo_sintetico_termina(self):
        # bancario.yml no tiene un ciclo real en depende_de; con un perfil_sintetico a->b->a
        # el caso ejercita de verdad la guardia de ciclos (sin colgarse ni RecursionError).
        caso = {"id": "K4s", "titulo": "x", "nivel": "perfil", "comprobacion": "ciclo_depende_de",
                "activo": "a",
                "perfil_sintetico": {"activos": {"a": {"depende_de": ["b"]}, "b": {"depende_de": ["a"]}}},
                "esperado": {"termina": True}}
        self.assertEqual(rg.correr_perfil(caso, self.p, self.c)["resultado"], "OK")


class TestGuias(unittest.TestCase):
    def test_guia_incluye_ataque_y_esperado(self):
        caso = {"id": "D1", "titulo": "Externo contra web-banking", "nivel": "vivo",
                "ataque": ("internet", "sshpass -p x ssh ... cliente@10.10.0.10 id"),
                "origen": "198.51.100.10", "esperado": {"accion_final": "BLOQUEAR_IP"},
                "deshacer": [("web-banking", "iptables -D INPUT -s 198.51.100.10 -j DROP")]}
        g = rg.guia_markdown(caso)
        self.assertIn("# D1", g)
        self.assertIn("Externo contra web-banking", g)
        self.assertIn("sshpass", g)
        self.assertIn("iptables -D INPUT", g)

    def test_guia_de_caso_de_decision(self):
        caso = {"id": "A3", "titulo": "Gestión = veto", "nivel": "decision",
                "alerta": {"origen_ip": "10.100.0.10", "activo": "web-banking"},
                "esperado": {"accion_final": None}}
        g = rg.guia_markdown(caso)
        self.assertIn("nivel: decision", g)
        self.assertIn("10.100.0.10", g)


class TestInforme(unittest.TestCase):
    def test_resume_por_resultado_y_nivel(self):
        res = [{"id": "D1", "titulo": "a", "resultado": "OK", "detalle": [], "segundos": 1, "nivel": "decision"},
               {"id": "K1", "titulo": "b", "resultado": "OK", "detalle": ["fallo conocido"], "segundos": 2, "nivel": "vivo"},
               {"id": "E6", "titulo": "c", "resultado": "OMITIDO", "detalle": ["requiere modelo"], "segundos": 0, "nivel": "vivo"}]
        txt = rg.informe(res, "2026-09-22 10:00")
        self.assertIn("2 OK", txt)
        self.assertIn("1 OMITIDO", txt)
        self.assertIn("decision", txt)
        self.assertIn("| D1 |", txt)


if __name__ == "__main__":
    unittest.main()
