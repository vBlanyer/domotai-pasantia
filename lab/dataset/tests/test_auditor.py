import unittest

from lab.scripts import auditor
from lab.scripts.auditor import parsear_puertos, resultado_nodo

NMAP_SALIDA = """
Starting Nmap 7.99
Nmap scan report for 192.168.1.30
Host is up.
PORT     STATE SERVICE
22/tcp   open  ssh
23/tcp   open  telnet
Nmap done: 1 IP address (1 host up) scanned in 1.23 seconds
"""


class TestParsearPuertos(unittest.TestCase):
    def test_extrae_puerto_servicio_estado(self):
        puertos = parsear_puertos(NMAP_SALIDA)
        self.assertIn({"puerto": 22, "servicio": "ssh", "estado": "open"}, puertos)
        self.assertIn({"puerto": 23, "servicio": "telnet", "estado": "open"}, puertos)

    def test_sin_puertos_abiertos_da_lista_vacia(self):
        self.assertEqual(parsear_puertos("Host is up. All 100 scanned ports are closed"), [])


class TestResultadoNodo(unittest.TestCase):
    def test_escaneo_exitoso_devuelve_puertos(self):
        # I2: nodo escaneado con éxito, sin servicios abiertos -> [] real,
        # no una lista vacía disfrazando un fallo.
        r = resultado_nodo(0, "Host is up. All 100 scanned ports are closed")
        self.assertEqual(r, [])

    def test_escaneo_fallido_devuelve_none_no_lista_vacia(self):
        # I2: returncode != 0 (docker exec o nmap fallaron) -> None, para que
        # postura_de lo trate como desconocido/gris, nunca como "no expuesto".
        r = resultado_nodo(1, "")
        self.assertIsNone(r)


class TestArgumentosNmap(unittest.TestCase):
    def test_por_defecto_top_100(self):
        self.assertEqual(auditor.argumentos_nmap("10.0.0.1", None),
                         ["nmap", "-Pn", "--top-ports", "100", "10.0.0.1"])

    def test_lista_explicita_de_puertos(self):
        # R2: el 1521 no esta en el top-100; el banco pasa la lista.
        self.assertEqual(auditor.argumentos_nmap("10.50.0.10", "22,1521"),
                         ["nmap", "-Pn", "-p", "22,1521", "10.50.0.10"])


if __name__ == "__main__":
    unittest.main()
