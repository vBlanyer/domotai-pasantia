"""Tests del generador de la demo de geolocalización. El contrato: cada ataque sintético lleva una
IP de origen PÚBLICA que geolocaliza por el pipeline real, y la campaña cubre varios países."""
import io
import json
import os
import unittest

from lab.geo_demo import generador
from prototipo.entrada import adaptador_wazuh
from prototipo.motor import actores


def _normalizar(cruda):
    """La misma normalización que hace el daemon (stream) sobre la fuente Wazuh."""
    return adaptador_wazuh.normalizar_alerta(cruda, "geo-demo")


class TestPoolPublico(unittest.TestCase):
    def test_todas_las_ips_son_publicas_y_geolocalizan(self):
        pool = generador.pool_publico()
        self.assertTrue(pool)
        for ip, pais, _codigo in pool:
            self.assertEqual(actores.clasificar_ip(ip), "publica", ip)
            geo = actores.geolocalizar(ip)              # geolocaliza por el pipeline real
            self.assertIsNotNone(geo, ip)
            self.assertEqual(geo["pais"], pais, ip)

    def test_cubre_varios_paises(self):
        paises = {p for _ip, p, _c in generador.pool_publico()}
        self.assertGreaterEqual(len(paises), 10)        # la tabla de muestra trae 14

    def test_la_ip_siempre_cae_dentro_del_cidr_incluso_en_bloques_pequenos(self):
        # Si alguien añade un bloque pequeño (/30, /32) a la tabla, la IP elegida DEBE seguir
        # dentro del CIDR, o geolocalizaría mal (otro país) o se caería. Tabla inyectada.
        import ipaddress
        tabla = [{"cidr": "203.0.113.0/30", "pais": "A", "codigo": "A"},
                 {"cidr": "198.51.100.7/32", "pais": "B", "codigo": "B"},
                 {"cidr": "8.8.8.0/24", "pais": "C", "codigo": "C"}]
        pool = generador.pool_publico(tabla=tabla)
        self.assertEqual(len(pool), 3)
        for (ip, _p, _c), e in zip(pool, tabla):
            self.assertIn(ipaddress.ip_address(ip), ipaddress.ip_network(e["cidr"]), e["cidr"])


class TestAlertaCruda(unittest.TestCase):
    def test_fija_el_origen_publico_el_activo_y_la_familia(self):
        cruda = generador.alerta_cruda("8.8.8.8", "reconocimiento", "web-banking")
        a = _normalizar(cruda)
        self.assertEqual(a["origen_ip"], "8.8.8.8")
        self.assertEqual(a["activo"], "web-banking")
        self.assertEqual(a["familia"], "reconocimiento")

    def test_cada_familia_se_clasifica_como_tal(self):
        for fam in generador.FAMILIAS:
            cruda = generador.alerta_cruda("5.45.0.1", fam, "core-db")
            self.assertEqual(_normalizar(cruda)["familia"], fam, fam)

    def test_el_evento_crudo_se_marca_como_demo_sintetica(self):
        a = _normalizar(generador.alerta_cruda("8.8.8.8", "reconocimiento", "web-banking"))
        self.assertIn("DEMO SINTÉTICA", a.get("evento_crudo") or "")

    def test_familia_desconocida_es_error(self):
        with self.assertRaises(ValueError):
            generador.alerta_cruda("8.8.8.8", "no_existe", "core-db")


class TestCampañaMundial(unittest.TestCase):
    def test_todas_geolocalizan_y_las_familias_son_validas(self):
        alertas = generador.campaña_mundial()
        self.assertGreaterEqual(len(alertas), 10)
        paises = set()
        for cruda in alertas:
            a = _normalizar(cruda)
            geo = actores.geolocalizar(a["origen_ip"])
            self.assertIsNotNone(geo, a["origen_ip"])
            self.assertIn(a["familia"], generador.FAMILIAS)
            paises.add(geo["pais"])
        self.assertGreaterEqual(len(paises), 10)        # campaña mundial: el mapa se enciende

    def test_es_reproducible_con_semilla(self):
        unos = [a["id"] for a in generador.campaña_mundial(semilla=7)]
        otros = [a["id"] for a in generador.campaña_mundial(semilla=7)]
        self.assertEqual(unos, otros)


class TestEmitir(unittest.TestCase):
    def test_escribe_una_linea_json_por_alerta(self):
        buf = io.StringIO()
        alertas = generador.campaña_mundial(semilla=1)
        generador.emitir(alertas, salida=buf, pausa=0)   # pausa 0: no duerme en los tests
        lineas = [l for l in buf.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(lineas), len(alertas))
        reconstruidas = [json.loads(l) for l in lineas]  # cada línea es JSON válido (lo que lee stream)
        self.assertEqual([r["id"] for r in reconstruidas], [a["id"] for a in alertas])


class TestExtremoAExtremo(unittest.TestCase):
    """El camino real del daemon: generar → normalizar → triaje.procesar → _resumen_traza (la fila
    del feed que consume la vista Ubicaciones). Prueba, sin contenedores, que el mapa se encenderá."""
    def test_una_alerta_generada_produce_una_fila_con_pais(self):
        from prototipo.motor import perfil as perfilm, triaje
        from prototipo.accion import catalogo as catm
        from prototipo.servicio import tablero
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        perfil = perfilm.cargar(os.path.join(base, "prototipo/perfiles/bancario.yml"))
        with open(os.path.join(base, "prototipo/tests/fixtures/hallazgos.json"), encoding="utf-8") as f:
            hallazgos = json.load(f)
        catalogo = catm.cargar_catalogo(os.path.join(base, "prototipo/catalogo.yml"))
        cruda = generador.alerta_cruda("8.8.8.8", "reconocimiento", "web-banking")
        alerta = _normalizar(cruda)
        reg = triaje.procesar(alerta, hallazgos, perfil, "bancario", catalogo,
                              id_decision="d0", timestamp=alerta["timestamp"])
        fila = tablero._resumen_traza(reg, perfil=perfil)
        self.assertEqual(fila["origen_ip"], "8.8.8.8")
        enr = fila["enriquecimiento_origen"]
        self.assertEqual(enr["alcance"], "externo")
        self.assertEqual(enr["geo"]["pais"], "Estados Unidos")
        self.assertEqual(enr["asn"]["org"], "Google LLC")


if __name__ == "__main__":
    unittest.main()
