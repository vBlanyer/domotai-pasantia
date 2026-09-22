import json
import unittest
import urllib.error
from lab.banco import monitor


class _Resp:
    def __init__(self, status): self.status = status
    def __enter__(self): return self
    def __exit__(self, *a): return False


class TestMonitor(unittest.TestCase):
    def test_parsear_servicios(self):
        self.assertEqual(monitor.parsear_servicios(["core-db=10.50.0.10:1521", "hsm=10.60.0.10:9000"]),
                         {"core-db": "10.50.0.10:1521", "hsm": "10.60.0.10:9000"})

    def test_sondear_distingue_sano_503_y_sin_respuesta(self):
        def abrir(url, timeout):
            if "10.0.0.1" in url:
                return _Resp(200)
            if "10.0.0.2" in url:
                raise urllib.error.HTTPError(url, 503, "degradado", None, None)
            raise OSError("sin ruta")
        estados = monitor.sondear({"a": "10.0.0.1:1", "b": "10.0.0.2:1", "c": "10.0.0.3:1"}, abrir=abrir)
        self.assertEqual(estados, {"a": "ok", "b": "caido", "c": "caido"})

    def test_sondear_cierra_httperror(self):
        """Verifica que HTTPError se cierra cuando urlopen lo lanza."""
        import io
        cerrados = []
        def abrir(url, timeout):
            fp = io.BytesIO(b"")
            e = urllib.error.HTTPError(url, 503, "caido", {}, fp)
            # Wrap close to track calls
            original_close = e.close
            def tracked_close():
                cerrados.append(True)
                original_close()
            e.close = tracked_close
            raise e
        monitor.sondear({"x": "10.0.0.1:1"}, abrir=abrir)
        self.assertEqual(len(cerrados), 1)

    def test_cambios(self):
        self.assertEqual(monitor.cambios({"a": "ok", "b": "ok", "c": "caido"}, {"a": "caido", "b": "ok", "c": "ok"}),
                         {"caen": ["a"], "vuelven": ["c"]})

    def test_registro_es_json_con_instante_utc(self):
        d = json.loads(monitor.registro({"a": "ok"}, 0))
        self.assertEqual(d, {"t": "1970-01-01T00:00:00Z", "estados": {"a": "ok"}})


if __name__ == "__main__":
    unittest.main()
