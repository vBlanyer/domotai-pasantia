import socket
import threading
import time
import unittest

from prototipo import receptor


def _cliente_envia(puerto, datos, espera=0.3):
    def _():
        try:
            c = socket.create_connection(("127.0.0.1", puerto), timeout=2)
            c.sendall(datos); time.sleep(espera); c.close()
        except OSError:
            pass
    threading.Thread(target=_, daemon=True).start()


def _recoge(gen, n_lineas, max_iter=200):
    lineas = []
    for _ in range(max_iter):
        v = next(gen)
        if v is not None:
            lineas.append(v)
        if len(lineas) >= n_lineas:
            break
    return lineas


class TestReceptor(unittest.TestCase):
    def _gen(self, **kw):
        srv = receptor._crear_servidor("127.0.0.1", 0)
        puerto = srv.getsockname()[1]
        gen = receptor.escuchar("127.0.0.1", puerto, intervalo=0.05, _socket_servidor=srv, **kw)
        self.addCleanup(gen.close)
        return gen, puerto

    def test_recibe_lineas_de_un_cliente_permitido(self):
        gen, puerto = self._gen(permitir={"127.0.0.1"})
        _cliente_envia(puerto, b'{"a":1}\n{"b":2}\n')
        self.assertEqual(_recoge(gen, 2), ['{"a":1}', '{"b":2}'])

    def test_en_reposo_rinde_none(self):
        gen, _ = self._gen(permitir={"127.0.0.1"})
        self.assertIsNone(next(gen))                      # nadie conectó: tick de reposo

    def test_rechaza_un_peer_fuera_de_la_lista(self):
        gen, puerto = self._gen(permitir={"10.0.0.1"})    # 127.0.0.1 NO permitido
        _cliente_envia(puerto, b'{"x":1}\n')
        vistos = [next(gen) for _ in range(8)]
        self.assertNotIn('{"x":1}', vistos)
        self.assertTrue(all(v is None for v in vistos))

    def test_sin_lista_acepta_a_cualquiera(self):
        gen, puerto = self._gen()                         # permitir=None -> sin filtro
        _cliente_envia(puerto, b'{"a":1}\n')
        self.assertEqual(_recoge(gen, 1), ['{"a":1}'])

    def test_linea_sobredimensionada_se_descarta_y_la_buena_llega(self):
        gen, puerto = self._gen(permitir={"127.0.0.1"}, max_linea=10)
        _cliente_envia(puerto, b"x" * 50 + b"basura\n" + b'{"ok":1}\n')
        self.assertEqual(_recoge(gen, 1), ['{"ok":1}'])   # la gigante se ignora; la buena llega


if __name__ == "__main__":
    unittest.main()
