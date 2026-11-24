"""Login correcto tras fuerza bruta (24/11): la regla de fuerza bruta de Wazuh (5763) calla 60 s para TODOS
los orígenes tras dispararse, así que un segundo atacante dentro de ese minuto no deja la compuesta 40112 →
100600 y su login llega suelto (5715) → no_soportada. El MDR lo correlaciona él: mismo origen, mismo equipo."""
import unittest

from prototipo.motor import correlacion as co


def _fallo(t, ip="198.51.100.10", activo="web-banking"):
    return {"familia": "acceso_credenciales", "origen_ip": ip, "activo": activo, "timestamp": f"2026-11-24T19:21:{t:02d}+0000"}


def _login(t, ip="198.51.100.10", activo="web-banking", minuto=21):
    return {"familia": "otra", "login_correcto": True, "origen_ip": ip, "activo": activo,
            "timestamp": f"2026-11-24T19:{minuto:02d}:{t:02d}+0000"}


class TestLoginTrasFuerzaBruta(unittest.TestCase):
    def _con_fallos(self, n, **kw):
        c = co.LoginTrasFuerzaBruta(**kw)
        for i in range(n):
            self.assertFalse(c.anotar(_fallo(i)))
        return c

    def test_cinco_fallos_y_un_login_es_acceso_consumado(self):
        c = self._con_fallos(5)
        a = _login(55)
        self.assertTrue(c.anotar(a))
        self.assertEqual(a["familia"], "acceso_consumado")
        self.assertEqual(a["correlacion"]["regla"], "login_tras_fuerza_bruta")
        self.assertEqual(a["correlacion"]["fallos"], 5)
        self.assertEqual(a["correlacion"]["ventana_s"], co.VENTANA_S)
        self.assertIn("lo correlacionó el MDR", a["correlacion"]["texto"])
        self.assertIn("5 fallos", a["correlacion"]["texto"])

    def test_cuatro_fallos_son_un_usuario_que_se_equivoca(self):
        a = _login(55)
        self.assertFalse(self._con_fallos(4).anotar(a))
        self.assertEqual(a["familia"], "otra")
        self.assertNotIn("correlacion", a)

    def test_fallos_fuera_de_la_ventana_no_cuentan(self):
        a = _login(59, minuto=25)                                 # más de 240 s después
        self.assertFalse(self._con_fallos(8).anotar(a))
        self.assertEqual(a["familia"], "otra")

    def test_otro_origen_u_otro_equipo_no_cuentan(self):
        c = self._con_fallos(8)
        for a in (_login(55, ip="198.51.100.11"), _login(55, activo="api-movil")):
            self.assertFalse(c.anotar(a))
            self.assertEqual(a["familia"], "otra")

    def test_el_origen_excluido_no_se_correlaciona(self):
        # el nodo de gestión del MDR: sus logins son actividad propia, nunca una intrusión inventada
        c = co.LoginTrasFuerzaBruta(excluir={"198.51.100.10"})
        for i in range(8):
            c.anotar(_fallo(i))
        a = _login(55)
        self.assertFalse(c.anotar(a))
        self.assertEqual(a["familia"], "otra")

    def test_solo_toca_logins_correctos_que_nadie_clasifico(self):
        c = self._con_fallos(8)
        ya = {**_login(55), "familia": "acceso_consumado"}        # el SIEM ya lo marcó (100600): no se toca
        self.assertFalse(c.anotar(ya))
        self.assertNotIn("correlacion", ya)
        otra = {**_login(55)}
        otra.pop("login_correcto")                                # una «otra» que no es un login
        self.assertFalse(c.anotar(otra))
        self.assertEqual(otra["familia"], "otra")

    def test_sin_hora_o_sin_origen_no_falla_ni_cambia_nada(self):
        c = self._con_fallos(8)
        for a in ({**_login(55), "timestamp": None}, {**_login(55), "origen_ip": None}, {}):
            self.assertFalse(c.anotar(a))
            self.assertNotEqual(a.get("familia"), "acceso_consumado")
        self.assertFalse(c.anotar({**_fallo(9), "timestamp": "no es una hora"}))

    def test_la_memoria_no_crece_sin_limite(self):
        c = co.LoginTrasFuerzaBruta(max_origenes=50)
        for i in range(500):
            c.anotar(_fallo(i % 60, ip=f"203.0.113.{i % 250}", activo=f"eq{i}"))
        self.assertLessEqual(len(c), 50)


import io, json, os
from unittest import mock

from prototipo.accion import catalogo as catm
from prototipo.servicio import lazo, stream

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CAT = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))


def _fx(n):
    import yaml
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return yaml.safe_load(f) if n.endswith(".yml") else json.loads(f.read().strip())


def _cruda(seg, rule_id, grupos, ip="198.51.100.10"):
    return json.dumps({"id": f"w{seg}", "timestamp": f"2026-11-24T19:21:{seg:02d}+0000",
                       "rule": {"id": rule_id, "level": 5, "groups": ["syslog", "sshd", *grupos], "mitre": {"id": ["T1078"]}},
                       "predecoder": {"hostname": "objetivo-vuln", "program_name": "sshd"}, "data": {"srcip": ip},
                       "full_log": f"sshd {rule_id} {ip}"})


class TestLaDecisionLoDice(unittest.TestCase):
    def test_la_decision_lleva_la_correlacion_y_la_justificacion_la_cuenta(self):
        a = {**_fx("alerta_vp.json"), "familia": "otra", "login_correcto": True}
        c = co.LoginTrasFuerzaBruta()
        for i in range(5):
            c.anotar({**a, "familia": "acceso_credenciales", "timestamp": f"2026-11-24T19:21:{i:02d}Z"})
        a["timestamp"] = "2026-11-24T19:21:30Z"
        self.assertTrue(c.anotar(a))
        d = lazo.decidir_incidente(a, _fx("hallazgos.json"), _fx("perfil.yml"), "prueba", CAT, "d1", "t")
        self.assertEqual(d["clase"], "vp_acceso_consumado")
        self.assertEqual(d["correlacion"]["fallos"], 5)
        self.assertIn("Login correcto tras 5 fallos", d["justificacion"])
        self.assertTrue(d["justificacion"].endswith("lo correlacionó el MDR. [justificación de plantilla]"), d["justificacion"])

    def test_sin_marca_de_origen_la_frase_va_al_final(self):
        a = {**_fx("alerta_vp.json"), "familia": "acceso_consumado",
             "correlacion": {"texto": "login correcto tras 6 fallos …; lo correlacionó el MDR"}}
        d = lazo.decidir_incidente(a, _fx("hallazgos.json"), _fx("perfil.yml"), "prueba", CAT, "d1", "t",
                                   justificar_fn=lambda *_: "Texto del modelo")
        self.assertEqual(d["justificacion"], "Texto del modelo. Login correcto tras 6 fallos …; lo correlacionó el MDR.")

    def test_sin_correlacion_la_decision_no_cambia(self):
        d = lazo.decidir_incidente(_fx("alerta_vp.json"), _fx("hallazgos.json"), _fx("perfil.yml"), "prueba", CAT, "d1", "t")
        self.assertNotIn("correlacion", d)
        self.assertNotIn("lo correlacionó el MDR", d["justificacion"])


class TestEnElDaemon(unittest.TestCase):
    LINEAS = [_cruda(i, "5760", ["authentication_failed"]) for i in range(6)] + [_cruda(30, "5715", ["authentication_success"])]

    def _correr(self):
        buf = io.StringIO()
        stream.ejecutar(self.LINEAS, hallazgos=_fx("hallazgos.json"), perfil=_fx("perfil.yml"), perfil_nombre="prueba",
                        catalogo=CAT, ejecutor=lazo._EjecutorAuto(), justificar_fn=None, ventana_agrupacion=0,
                        salida_traza=buf, escribir=lambda *a, **k: None, leer=lambda *_: "2")
        regs = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
        return [r for r in regs if r.get("tipo") == "decision"]

    def test_el_login_tras_los_fallos_se_decide_como_acceso_consumado(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_CORRELACION_LOGIN", None)
            decisiones = self._correr()
        login = [d for d in decisiones if d.get("correlacion")]
        self.assertEqual(len(login), 1, [(d.get("clase"), d.get("id_alerta")) for d in decisiones])
        self.assertEqual(login[0]["clase"], "vp_acceso_consumado")
        self.assertEqual(login[0]["accion_propuesta"], "MATAR_CONEXION")
        self.assertFalse([d for d in decisiones if d.get("clase") == "no_soportada"])

    def test_se_puede_apagar(self):
        with mock.patch.dict(os.environ, {"TRIAJE_CORRELACION_LOGIN": "0"}):
            decisiones = self._correr()
        self.assertFalse([d for d in decisiones if d.get("correlacion")])
        self.assertTrue([d for d in decisiones if d.get("clase") == "no_soportada"])
