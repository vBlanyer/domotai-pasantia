"""Descubrimiento con Nmap (plan del asistente de red, tarea 3). Los XML de fixtures/nmap son la salida
REAL de Nmap 7.95 contra el laboratorio oficina (vivos, detalle y salida), y huellas.txt la de ssh-keyscan."""
import os
import subprocess
import unittest
from unittest import mock

from prototipo.servicio import descubrimiento as d

FX = os.path.join(os.path.dirname(__file__), "fixtures", "nmap")


def _leer(nombre):
    with open(os.path.join(FX, nombre), encoding="utf-8") as f:
        return f.read()


PETICION = {"rangos": ["172.16.10.0/24", "10.20.0.0/24", "10.0.0.0/24", "10.99.0.0/24"],
            "externo": "198.51.100.10", "ritmo": "suave", "puertos": "comunes"}


def _correr_falso(llamadas=None):
    def correr(args):
        if llamadas is not None:
            llamadas.append(list(args))
        if args[0] == "ssh-keyscan":
            return 0, _leer("huellas.txt")
        if "198.51.100.10" in args:
            return 0, _leer("salida.xml")
        if "-sn" in args:
            return 0, _leer("vivos.xml")
        return 0, _leer("detalle.xml")
    return correr


class TestParsear(unittest.TestCase):
    def setUp(self):
        self.det = {e["ip"]: e for e in d.parsear_xml(_leer("detalle.xml"))}

    def test_parsea_puertos_servicios_y_huella(self):
        web = self.det["172.16.10.10"]
        self.assertEqual([(p["puerto"], p["servicio"]) for p in web["puertos"]], [(22, "ssh"), (80, "http"), (443, "https")])
        self.assertIsNone(web["huella_ssh"])                       # la huella la añade ssh-keyscan
        self.assertEqual(self.det["10.20.0.77"]["puertos"], [])
        huellas = d.parsear_huellas(_leer("huellas.txt"))
        self.assertEqual(huellas["10.99.0.1"], huellas["172.16.10.1"])   # fw-borde, dos interfaces
        self.assertEqual(huellas["10.99.0.1"], huellas["10.0.0.1"])
        self.assertNotEqual(huellas["10.0.0.2"], huellas["10.99.0.1"])
        self.assertTrue(huellas["10.20.0.10"].startswith("SHA256:"))

    def test_parsea_saltos_sin_el_propio_equipo(self):
        self.assertEqual(self.det["10.20.0.10"]["saltos"], ["10.99.0.1", "10.0.0.2"])
        self.assertEqual(self.det["172.16.10.10"]["saltos"], ["10.99.0.1"])
        self.assertEqual(self.det["10.99.0.1"]["saltos"], [])

    def test_salto_mudo_queda_como_hueco(self):
        # El primer salto 10.0.0.2 del XML es el de srv-app01 (10.20.0.10): se convierte en otro elemento.
        sin = d.parsear_xml(_leer("detalle.xml").replace('<hop ttl="2" ipaddr="10.0.0.2"', '<borrado ttl="2"', 1))
        app = next(e for e in sin if e["ip"] == "10.20.0.10")
        self.assertEqual(app["saltos"], ["10.99.0.1", None])

    def test_sin_trace_saltos_es_none(self):
        vivos = d.parsear_xml(_leer("vivos.xml"))
        self.assertTrue(vivos)
        self.assertTrue(all(e["saltos"] is None for e in vivos))


class TestArgumentos(unittest.TestCase):
    def test_argumentos_fijos(self):
        p = d.validar_peticion(PETICION)
        ritmo = ["-T3", "--max-rate", "100"]
        self.assertEqual(d.argumentos_vivos(p), ["nmap", "-sn", *ritmo, "-oX", "-", *PETICION["rangos"]])
        self.assertEqual(d.argumentos_detalle(p, ["10.20.0.10"]),
                         ["nmap", "--traceroute", "--host-timeout", "120s", *ritmo, "--top-ports", "1000",
                          "-oX", "-", "10.20.0.10"])
        self.assertEqual(d.argumentos_salida(p), ["nmap", "-sn", "--traceroute", *ritmo, "-oX", "-", "198.51.100.10"])
        self.assertEqual(d.argumentos_huellas(["10.20.0.10"]), ["ssh-keyscan", "-T", "5", "-t", "ed25519", "10.20.0.10"])
        normal = d.validar_peticion({**PETICION, "ritmo": "normal", "puertos": [22, 80]})
        self.assertEqual(d.argumentos_detalle(normal, ["10.0.0.2"]),
                         ["nmap", "--traceroute", "--host-timeout", "120s", "-T4", "-p", "22,80", "-oX", "-", "10.0.0.2"])

    def test_entradas_hostiles_no_llegan_a_nmap(self):
        malas = [{"rangos": ["10.0.0.0/24 --script=x"]}, {"rangos": ["0.0.0.0/0"]}, {"rangos": ["8.8.8.0/24"]},
                 {"rangos": ["10.0.0.0/16"]}, {"rangos": [f"10.0.{i}.0/24" for i in range(9)]}, {"rangos": []},
                 {"rangos": "10.0.0.0/24"}, {"externo": "10.0.0.0/24"}, {"externo": "-oX"}, {"ritmo": "loco"},
                 {"puertos": "22;rm"}, {"puertos": [0]}, {"puertos": ["22"]}, {"puertos": list(range(1, 102))}]
        for cambio in malas:
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                d.validar_peticion({**PETICION, **cambio})

    def test_normaliza_los_rangos(self):
        self.assertEqual(d.validar_peticion({**PETICION, "rangos": ["10.20.0.7/24"]})["rangos"], ["10.20.0.0/24"])


class TestDescubrir(unittest.TestCase):
    def test_descubrir_excluye_al_mdr_y_junta_las_pasadas(self):
        llamadas = []
        r = d.descubrir(d.validar_peticion(PETICION), _correr_falso(llamadas), "10.99.0.10", "ana", "2026-11-11T15:00:00+00:00")
        ips = {e["ip"] for e in r["equipos"]}
        self.assertNotIn("10.99.0.10", ips)
        self.assertEqual(len(ips), 12)
        self.assertNotIn("10.99.0.10", llamadas[1])                         # el detalle no escanea al MDR
        keyscan = next(a for a in llamadas if a[0] == "ssh-keyscan")
        self.assertNotIn("10.20.0.50", keyscan)                             # la impresora no tiene SSH
        por_ip = {e["ip"]: e for e in r["equipos"]}
        self.assertEqual(por_ip["172.16.10.1"]["huella_ssh"], por_ip["10.99.0.1"]["huella_ssh"])
        self.assertEqual(r["salida"], ["10.99.0.1"])
        self.assertTrue(r["traceroute"])
        self.assertEqual((r["operador"], r["gestion"], r["rangos"], r["externo"]),
                         ("ana", "10.99.0.10", PETICION["rangos"], "198.51.100.10"))

    def test_un_fallo_de_nmap_es_runtimeerror(self):
        with self.assertRaises(RuntimeError) as e:
            d.descubrir(d.validar_peticion(PETICION), lambda args: (1, "QUITTING!"), "10.99.0.10", "ana", "t")
        self.assertIn("QUITTING", str(e.exception))

    def test_ejecutor_por_nodo_de_gestion(self):
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "salida", "")
            rc, out = d.ejecutor_nmap({"TRIAJE_NODO_GESTION": "x"})(["nmap", "-sn", "10.0.0.0/24"])
        self.assertEqual(run.call_args[0][0][:4], ["docker", "exec", "x", "nmap"])
        self.assertEqual((rc, out), (0, "salida"))
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            d.ejecutor_nmap({})(["nmap", "-sn", "10.0.0.0/24"])
        self.assertEqual(run.call_args[0][0][0], "nmap")

    def test_ejecutor_con_plazo(self):
        with mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("nmap", 1200)):
            rc, out = d.ejecutor_nmap({})(["nmap"])
        self.assertEqual(rc, 124)


if __name__ == "__main__":
    unittest.main()


class TestCLI(unittest.TestCase):
    def test_cli_escribe_el_descubrimiento(self):
        import io, json, tempfile
        from contextlib import redirect_stdout
        from prototipo.herramientas import descubrir as cli
        salida = os.path.join(tempfile.mkdtemp(), "d.json")
        with mock.patch.object(d, "ejecutor_nmap", return_value=_correr_falso()), redirect_stdout(io.StringIO()) as out:
            rc = cli.main(["--gestion", "10.99.0.10", *sum((["--rango", r] for r in PETICION["rangos"]), []),
                           "--externo", "198.51.100.10", "--salida", salida, "--operador", "ana", "--autorizado"])
        self.assertEqual(rc, 0)
        with open(salida, encoding="utf-8") as f:
            r = json.load(f)
        self.assertEqual(len(r["equipos"]), 12)
        self.assertIn("12 equipos", out.getvalue())

    def test_cli_rechaza_un_rango_publico(self):
        import io
        from contextlib import redirect_stdout
        from prototipo.herramientas import descubrir as cli
        with redirect_stdout(io.StringIO()) as out:
            rc = cli.main(["--gestion", "10.99.0.10", "--rango", "8.8.8.0/24", "--externo", "198.51.100.10", "--salida", "/tmp/x",
                           "--autorizado"])
        self.assertEqual(rc, 1)
        self.assertIn("privadas", out.getvalue())


class TestTrazaIncompleta(unittest.TestCase):
    def test_traza_que_no_llega_al_equipo_acaba_en_hueco(self):
        xml = _leer("detalle.xml").replace('<hop ttl="3" ipaddr="10.20.0.10"', '<borrado ttl="3"', 1)
        app = next(e for e in d.parsear_xml(xml) if e["ip"] == "10.20.0.10")
        self.assertEqual(app["saltos"], ["10.99.0.1", "10.0.0.2", None])


class TestCLIAutorizacion(unittest.TestCase):
    def _cli(self, *extra):
        import io, tempfile
        from contextlib import redirect_stdout
        from prototipo.herramientas import descubrir as cli
        salida = os.path.join(tempfile.mkdtemp(), "d.json")
        with mock.patch.object(d, "ejecutor_nmap", return_value=_correr_falso()), redirect_stdout(io.StringIO()) as out:
            rc = cli.main(["--rango", "10.20.0.0/24", "--externo", "198.51.100.10", "--salida", salida, *extra])
        return rc, out.getvalue(), salida

    def test_sin_autorizacion_no_escanea(self):
        rc, out, salida = self._cli("--gestion", "10.99.0.10")
        self.assertEqual(rc, 1)
        self.assertIn("autoriz", out)
        self.assertFalse(os.path.exists(salida))

    def test_gestion_invalida_no_escanea(self):
        rc, out, _ = self._cli("--gestion", "foo", "--autorizado")
        self.assertEqual(rc, 1)

    def test_escribe_en_0600_y_marca_el_origen(self):
        import json
        rc, _, salida = self._cli("--gestion", "10.99.0.10", "--autorizado")
        self.assertEqual(rc, 0)
        self.assertEqual(oct(os.stat(salida).st_mode & 0o777), "0o600")
        with open(salida, encoding="utf-8") as f:
            r = json.load(f)
        self.assertEqual((r["origen"], r["autorizado"]), ("cli", True))
