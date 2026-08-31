import unittest

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


if __name__ == "__main__":
    unittest.main()
