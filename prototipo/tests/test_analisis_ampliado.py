"""Análisis ampliado de la tarjeta de Aprobaciones: lo arma el MDR con reglas, a partir de sus propios
datos (alertas recientes del origen, escaneo de la red, perfil y playbook). Ayuda al analista a decidir;
NO cambia la decisión del motor."""
import copy, unittest

from prototipo.explicacion import analisis_ampliado as aa


def _alerta(n, seg=0, origen="203.0.113.7", activo="objetivo-vuln", familia="acceso_credenciales",
            servicio="ssh", regla="5760", minuto=0):
    return {"id_alerta": f"a{n}", "timestamp": f"2026-08-31T10:{minuto:02d}:{seg:02d}Z",
            "origen_ip": origen, "activo": activo, "familia": familia, "servicio": servicio,
            "regla_id": regla, "nivel_wazuh": 10}


DECISION = {"clase": "vp_intento_acceso", "prioridad": 3, "accion_final": "BLOQUEAR_IP",
            "impacto_determinado": {"activos_afectados_en_cascada": []}}
HALLAZGOS = {"nodos": {"objetivo-vuln": [{"puerto": 22, "servicio": "ssh", "estado": "open"},
                                         {"puerto": 80, "servicio": "http", "estado": "open"},
                                         {"puerto": 23, "servicio": "telnet", "estado": "closed"}],
                       "puesto": []}}
PERFIL = {"activos": {"objetivo-vuln": {"criticidad": "alta"}}, "redes_internas": ["10.30.0.0/16"]}
CORPUS = [{"id": "mapeo-acceso_credenciales", "tipo": "mapeo", "titulo": "Mapeo",
           "texto": "Filtrado de tráfico entrante: BLOQUEAR_IP."}]


def _seccion(r, titulo):
    return next((s for s in r["secciones"] if s["titulo"] == titulo), None)


class TestRecientes(unittest.TestCase):
    def test_devuelve_las_alertas_del_origen_dentro_de_la_ventana(self):
        rec = aa.Recientes(ventana_s=3600)
        rec.registrar(_alerta(1, minuto=0))
        rec.registrar(_alerta(2, minuto=30))
        rec.registrar(_alerta(3, origen="198.51.100.1", minuto=31))
        self.assertEqual([e["id_alerta"] for e in rec.de("203.0.113.7")], ["a1", "a2"])

    def test_olvida_lo_que_sale_de_la_ventana_por_el_reloj_de_las_alertas(self):
        rec = aa.Recientes(ventana_s=60)
        rec.registrar(_alerta(1, minuto=0))
        rec.registrar(_alerta(2, minuto=5))         # 5 min después: la primera ya no cuenta
        self.assertEqual([e["id_alerta"] for e in rec.de("203.0.113.7")], ["a2"])

    def test_tope_por_origen(self):
        rec = aa.Recientes(max_por_origen=3)
        for i in range(10):
            rec.registrar(_alerta(i, seg=i))
        self.assertEqual([e["id_alerta"] for e in rec.de("203.0.113.7")], ["a7", "a8", "a9"])

    def test_tope_de_origenes_evicta_el_menos_reciente(self):
        rec = aa.Recientes(max_origenes=2)
        rec.registrar(_alerta(1, origen="1.1.1.1"))
        rec.registrar(_alerta(2, origen="2.2.2.2"))
        rec.registrar(_alerta(3, origen="3.3.3.3"))
        self.assertEqual(rec.de("1.1.1.1"), [])
        self.assertEqual(len(rec.de("3.3.3.3")), 1)

    def test_sin_origen_o_sin_hora_no_se_registra(self):
        rec = aa.Recientes()
        rec.registrar({**_alerta(1), "origen_ip": None})
        rec.registrar({**_alerta(2), "timestamp": "no es una fecha"})
        self.assertEqual(rec.de("203.0.113.7"), [])
        self.assertEqual(rec.de(None), [])


class TestConstruir(unittest.TestCase):
    def test_marca_su_origen_y_sus_fuentes(self):
        r = aa.construir(_alerta(1), DECISION, hallazgos=HALLAZGOS, perfil=PERFIL, corpus=CORPUS)
        self.assertEqual(r["generado_por"], "reglas")
        self.assertTrue(r["fuentes"])
        self.assertTrue(r["comprobar"])

    def test_historial_del_origen_excluye_la_alerta_que_dispara(self):
        rec = aa.Recientes()
        rec.registrar(_alerta(1, familia="reconocimiento", servicio="", regla="100100", minuto=1))
        rec.registrar(_alerta(2, activo="puesto", minuto=2))
        disparo = _alerta(3, minuto=3)
        rec.registrar(disparo)
        r = aa.construir(disparo, DECISION, recientes=rec)
        s = _seccion(r, "Este origen en la última hora")
        texto = "\n".join(s["lineas"])
        self.assertIn("2 alertas más", texto)
        self.assertIn("reconocimiento", texto)
        self.assertNotIn("a3", texto)
        # escaneó antes y tocó más de un equipo: dos comprobaciones concretas
        comprobar = "\n".join(r["comprobar"])
        self.assertIn("reconocimiento", comprobar)
        self.assertIn("2 equipos", comprobar)

    def test_sin_id_o_con_id_repetido_solo_se_excluye_la_que_dispara(self):
        rec = aa.Recientes()
        for i in range(3):
            rec.registrar({**_alerta(i, minuto=i), "id_alerta": None})
        disparo = {**_alerta(9, minuto=3), "id_alerta": None}
        rec.registrar(disparo)
        s = _seccion(aa.construir(disparo, DECISION, recientes=rec), "Este origen en la última hora")
        self.assertIn("3 alertas más", s["lineas"][0])
        rec = aa.Recientes()
        rec.registrar(_alerta(1, minuto=1))
        disparo = _alerta(1, minuto=2)                     # mismo id, otro instante
        rec.registrar(disparo)
        s = _seccion(aa.construir(disparo, DECISION, recientes=rec), "Este origen en la última hora")
        self.assertIn("1 alerta más", s["lineas"][0])

    def test_primera_alerta_del_origen(self):
        rec = aa.Recientes()
        disparo = _alerta(1)
        rec.registrar(disparo)
        s = _seccion(aa.construir(disparo, DECISION, recientes=rec), "Este origen en la última hora")
        self.assertIn("primera", s["lineas"][0])

    def test_historial_muestra_como_mucho_cinco_lineas_de_detalle(self):
        rec = aa.Recientes()
        for i in range(9):
            rec.registrar(_alerta(i, seg=i))
        disparo = _alerta(99, seg=30)
        r = aa.construir(disparo, DECISION, recientes=rec)
        s = _seccion(r, "Este origen en la última hora")
        self.assertIn("9 alertas más", s["lineas"][0])
        self.assertEqual(len(s["lineas"]), 1 + 5 + 1)     # resumen + 5 + «y 4 más»
        self.assertIn("4 más", s["lineas"][-1])

    def test_equipo_atacado_con_servicios_abiertos_y_criticidad(self):
        r = aa.construir(_alerta(1), DECISION, hallazgos=HALLAZGOS, perfil=PERFIL)
        texto = "\n".join(_seccion(r, "El equipo atacado")["lineas"])
        self.assertIn("ssh/22", texto)
        self.assertIn("http/80", texto)
        self.assertNotIn("telnet", texto)                  # cerrado: no se lista como abierto
        self.assertIn("alta", texto)

    def test_servicio_atacado_no_abierto_pide_comprobarlo(self):
        r = aa.construir(_alerta(1, servicio="telnet"), DECISION, hallazgos=HALLAZGOS)
        self.assertTrue(any("telnet" in c and "no figura abierto" in c for c in r["comprobar"]))

    def test_equipo_que_no_esta_en_el_escaneo(self):
        r = aa.construir(_alerta(1, activo="desconocido"), DECISION, hallazgos=HALLAZGOS)
        self.assertIn("no aparece", "\n".join(_seccion(r, "El equipo atacado")["lineas"]))

    def test_playbook_de_la_familia_o_aviso_si_no_hay_ficha(self):
        r = aa.construir(_alerta(1), DECISION, corpus=CORPUS)
        self.assertIn("BLOQUEAR_IP", "\n".join(_seccion(r, "Qué dice el playbook")["lineas"]))
        self.assertIn("mapeo-acceso_credenciales", "\n".join(r["fuentes"]))
        r = aa.construir(_alerta(1, familia="malware"), DECISION, corpus=CORPUS)
        self.assertIn("Sin ficha", "\n".join(_seccion(r, "Qué dice el playbook")["lineas"]))

    def test_origen_interno_pide_confirmar_con_el_responsable(self):
        r = aa.construir(_alerta(1, origen="10.30.0.15"), DECISION, perfil=PERFIL)
        self.assertTrue(any("interno" in c for c in r["comprobar"]))
        r = aa.construir(_alerta(1), DECISION, perfil=PERFIL)
        self.assertFalse(any("interno" in c for c in r["comprobar"]))

    def test_cascada_lista_los_equipos_afectados(self):
        d = {**DECISION, "impacto_determinado": {"activos_afectados_en_cascada": ["app", "bd"]}}
        r = aa.construir(_alerta(1), d)
        self.assertTrue(any("app" in c and "bd" in c for c in r["comprobar"]))

    def test_accion_vetada_avisa_que_aprobar_no_contiene(self):
        r = aa.construir(_alerta(1), {**DECISION, "accion_final": None})
        self.assertTrue(any("no ejecuta ninguna contención" in c for c in r["comprobar"]))

    def test_sin_nada_que_senalar_hay_una_comprobacion_por_defecto(self):
        r = aa.construir(_alerta(1), DECISION)
        self.assertEqual(len(r["comprobar"]), 1)

    def test_no_cambia_la_decision_ni_la_alerta(self):
        d, a = copy.deepcopy(DECISION), _alerta(1)
        d0, a0 = copy.deepcopy(d), copy.deepcopy(a)
        aa.construir(a, d, recientes=aa.Recientes(), hallazgos=HALLAZGOS, perfil=PERFIL, corpus=CORPUS)
        self.assertEqual((d, a), (d0, a0))

    def test_aguanta_entradas_vacias(self):
        r = aa.construir({}, {})
        self.assertEqual(r["generado_por"], "reglas")
        self.assertTrue(r["comprobar"])


if __name__ == "__main__":
    unittest.main()
