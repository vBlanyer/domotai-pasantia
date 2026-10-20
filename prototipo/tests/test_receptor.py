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

    def test_lista_vacia_bloquea_a_todos_fail_closed(self):
        # I-1: permitir=[] (lista dada pero vacía) NO es "sin filtro" -> rechaza a cualquiera.
        gen, puerto = self._gen(permitir=[])
        _cliente_envia(puerto, b'{"x":1}\n')
        vistos = [next(gen) for _ in range(8)]
        self.assertTrue(all(v is None for v in vistos))

    def test_cola_acotada_no_pierde_lineas_por_backpressure(self):
        # I-2: con la cola muy pequeña, un consumidor lento no pierde líneas (backpressure TCP).
        gen, puerto = self._gen(permitir={"127.0.0.1"}, cola_max=1)
        _cliente_envia(puerto, b'{"a":1}\n{"b":2}\n{"c":3}\n', espera=0.6)
        self.assertEqual(_recoge(gen, 3), ['{"a":1}', '{"b":2}', '{"c":3}'])


class TestAgotamientoDeSlots(unittest.TestCase):
    """M1 de la auditoría 20/10: una conexión ociosa no retiene su slot para siempre, una IP no
    monopoliza todos los slots, y un rechazo deja rastro (no se cierra en silencio)."""

    def _gen(self, **kw):
        srv = receptor._crear_servidor("127.0.0.1", 0)
        puerto = srv.getsockname()[1]
        gen = receptor.escuchar("127.0.0.1", puerto, intervalo=0.05, _socket_servidor=srv, **kw)
        self.addCleanup(gen.close)
        return gen, puerto

    def test_conexion_ociosa_se_cierra_y_libera_el_slot(self):
        gen, puerto = self._gen(permitir={"127.0.0.1"}, max_conexiones=1, inactividad_s=0.2)
        ocioso = socket.create_connection(("127.0.0.1", puerto), timeout=2)   # no envía nada
        self.addCleanup(ocioso.close)
        for _ in range(30):                               # deja pasar el plazo de inactividad
            next(gen)
        _cliente_envia(puerto, b'{"ok":1}\n')             # el slot debe estar libre otra vez
        self.assertEqual(_recoge(gen, 1), ['{"ok":1}'])

    def test_una_ip_no_monopoliza_los_slots(self):
        gen, puerto = self._gen(permitir={"127.0.0.1"}, max_por_ip=1, inactividad_s=30)
        primero = socket.create_connection(("127.0.0.1", puerto), timeout=2)  # ocupa el cupo de la IP
        primero.sendall(b'{"p":0}\n')
        self.assertEqual(_recoge(gen, 1), ['{"p":0}'])    # su línea llegó => el aceptador ya lo contó
        _cliente_envia(puerto, b'{"x":1}\n')              # 2ª conexión de la misma IP: rechazada
        vistos = [next(gen) for _ in range(8)]
        self.assertNotIn('{"x":1}', vistos)
        primero.close()                                   # al cerrar, el cupo se libera
        _cliente_envia(puerto, b'{"ok":2}\n')
        self.assertEqual(_recoge(gen, 1), ['{"ok":2}'])

    def test_abierto_fuera_de_loopback_se_niega_tambien_aqui(self):
        # Defensa en profundidad de M2: el fail-closed no vive solo en la CLI (stream.validar_escucha);
        # el propio mecanismo se niega a escuchar abierto fuera de loopback.
        gen = receptor.escuchar("0.0.0.0", 0)             # sin permitir
        self.addCleanup(gen.close)
        with self.assertRaises(ValueError):
            next(gen)

    def test_fallo_al_lanzar_el_hilo_no_filtra_el_slot(self):
        from unittest import mock
        gen, puerto = self._gen(permitir={"127.0.0.1"}, max_conexiones=1, inactividad_s=30)
        next(gen)                                         # arranca el aceptador (hilo ya creado)
        reventar = mock.Mock(side_effect=RuntimeError("can't start new thread"))
        with mock.patch.object(receptor.threading, "Thread",
                               return_value=mock.Mock(start=reventar)):
            # conexión en línea (sin hilo auxiliar: Thread está parcheado globalmente)
            c = socket.create_connection(("127.0.0.1", puerto), timeout=2)
            c.sendall(b'{"x":1}\n')                       # su hilo no arranca: el slot debe liberarse
            for _ in range(20):
                next(gen)
                if reventar.called:
                    break
            c.close()
        _cliente_envia(puerto, b'{"ok":3}\n')             # con el único slot libre, esta sí entra
        self.assertEqual(_recoge(gen, 1), ['{"ok":3}'])

    def test_el_rechazo_deja_rastro(self):
        avisos = []
        gen, puerto = self._gen(permitir={"10.0.0.1"}, avisar=avisos.append)
        _cliente_envia(puerto, b'{"x":1}\n')
        for _ in range(8):
            next(gen)
        self.assertTrue(any("127.0.0.1" in a and "autoriza" in a for a in avisos), avisos)


class TestContextoTLS(unittest.TestCase):
    def setUp(self):
        import shutil, subprocess, tempfile
        if not shutil.which("openssl"):
            self.skipTest("sin openssl para generar el certificado de prueba")
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        self.cert, self.clave = f"{d}/c.pem", f"{d}/k.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt",
                        "ec_paramgen_curve:prime256v1", "-keyout", self.clave, "-out", self.cert,
                        "-days", "2", "-nodes", "-subj", "/CN=test"],
                       check=True, capture_output=True)

    def test_sin_ca_no_exige_certificado_de_cliente(self):
        import ssl
        ctx = receptor.contexto_tls(self.cert, self.clave)
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)

    def test_con_ca_exige_certificado_de_cliente(self):
        # M2: mTLS opcional — con una CA, el receptor autentica al EMISOR, no solo se cifra.
        import ssl
        ctx = receptor.contexto_tls(self.cert, self.clave, ca=self.cert)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)


if __name__ == "__main__":
    unittest.main()
