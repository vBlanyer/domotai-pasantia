import json, os, tempfile, time, unittest
from prototipo.herramientas import estado_instalacion as ei

PERFIL = """activos:
  web01: { ip: 192.0.2.10 }
  app01: { ip: 10.20.0.10 }
topologia:
  web01: { rol: host_victima, ip: 192.0.2.10, gateway: fw }
  app01: { rol: host_victima, ip: 10.20.0.10, gateway: fw }
  fw: { rol: firewall_perimetral, ip: 10.0.0.1 }
"""


class Sistema:
    def __init__(self, activo=True, habilitado=True):
        self.activo, self.habilitado = activo, habilitado

    def __call__(self, args, **kw):
        rc = 0 if ((args[1] == "is-active" and self.activo) or (args[1] == "is-enabled" and self.habilitado)) else 3
        return type("R", (), {"returncode": rc, "stdout": "", "stderr": ""})()


class TestEstado(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        j = lambda *p: os.path.join(self.d, *p)
        with open(j("perfil.yml"), "w") as f:
            f.write(PERFIL)
        with open(j("postura.json"), "w") as f:
            json.dump({"nodos": {"web01": [{"puerto": 22, "servicio": "ssh", "estado": "open"}]}}, f)
        with open(j("alerts.json"), "w") as f:
            f.write("")
        for nombre in ("dbip-country-lite.csv.gz", "dbip-asn-lite.csv.gz"):
            with open(j(nombre), "w") as f:
                f.write("x")
        os.makedirs(j("conector"))
        with open(j("conector", "clave"), "w") as f:
            f.write("privada")
        with open(j("conectividad-pruebas.json"), "w") as f:
            json.dump({"192.0.2.10": {"estado": "verificada", "ok": True},
                       "10.20.0.10": {"estado": "sin_aprovisionar", "ok": False}}, f)
        self.env = {"TRIAJE_PERFIL": j("perfil.yml"), "TRIAJE_HALLAZGOS": j("postura.json"),
                    "TRIAJE_ALERTS": j("alerts.json"), "TRIAJE_SALIDA": j("trazas-cliente.jsonl"),
                    "TRIAJE_SSH_MODO": "directo", "TRIAJE_SSH_CLAVE": j("conector", "clave"),
                    "TRIAJE_TRAZA_CLAVE": "ab" * 32, "TRIAJE_CONSOLA_OPERADORES": '{"t":"ana"}',
                    "TRIAJE_GEOIP": j("dbip-country-lite.csv.gz"), "TRIAJE_ASN": j("dbip-asn-lite.csv.gz")}
        self.salud = lambda puerto: {"ok": True, "ingesta_silencio_s": 12.0, "alertas": 142}

    def _por_tema(self, **kw):
        args = dict(env=self.env, ejecutar=Sistema(), salud=self.salud)
        args.update(kw)
        return {c["tema"]: c for c in ei.comprobar(**args)}

    def test_todo_en_orden_salvo_un_equipo_sin_aprovisionar(self):
        c = self._por_tema()
        self.assertEqual(c["servicio"]["nivel"], "ok")
        self.assertIn("142 alertas", c["salud"]["texto"])
        self.assertEqual(c["equipos"]["nivel"], "aviso")
        self.assertIn("1 de 3", c["equipos"]["texto"])
        self.assertEqual(c["analistas"]["nivel"], "ok")
        self.assertEqual(c["postura"]["nivel"], "ok")

    def test_sin_analistas_la_consola_esta_abierta_y_es_un_fallo(self):
        del self.env["TRIAJE_CONSOLA_OPERADORES"]
        c = self._por_tema()["analistas"]
        self.assertEqual(c["nivel"], "fallo")
        self.assertIn("mdr analista alta", c["remedio"])

    def test_servicio_parado_y_salud_sin_respuesta(self):
        c = self._por_tema(ejecutar=Sistema(activo=False), salud=lambda p: None)
        self.assertEqual(c["servicio"]["nivel"], "fallo")
        self.assertEqual(c["salud"]["nivel"], "fallo")

    def test_postura_vacia_avisa_de_que_nada_se_automatiza(self):
        with open(self.env["TRIAJE_HALLAZGOS"], "w") as f:
            json.dump({"nodos": {}}, f)
        c = self._por_tema()["postura"]
        self.assertEqual(c["nivel"], "aviso")
        self.assertIn("mdr escanear", c["remedio"])

    def test_base_de_paises_ausente_o_vieja(self):
        os.unlink(self.env["TRIAJE_GEOIP"])
        self.assertEqual(self._por_tema()["países"]["nivel"], "aviso")
        with open(self.env["TRIAJE_GEOIP"], "w") as f:
            f.write("x")
        viejo = time.time() - 60 * 86400
        os.utime(self.env["TRIAJE_GEOIP"], (viejo, viejo))
        self.assertIn("60 días", self._por_tema()["países"]["texto"])

    def test_sin_clave_del_conector_avisa_de_conectividad(self):
        os.unlink(self.env["TRIAJE_SSH_CLAVE"])
        c = self._por_tema()["conector"]
        self.assertEqual(c["nivel"], "aviso")
        self.assertIn("Conectividad", c["remedio"])

    def test_perfil_ausente_es_un_fallo(self):
        os.unlink(self.env["TRIAJE_PERFIL"])
        self.assertEqual(self._por_tema()["perfil"]["nivel"], "fallo")

    def test_informe_y_codigo_de_salida(self):
        lineas, rc = ei.informe(ei.comprobar(env=self.env, ejecutar=Sistema(), salud=self.salud))
        self.assertEqual(rc, 0)                       # avisos, ningún fallo
        self.assertTrue(any("!" in l and "equipos" in l for l in lineas))
        del self.env["TRIAJE_CONSOLA_OPERADORES"]
        _, rc = ei.informe(ei.comprobar(env=self.env, ejecutar=Sistema(), salud=self.salud))
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
