"""De lo descubierto a una propuesta (plan del asistente de red, tarea 4). fixtures/nmap/descubrimiento.json
es el escaneo REAL del laboratorio oficina (mdr descubrir del 11/11/2026)."""
import copy
import json
import os
import unittest

from prototipo.accion import catalogo as catm
from prototipo.motor import perfil as perfilm
from prototipo.motor import politica_empresa as pe
from prototipo.servicio import asistente_red as a
from prototipo.servicio import red as redm

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = catm.cargar_catalogo(os.path.join(RAIZ, "catalogo.yml"))
with open(os.path.join(os.path.dirname(__file__), "fixtures", "nmap", "descubrimiento.json"), encoding="utf-8") as f:
    DESC = json.load(f)

NOMBRES = {"10.99.0.1": "fw-borde", "10.0.0.2": "fw-interno", "172.16.10.10": "srv-web01",
           "172.16.10.20": "srv-correo01", "10.20.0.10": "srv-app01", "10.20.0.20": "srv-db01",
           "10.20.0.30": "nas01", "10.20.0.50": "impresora"}


def _oficina():
    b = a.borrador_inicial(DESC)
    cambios = {ip: {"nombre": n} for ip, n in NOMBRES.items()}
    for ip in ("172.16.10.10", "172.16.10.20"):
        cambios[ip]["zona"] = "DMZ"
    for ip in ("10.20.0.10", "10.20.0.20", "10.20.0.30", "10.20.0.50"):
        cambios[ip]["zona"] = "Interna"
    cambios["10.20.0.20"].update({"no_tocar": True, "criticidad": "critica"})
    cambios["172.16.10.10"]["depende_de"] = ["srv-app01"]
    cambios["10.20.0.10"]["depende_de"] = ["srv-db01"]
    return a.aplicar_cambios(b, cambios)


class TestBorradorInicial(unittest.TestCase):
    def setUp(self):
        self.b = a.borrador_inicial(DESC)
        self.e = self.b["equipos"]

    def test_el_mdr_no_es_un_equipo_descubierto(self):
        self.assertNotIn("10.99.0.10", self.e)
        self.assertEqual(self.b["gestion"], "10.99.0.10")

    def test_interfaces_de_un_cortafuegos_se_agrupan_por_huella(self):
        self.assertEqual(self.e["10.99.0.1"]["papel"], "cortafuegos")
        self.assertEqual(sorted(self.e["10.99.0.1"]["interfaces"]), ["10.0.0.1", "172.16.10.1"])
        self.assertEqual(self.e["10.0.0.2"]["interfaces"], ["10.20.0.1"])
        for ip in ("10.0.0.1", "172.16.10.1", "10.20.0.1"):
            self.assertNotIn(ip, self.e)                   # no salen como equipos sueltos

    def test_cadena_hacia_fuera(self):
        self.assertIsNone(self.e["10.99.0.1"]["gateway"])               # borde
        self.assertEqual(self.e["10.0.0.2"]["gateway"], "10.99.0.1")
        self.assertTrue(self.e["10.0.0.2"]["deducido"])
        self.assertFalse(self.e["10.99.0.1"]["deducido"])

    def test_gateway_y_zona_de_cada_equipo(self):
        self.assertEqual(self.e["172.16.10.10"]["gateway"], "10.99.0.1")
        self.assertEqual(self.e["10.20.0.10"]["gateway"], "10.0.0.2")
        self.assertEqual(self.e["10.20.0.10"]["zona"], "Zona 10.20.0.0/24")
        self.assertEqual(self.e["172.16.10.20"]["zona"], "Zona 172.16.10.0/24")
        self.assertEqual(self.e["10.20.0.10"]["servicios"], [22, 8443])

    def test_papeles(self):
        self.assertEqual(self.e["10.20.0.50"]["papel"], "fragil")
        self.assertEqual(self.e["10.20.0.10"]["papel"], "servidor")
        self.assertEqual(self.e["10.20.0.77"]["papel"], "desconocido")
        self.assertFalse(self.e["10.20.0.77"]["incluido"])
        self.assertTrue(self.e["10.20.0.50"]["incluido"])

    def test_traceroute_ausente_no_inventa_gateway(self):
        sin = copy.deepcopy(DESC)
        for e in sin["equipos"]:
            e["saltos"] = None
        sin["salida"], sin["traceroute"] = None, False
        b = a.borrador_inicial(sin)
        app = b["equipos"]["10.20.0.10"]
        self.assertIsNone(app["gateway"])
        self.assertTrue(app["sin_camino"])
        self.assertFalse(any(e["papel"] == "cortafuegos" for e in b["equipos"].values()))
        self.assertTrue(any("traceroute" in x for x in a.validar(b, CAT)["avisos"]))

    def test_un_salto_mudo_no_es_un_gateway(self):
        hueco = copy.deepcopy(DESC)
        for e in hueco["equipos"]:
            if e["ip"] == "10.20.0.10":
                e["saltos"] = ["10.99.0.1", None]
        app = a.borrador_inicial(hueco)["equipos"]["10.20.0.10"]
        self.assertIsNone(app["gateway"])
        self.assertTrue(app["sin_camino"])


class TestPropuesta(unittest.TestCase):
    def setUp(self):
        self.b = _oficina()
        self.perfil = a.perfil_desde_borrador(self.b)

    def test_perfil_de_la_oficina_valida(self):
        self.assertEqual(perfilm.validar(self.perfil), [])
        t = self.perfil["topologia"]
        self.assertEqual(t["srv-app01"]["gateway"], "fw-interno")
        self.assertEqual(t["fw-interno"], {"rol": "firewall_perimetral", "ip": "10.0.0.2", "gateway": "fw-borde"})
        self.assertNotIn("gateway", t["fw-borde"])
        self.assertNotIn("srv-db01", t)                     # no tocar directamente
        self.assertNotIn("impresora", t)                    # frágil
        self.assertEqual(self.perfil["activos"]["srv-web01"]["depende_de"], ["srv-app01"])
        self.assertEqual(self.perfil["activos"]["srv-db01"]["criticidad"], "critica")
        self.assertEqual(self.perfil["ip_gestion"], "10.99.0.10")
        self.assertEqual(self.perfil["redes_internas"], DESC["rangos"])
        self.assertNotIn("origenes_legitimos", self.perfil)          # la confianza va en politica.yml

    def test_la_red_dibuja_lo_mismo(self):
        r = redm.red_de(self.perfil)
        self.assertEqual(r.get("avisos") or [], [])
        self.assertEqual(sorted(z for z, _ in r["zonas"]), ["DMZ", "Gestión", "Interna"])
        self.assertIn("fw-borde", r["nodos"])
        self.assertIn("internet", r["nodos"])
        self.assertEqual(self.perfil["red"]["enlaces"]["fw-borde"], "internet")
        self.assertEqual(self.perfil["red"]["enlaces"]["mdr"], "fw-borde")
        self.assertEqual(self.perfil["red"]["enlaces"]["srv-db01"], "fw-interno")

    def test_politica_valida_con_ese_perfil(self):
        pol = a.politica_desde(self.b, "2026-11-11")
        self.assertEqual(pe.validar_politica(pol, self.perfil, CAT), [])
        self.assertEqual(pol["confianza"]["administradores"], ["10.99.0.10"])
        self.assertIn("pendiente", pol["politica"]["aprobada_por"])

    def test_postura_por_nombre(self):
        post = a.postura_desde(DESC, self.b)
        self.assertEqual(post["nodos"]["srv-db01"], [{"puerto": 22, "servicio": "ssh", "estado": "open"},
                                                     {"puerto": 5432, "servicio": "postgresql", "estado": "open"}])
        self.assertIn("fw-borde", post["nodos"])
        self.assertNotIn("10.20.0.77", json.dumps(post))

    def test_la_oficina_completa_no_tiene_errores(self):
        v = a.validar(self.b, CAT)
        self.assertEqual(v["errores"], [])

    def test_errores_bloqueantes(self):
        casos = {
            "sin nombre": {"10.20.0.30": {"nombre": ""}},
            "repetido": {"10.20.0.30": {"nombre": "srv-app01"}},
            "dependencia": {"10.20.0.77": {"incluido": False}, "10.20.0.10": {"depende_de": ["nadie"]}},
            "gateway": {"10.0.0.2": {"incluido": False}},
        }
        for nombre, cambios in casos.items():
            with self.subTest(caso=nombre):
                self.assertTrue(a.validar(a.aplicar_cambios(self.b, cambios), CAT)["errores"])

    def test_avisos_fuera_de_cadena(self):
        avisos = a.validar(self.b, CAT)["avisos"]
        for nombre in ("srv-db01", "impresora"):
            self.assertTrue(any(nombre in x and "perimetrales" in x for x in avisos), nombre)
        self.assertTrue(any("fw-interno" in x and "confírma" in x for x in avisos))

    def test_aplicar_cambios_rechaza_claves_desconocidas(self):
        for cambios in ({"10.20.0.10": {"rol": "x"}}, {"1.2.3.4": {"nombre": "x"}}, {"10.20.0.10": {"nombre": "Con Espacios"}},
                        {"10.20.0.10": {"papel": "dios"}}, {"10.20.0.10": {"criticidad": "extrema"}},
                        {"10.20.0.10": {"gateway": "10.20.0.30"}}, {"10.20.0.10": {"incluido": "si"}}):
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                a.aplicar_cambios(self.b, cambios)
        self.assertEqual(self.b["equipos"]["10.20.0.10"]["nombre"], "srv-app01")     # no muta

    def test_nombres_del_siem(self):
        regs = [{"activo": "srv-web01"}, {"activo": "srv-web01", "tipo": "decision"}, {"activo": "nas01"},
                {"activo": "mdr"}, {"activo": "desconocido"}, {"activo": "x", "tipo": "auditoria_conectividad"}]
        self.assertEqual(a.nombres_del_siem(regs, perfilm.perfil_minimo("10.99.0.10", ["10.20.0.0/24"])),
                         ["srv-web01", "nas01"])


if __name__ == "__main__":
    unittest.main()


class TestCasosReales(unittest.TestCase):
    """Revisión final: lo que encuentra un técnico en un cliente real."""
    def test_rangos_sin_transito_ni_gestion_no_dicen_directo(self):
        solo = copy.deepcopy(DESC)
        solo["rangos"] = ["172.16.10.0/24", "10.20.0.0/24"]
        solo["equipos"] = [e for e in solo["equipos"] if not e["ip"].startswith(("10.0.0.", "10.99.0."))]
        b = a.borrador_inicial(solo)
        self.assertEqual(b["equipos"]["10.20.0.10"]["gateway"], "10.0.0.2")
        self.assertEqual(b["equipos"]["172.16.10.10"]["gateway"], "10.99.0.1")
        self.assertEqual(b["equipos"]["10.99.0.1"]["papel"], "cortafuegos")
        self.assertIn("10.99.0.0/24", b["redes_internas"])
        self.assertIn("10.0.0.0/24", b["redes_internas"])
        self.assertTrue(any("fuera de los rangos" in x for x in a.validar(b, CAT)["avisos"]))

    def test_huella_clonada_no_absorbe_servidores_detras_del_cortafuegos(self):
        clon = copy.deepcopy(DESC)
        fw = next(e for e in clon["equipos"] if e["ip"] == "10.0.0.2")["huella_ssh"]
        for e in clon["equipos"]:
            if e["ip"] in ("10.20.0.10", "10.20.0.20"):
                e["huella_ssh"] = fw
        b = a.borrador_inicial(clon)
        self.assertIn("10.20.0.10", b["equipos"])
        self.assertIn("10.20.0.20", b["equipos"])
        self.assertEqual(b["equipos"]["10.0.0.2"]["interfaces"], ["10.20.0.1"])

    def test_huella_clonada_en_el_mismo_segmento_se_avisa(self):
        clon = copy.deepcopy(DESC)
        fw = next(e for e in clon["equipos"] if e["ip"] == "10.99.0.1")["huella_ssh"]
        for e in clon["equipos"]:
            if e["ip"] == "172.16.10.1":
                e["puertos"].append({"puerto": 443, "servicio": "https", "producto": None, "version": None})
                e["huella_ssh"] = fw
        b = a.borrador_inicial(clon)
        self.assertIn("172.16.10.1", b["equipos"])                     # puertos distintos: no es una interfaz
        self.assertTrue(any("172.16.10.1" in x and "huella" in x for x in a.validar(b, CAT)["avisos"]))

    def test_nombres_como_los_trae_el_siem(self):
        b = a.aplicar_cambios(_oficina(), {"172.16.10.10": {"nombre": "WEB01.cliente.local"}, "10.20.0.30": {"nombre": "NAS_01"}})
        self.assertEqual(b["equipos"]["172.16.10.10"]["nombre"], "WEB01.cliente.local")
        self.assertEqual(a.validar(b, CAT)["errores"], [])

    def test_nombres_y_zona_reservados(self):
        for cambios in ({"10.20.0.30": {"nombre": "mdr"}}, {"10.20.0.30": {"nombre": "internet"}},
                        {"10.20.0.30": {"zona": "Gestión"}}):
            with self.subTest(cambios=cambios):
                self.assertTrue(a.validar(a.aplicar_cambios(_oficina(), cambios), CAT)["errores"])
