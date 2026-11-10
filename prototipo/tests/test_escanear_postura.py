import json, os, tempfile, unittest
from prototipo.herramientas import escanear_postura as ep

SALIDA_NMAP = """Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 192.0.2.10
PORT    STATE    SERVICE
22/tcp  open     ssh
80/tcp  open     http
443/tcp filtered https
"""

PERFIL = {"activos": {"web01": {"ip": "192.0.2.10"}, "db01": {"ip": "10.20.0.20"}, "sin-ip": {}}}


class _Res:
    def __init__(self, rc, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


def ejecutor(fallan=()):
    llamadas = []

    def run(args, **kw):
        llamadas.append(args)
        if args[:2] == ["nmap", "--version"]:
            return _Res(0, "Nmap version 7.94 ( https://nmap.org )\n")
        return _Res(1) if args[-1] in fallan else _Res(0, SALIDA_NMAP)
    run.llamadas = llamadas
    return run


class TestEscanearPostura(unittest.TestCase):
    def test_formato_que_consume_el_motor(self):
        h, omitidos = ep.escanear(PERFIL, ejecutar=ejecutor(), ahora="2026-11-09T10:00:00Z")
        self.assertEqual(h["version_herramienta"], "Nmap version 7.94")
        self.assertEqual(h["timestamp"], "2026-11-09T10:00:00Z")
        self.assertEqual(set(h["nodos"]), {"web01", "db01"})
        self.assertIn({"puerto": 22, "servicio": "ssh", "estado": "open"}, h["nodos"]["web01"])
        self.assertIn({"puerto": 443, "servicio": "https", "estado": "filtered"}, h["nodos"]["web01"])
        self.assertEqual(omitidos, [])

    def test_un_escaneo_fallido_se_omite_y_no_se_escribe_vacio(self):
        # Una lista vacía diría «escaneado, sin puertos» y voltearía un ataque real a falso positivo.
        h, omitidos = ep.escanear(PERFIL, ejecutar=ejecutor(fallan={"10.20.0.20"}))
        self.assertNotIn("db01", h["nodos"])
        self.assertEqual(omitidos, ["db01"])

    def test_sin_nmap_no_escribe_nada(self):
        def sin_nmap(args, **kw):
            raise FileNotFoundError("nmap")
        with self.assertRaises(SystemExit):
            ep.escanear(PERFIL, ejecutar=sin_nmap)

    def test_puertos_y_equipos_a_elegir(self):
        run = ejecutor()
        h, _ = ep.escanear(PERFIL, ejecutar=run, puertos="22,5432", equipos=["db01"])
        self.assertEqual(set(h["nodos"]), {"db01"})
        self.assertIn(["nmap", "-Pn", "--host-timeout", "120s", "-p", "22,5432", "10.20.0.20"], run.llamadas)

    def test_por_defecto_los_1000_puertos_habituales(self):
        run = ejecutor()
        ep.escanear({"activos": {"web01": {"ip": "192.0.2.10"}}}, ejecutar=run)
        self.assertIn(["nmap", "-Pn", "--host-timeout", "120s", "--top-ports", "1000", "192.0.2.10"], run.llamadas)

    def test_una_ip_que_no_es_ip_no_llega_a_nmap(self):
        run = ejecutor()
        h, omitidos = ep.escanear({"activos": {"raro": {"ip": "-oN /etc/x"}}}, ejecutar=run)
        self.assertEqual(h["nodos"], {})
        self.assertEqual(omitidos, ["raro"])
        self.assertEqual([a for a in run.llamadas if a[:2] != ["nmap", "--version"]], [])

    def test_escanear_algunos_equipos_conserva_la_postura_del_resto(self):
        anterior = {"version_herramienta": "v0", "timestamp": "t0",
                    "nodos": {"web01": [{"puerto": 80, "servicio": "http", "estado": "open"}],
                              "db01": [{"puerto": 5432, "servicio": "postgresql", "estado": "open"}],
                              "app01": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}
        nuevo = {"version_herramienta": "v1", "timestamp": "t1",
                 "nodos": {"web01": [{"puerto": 443, "servicio": "https", "estado": "open"}]}}
        f = ep.fusionar(anterior, nuevo, intentados=["web01", "app01"])     # app01 falló al reescanear
        self.assertEqual(f["nodos"]["web01"][0]["puerto"], 443)              # actualizado
        self.assertIn("db01", f["nodos"])                                    # no se tocó
        self.assertNotIn("app01", f["nodos"])                                # falló: caso gris, no lo viejo
        self.assertEqual(f["version_herramienta"], "v1")

    def test_escribir_deja_el_fichero_entero(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "postura.json")
            ep.escribir({"version_herramienta": "x", "timestamp": "t", "nodos": {}}, ruta)
            self.assertEqual(json.load(open(ruta))["nodos"], {})
            self.assertEqual(os.listdir(d), ["postura.json"])


if __name__ == "__main__":
    unittest.main()
