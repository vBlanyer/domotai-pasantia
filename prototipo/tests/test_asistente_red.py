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
            # «gateway» (descartar fw-interno) ya no bloquea: lo que salía por él se reengancha a su siguiente
            # salto (TestCambiosDelTecnico.test_descartar_un_cortafuegos_reengancha_lo_que_salia_por_el).
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


def _sin_camino(b, ip):
    b = copy.deepcopy(b)
    b["equipos"][ip].update({"gateway": None, "sin_camino": True})
    return b


class TestCambiosDelTecnico(unittest.TestCase):
    """Revisión del 23/11: lo que la consola tiene que dejar corregir sin tocar el fichero a mano."""

    def setUp(self):
        self.b = _oficina()

    def test_zona_vacia_es_sin_zona(self):
        self.assertIsNone(a.aplicar_cambios(self.b, {"10.20.0.10": {"zona": ""}})["equipos"]["10.20.0.10"]["zona"])

    def test_indicar_el_cortafuegos_quita_sin_camino_y_deducido(self):
        b = _sin_camino(self.b, "10.20.0.10")
        b["equipos"]["10.20.0.10"]["deducido"] = True
        e = a.aplicar_cambios(b, {"10.20.0.10": {"gateway": "10.0.0.2"}})["equipos"]["10.20.0.10"]
        self.assertEqual((e["gateway"], e["sin_camino"], e["deducido"]), ("10.0.0.2", False, False))
        self.assertFalse([x for x in a.validar(a.aplicar_cambios(b, {"10.20.0.10": {"gateway": "10.0.0.2"}}), CAT)["avisos"]
                          if "srv-app01: sin camino" in x])

    def test_un_cortafuegos_no_puede_ser_su_propio_gateway_ni_cerrar_un_ciclo(self):
        with self.assertRaises(ValueError):
            a.aplicar_cambios(self.b, {"10.0.0.2": {"gateway": "10.0.0.2"}})
        with self.assertRaises(ValueError) as cm:
            a.aplicar_cambios(self.b, {"10.99.0.1": {"gateway": "10.0.0.2"}})     # fw-interno ya sale por fw-borde
        self.assertIn("ciclo", str(cm.exception))

    def test_descartar_un_cortafuegos_reengancha_lo_que_salia_por_el(self):
        b = a.aplicar_cambios(self.b, {"10.0.0.2": {"incluido": False}})
        for ip in ("10.20.0.10", "10.20.0.20", "10.20.0.30"):
            self.assertEqual(b["equipos"][ip]["gateway"], "10.99.0.1", ip)
        self.assertFalse([x for x in a.validar(b, CAT)["errores"] if "descartado" in x])

    def test_un_cortafuegos_que_pasa_a_servidor_tambien_reengancha(self):
        b = a.aplicar_cambios(self.b, {"10.0.0.2": {"papel": "servidor"}})
        self.assertEqual(b["equipos"]["10.20.0.10"]["gateway"], "10.99.0.1")

    def test_pasar_a_cortafuegos_vacia_sus_dependencias(self):
        b = a.aplicar_cambios(self.b, {"10.20.0.10": {"papel": "cortafuegos"}})
        self.assertEqual(b["equipos"]["10.20.0.10"]["depende_de"], [])


class TestCambiosParciales(unittest.TestCase):
    def test_lo_valido_se_guarda_y_lo_invalido_se_devuelve(self):
        b = a.borrador_inicial(DESC)
        nuevo, rechazados = a.aplicar_cambios_parcial(
            b, {"10.99.0.1": {"nombre": "fw core ñ", "criticidad": "alta"}, "10.0.0.2": {"nombre": "fw-interno"},
                "1.2.3.4": {"nombre": "x"}})
        self.assertEqual(nuevo["equipos"]["10.0.0.2"]["nombre"], "fw-interno")
        self.assertEqual(nuevo["equipos"]["10.99.0.1"]["criticidad"], "alta")
        self.assertEqual(nuevo["equipos"]["10.99.0.1"]["nombre"], "")
        self.assertEqual(sorted((r["ip"], r["campo"]) for r in rechazados), [("1.2.3.4", None), ("10.99.0.1", "nombre")])
        self.assertTrue(all(r["error"] for r in rechazados))


class TestSaltosDelProveedor(unittest.TestCase):
    """Doble NAT: el traceroute hacia fuera cruza routers privados del proveedor después del borde."""

    def setUp(self):
        desc = copy.deepcopy(DESC)
        desc["salida"] = ["10.99.0.1", "192.168.1.1", "10.255.0.1"]
        self.b = a.borrador_inicial(desc)

    def test_avisa_de_que_un_salto_de_fuera_puede_ser_del_proveedor(self):
        avisos = a.validar(self.b, CAT)["avisos"]
        self.assertTrue(any("192.168.1.1" in x and "proveedor" in x for x in avisos), avisos)

    def test_descartarlos_deja_el_borde_del_cliente_y_saca_sus_redes(self):
        cambios = {ip: {"nombre": n} for ip, n in NOMBRES.items()}
        cambios.update({"192.168.1.1": {"incluido": False}, "10.255.0.1": {"incluido": False}})
        b = a.aplicar_cambios(self.b, cambios)
        self.assertIsNone(b["equipos"]["10.99.0.1"]["gateway"])            # fw-borde vuelve a ser el borde
        v = a.validar(b, CAT)
        self.assertEqual(v["errores"], [])
        redes = a.perfil_desde_borrador(b)["redes_internas"]
        self.assertNotIn("192.168.1.0/24", redes)
        self.assertNotIn("10.255.0.0/24", redes)
        self.assertIn("10.20.0.0/24", redes)


class TestValidarComoValidarPerfil(unittest.TestCase):
    """«Validar» promete las mismas reglas que `mdr validar-perfil`: sin errores aquí, sin avisos allí."""

    def _validar_perfil(self, b):
        from prototipo.servicio import stream
        perfil = a.perfil_desde_borrador(b)
        return list(perfilm.validar(perfil)) + stream.lineas_avisos_red(perfil)

    def test_el_caso_de_la_oficina_pasa_las_dos(self):
        b = _oficina()
        self.assertEqual(a.validar(b, CAT)["errores"], [])
        self.assertEqual(self._validar_perfil(b), [])

    def test_un_ciclo_entre_cortafuegos_es_un_error(self):
        b = _oficina()
        b["equipos"]["10.99.0.1"]["gateway"] = "10.0.0.2"                   # rutas asimétricas (o fichero a mano)
        errores = a.validar(b, CAT)["errores"]
        self.assertTrue(any("ciclo" in x for x in errores), errores)
        self.assertTrue(self._validar_perfil(b))

    def test_los_avisos_del_mapa_cuentan_como_errores(self):
        # validar-perfil sale con 1 ante cualquier aviso del mapa (tablero.estado_red): aquí no puede ser «sin errores».
        from unittest import mock
        from prototipo.servicio import tablero
        real = tablero.estado_red
        with mock.patch.object(tablero, "estado_red", lambda p, *x: {**real(p, *x), "avisos": ["enlace a un nodo que no existe"]}):
            errores = a.validar(_oficina(), CAT)["errores"]
        self.assertTrue(any("enlace a un nodo que no existe" in x for x in errores), errores)

    def test_sin_salida_trazada_se_avisa(self):
        b = _oficina()
        b["salida"] = []
        self.assertTrue(any("salida" in x and "internet" in x for x in a.validar(b, CAT)["avisos"]))


class TestConservarAlReescanear(unittest.TestCase):
    def test_lo_escrito_para_las_mismas_ips_se_conserva(self):
        viejo = _oficina()
        nuevo = a.conservar_trabajo(viejo, a.borrador_inicial(DESC))
        for ip, n in NOMBRES.items():
            self.assertEqual(nuevo["equipos"][ip]["nombre"], n, ip)
        self.assertEqual(nuevo["equipos"]["10.20.0.20"]["criticidad"], "critica")
        self.assertTrue(nuevo["equipos"]["10.20.0.20"]["no_tocar"])
        self.assertEqual(nuevo["equipos"]["10.20.0.10"]["depende_de"], ["srv-db01"])
        self.assertEqual(nuevo["equipos"]["172.16.10.10"]["zona"], "DMZ")
        self.assertEqual(a.validar(nuevo, CAT)["errores"], [])

    def test_lo_que_ya_no_esta_no_se_inventa_y_lo_nuevo_queda_como_viene(self):
        viejo = _oficina()
        desc = copy.deepcopy(DESC)
        desc["equipos"] = [e for e in desc["equipos"] if e["ip"] != "10.20.0.30"]
        nuevo = a.conservar_trabajo(viejo, a.borrador_inicial(desc))
        self.assertNotIn("10.20.0.30", nuevo["equipos"])
        self.assertEqual(a.conservar_trabajo(None, a.borrador_inicial(DESC)), a.borrador_inicial(DESC))

    def test_un_gateway_que_ya_no_es_cortafuegos_no_se_arrastra(self):
        viejo = a.aplicar_cambios(_oficina(), {"10.20.0.10": {"gateway": "10.99.0.1"}})
        desc = copy.deepcopy(DESC)
        desc["salida"] = []
        desc["equipos"] = [e for e in desc["equipos"] if e["ip"] != "10.99.0.1"]
        for e in desc["equipos"]:
            e["saltos"] = [s for s in (e.get("saltos") or []) if s != "10.99.0.1"] if e.get("saltos") is not None else None
        nuevo = a.conservar_trabajo(viejo, a.borrador_inicial(desc))
        self.assertNotEqual(nuevo["equipos"]["10.20.0.10"].get("gateway"), "10.99.0.1")


class TestInterfacesUnSoloDueno(unittest.TestCase):
    def test_una_ip_no_es_interfaz_de_dos_cortafuegos(self):
        # Banco (23/11): todos los nodos comparten clave SSH; dos «cortafuegos» se quedaban las MISMAS 52 IPs.
        desc = copy.deepcopy(DESC)
        huella = next(e["huella_ssh"] for e in desc["equipos"] if e["ip"] == "10.99.0.1")
        for e in desc["equipos"]:
            if e["ip"] == "10.0.0.2":
                e["huella_ssh"] = huella
                e["puertos"] = [p for p in next(x for x in desc["equipos"] if x["ip"] == "10.99.0.1")["puertos"]]
        b = a.borrador_inicial(desc)
        todas = [i for e in b["equipos"].values() for i in e["interfaces"]]
        self.assertEqual(len(todas), len(set(todas)), todas)
