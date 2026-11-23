"""API de la política de la empresa (tarea 4): origen de cada valor, diferencias consola↔fichero,
la política en castellano y la propuesta de versión nueva (solo lectura)."""
import copy, http.client, json, os, tempfile, threading, unittest
from unittest import mock

import yaml

from prototipo.motor import politica_empresa as pe
from prototipo.servicio import tablero

CAT = {"BLOQUEAR_IP": {"reversion": "definida", "impacto": "bajo"},
       "AISLAR_NODO": {"reversion": "definida", "impacto": "alto", "nunca_automatica": True}}
PERFIL = {"ip_gestion": "10.0.0.1", "activos": {"srv": {"ip": "10.0.0.5", "criticidad": "media"}},
          "red": {"zonas": {"Core": ["srv"]}}}
POL = {"politica": {"version": 3, "aprobada_por": "Seguridad", "fecha": "2026-11-10"},
       "respuesta_automatica": {"por_tipo_de_ataque": {"reconocimiento": "si_hay_certeza"},
                                "por_zona": {"Core": "con_analista"}}}


class TestApiPolitica(unittest.TestCase):
    def _srv(self, pol=None):
        d = tempfile.mkdtemp()
        self.ov = os.path.join(d, "politica-operativa.yml")
        perfil = pe.fusionar_perfil_y_politica(copy.deepcopy(PERFIL), pol) if pol else copy.deepcopy(PERFIL)
        srv = tablero.crear_servidor(tablero.EstadoTablero(), os.path.join(d, "t.jsonl"), puerto=0,
                                     estaticos=tempfile.mkdtemp(), perfil=perfil, catalogo=CAT,
                                     ruta_overlay=self.ov, ruta_auditoria=os.path.join(d, "audit.jsonl"))
        srv.politica_info = ({"version": 3, "aprobada_por": "Seguridad", "fecha": "2026-11-10",
                              "ruta": "/etc/mdr/politica.yml", "hash": "ab" * 32, "politica": pol} if pol else None)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv

    def _req(self, srv, metodo, ruta, obj=None):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        c.request(metodo, ruta, json.dumps(obj) if obj is not None else None, {"Content-Type": "application/json"})
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def _cambiar(self, srv, dimension, clave, valor):
        with mock.patch.dict(os.environ, {"TRIAJE_POLITICA_ABIERTA": "1"}):
            st, _ = self._req(srv, "POST", "/api/politica",
                              {"dimension": dimension, "clave": clave, "automatizacion": valor, "operador": "ana"})
        self.assertEqual(st, 200)

    def test_sin_politica_los_origenes_son_codigo_o_por_defecto(self):
        _, est = self._req(self._srv(), "GET", "/api/politica")
        self.assertIsNone(est["politica"])
        fam = {f["familia"]: f["origen"] for f in est["familias"]}
        self.assertEqual(fam["reconocimiento"], "por_defecto")
        self.assertEqual(fam["integridad_fichero"], "codigo")
        self.assertEqual(est["zonas"][0]["origen"], "por_defecto")
        self.assertEqual(est["diferencias"], [])

    def test_con_politica_el_valor_viene_del_fichero(self):
        _, est = self._req(self._srv(POL), "GET", "/api/politica")
        self.assertEqual(est["politica"]["version"], 3)
        self.assertEqual(est["politica"]["huella"], "ab" * 32)
        self.assertNotIn("politica", est["politica"])          # el fichero entero no viaja al navegador
        fam = {f["familia"]: f["origen"] for f in est["familias"]}
        self.assertEqual(fam["reconocimiento"], "fichero")
        self.assertEqual(est["zonas"][0]["origen"], "fichero")

    def test_un_cambio_de_consola_cambia_el_origen_y_aparece_como_diferencia(self):
        srv = self._srv(POL)
        self._cambiar(srv, "familia", "reconocimiento", "humano_siempre")
        _, est = self._req(srv, "GET", "/api/politica")
        fam = {f["familia"]: f for f in est["familias"]}
        self.assertEqual(fam["reconocimiento"]["origen"], "consola")
        [d] = est["diferencias"]
        self.assertEqual((d["dimension"], d["clave"], d["antes"], d["despues"], d["operador"]),
                         ("familia", "reconocimiento", "automatica_si_confianza", "humano_siempre", "ana"))
        self.assertTrue(d["en"])

    def test_confianza_e_intocables(self):
        pol = {**POL, "confianza": {"administradores": ["10.0.0.1"], "sospechar_si_rafaga": {"alertas": 9, "en_segundos": 60}},
               "nunca_tocar_en_automatico": [{"equipo": "srv", "servicio": 5432}]}
        _, est = self._req(self._srv(pol), "GET", "/api/politica")
        self.assertEqual(est["confianza"]["administradores"], ["10.0.0.1"])
        self.assertEqual(est["confianza"]["rafaga"], {"alertas": 9, "en_segundos": 60})
        self.assertEqual(est["confianza"]["origen"], "fichero")
        self.assertEqual(est["intocables"], [{"activo": "srv", "servicio": 5432, "origen": "fichero", "funcion": None}])
        _, sin = self._req(self._srv(), "GET", "/api/politica")
        self.assertEqual((sin["confianza"]["administradores"], sin["intocables"]), ([], []))

    def test_intocables_dicen_que_es_el_equipo(self):
        # El Resumen de Políticas dice «core-db · base de datos del core», no solo el nombre y el puerto.
        pol = {**POL, "nunca_tocar_en_automatico": [{"equipo": "srv", "servicio": 5432}]}
        srv = self._srv(pol)
        srv.perfil["activos"]["srv"]["funcion"] = "base de datos"
        _, est = self._req(srv, "GET", "/api/politica")
        self.assertEqual(est["intocables"][0]["funcion"], "base de datos")

    def test_la_confianza_dice_si_los_equipos_propios_exigen_analista(self):
        _, sin = self._req(self._srv(), "GET", "/api/politica")
        self.assertEqual((sin["confianza"]["equipos_propios"], sin["confianza"]["equipos_propios_origen"]),
                         ("humano_siempre", "codigo"))
        pol = {**POL, "respuesta_automatica": {**POL["respuesta_automatica"], "equipos_propios": "si_hay_certeza"}}
        _, con = self._req(self._srv(pol), "GET", "/api/politica")
        self.assertEqual((con["confianza"]["equipos_propios"], con["confianza"]["equipos_propios_origen"]),
                         ("automatica_si_confianza", "fichero"))

    def test_explicar(self):
        st, r = self._req(self._srv(POL), "GET", "/api/politica/explicar")
        self.assertEqual(st, 200)
        self.assertTrue(any("Core" in f for f in r["frases"]))

    def test_propuesta_con_los_cambios_de_consola_sin_escribir_nada(self):
        srv = self._srv(POL)
        self._cambiar(srv, "activo", "srv", "humano_siempre")
        st, r = self._req(srv, "GET", "/api/politica/propuesta")
        self.assertEqual(st, 200)
        p = yaml.safe_load(r["yaml"])
        self.assertEqual((r["version"], p["politica"]["version"], p["politica"]["basada_en"]), (4, 4, 3))
        self.assertEqual(p["respuesta_automatica"]["por_equipo"], {"srv": "con_analista"})
        self.assertEqual(srv.politica_info["politica"]["politica"]["version"], 3)

    def test_la_consola_no_puede_aflojar_la_politica(self):
        pol = {**POL, "respuesta_automatica": {**POL["respuesta_automatica"],
                                               "por_tipo_de_ataque": {"acceso_credenciales": "con_analista"}}}
        srv = self._srv(pol)
        with mock.patch.dict(os.environ, {"TRIAJE_POLITICA_ABIERTA": "1"}):
            for dim, clave in (("familia", "acceso_credenciales"), ("zona", "Core"), ("activo", "srv")):
                st, r = self._req(srv, "POST", "/api/politica", {"dimension": dim, "clave": clave,
                                  "automatizacion": "automatica_si_confianza", "operador": "ana"})
                self.assertEqual(st, 400, (dim, r))
        self.assertFalse(os.path.exists(self.ov))

    def test_un_overlay_antiguo_que_afloja_o_ya_coincide_no_cuenta(self):
        srv = self._srv(POL)
        with open(self.ov, "w", encoding="utf-8") as f:     # escrito antes de la política, o ya aprobado
            yaml.safe_dump({"politicas_por_zona": {"Core": {"automatizacion": "automatica_si_confianza"}},
                            "automatizacion_por_familia": {"reconocimiento": {"automatizacion": "automatica_si_confianza"}}}, f)
        _, est = self._req(srv, "GET", "/api/politica")
        self.assertEqual(est["diferencias"], [])
        self.assertEqual({f["familia"]: f["origen"] for f in est["familias"]}["reconocimiento"], "fichero")
        _, r = self._req(srv, "GET", "/api/politica/propuesta")
        p = yaml.safe_load(r["yaml"])
        self.assertEqual(p["respuesta_automatica"]["por_zona"], {"Core": "con_analista"})

    def test_propuesta_sin_politica_parte_del_perfil(self):
        st, r = self._req(self._srv(), "GET", "/api/politica/propuesta")
        self.assertEqual((st, r["version"]), (200, 1))


if __name__ == "__main__":
    unittest.main()
