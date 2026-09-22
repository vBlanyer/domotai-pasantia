import json
import subprocess
import unittest
from lab.banco import panel

TODO_OK = {n: "ok" for n in ("core-db", "hsm", "middleware", "web-banking", "api-movil", "swift-alliance", "atm")}


def _muestra(t, **caidos):
    estados = dict(TODO_OK)
    estados.update({n.replace("_", "-"): "caido" for n in caidos})
    return {"t": t, "estados": estados}


class TestLeer(unittest.TestCase):
    def test_lee_la_ultima_muestra_del_monitor(self):
        linea = json.dumps(_muestra("2026-09-22T15:00:00Z"))
        def ejecutar(args, **kw):
            self.assertEqual(args[:3], ["docker", "exec", "clab-banco-mdr-siem"])
            return subprocess.CompletedProcess(args, 0, linea + "\n", "")
        self.assertEqual(panel.leer_ultima(ejecutar)["t"], "2026-09-22T15:00:00Z")

    def test_sin_datos_devuelve_none(self):
        def ejecutar(args, **kw):
            return subprocess.CompletedProcess(args, 1, "", "No such container")
        self.assertIsNone(panel.leer_ultima(ejecutar))

    def test_linea_corrupta_devuelve_none(self):
        def ejecutar(args, **kw):
            return subprocess.CompletedProcess(args, 0, "{no es json", "")
        self.assertIsNone(panel.leer_ultima(ejecutar))


class TestHistorial(unittest.TestCase):
    def test_registra_solo_los_cambios(self):
        h = panel.historial_vacio()
        panel.actualizar(h, _muestra("2026-09-22T15:00:00Z"))
        panel.actualizar(h, _muestra("2026-09-22T15:00:02Z"))
        self.assertEqual(h["eventos"], [])                       # la primera muestra no es un cambio
        panel.actualizar(h, _muestra("2026-09-22T15:00:04Z", core_db=1, middleware=1))
        self.assertEqual(h["eventos"], [("2026-09-22T15:00:04Z", "core-db", "caido"),
                                        ("2026-09-22T15:00:04Z", "middleware", "caido")])
        self.assertEqual(h["desde"]["core-db"], "2026-09-22T15:00:04Z")
        self.assertEqual(h["desde"]["hsm"], "2026-09-22T15:00:00Z")

    def test_la_vuelta_tambien_es_un_evento(self):
        h = panel.historial_vacio()
        panel.actualizar(h, _muestra("2026-09-22T15:00:00Z", atm=1))
        panel.actualizar(h, _muestra("2026-09-22T15:00:10Z"))
        self.assertEqual(h["eventos"], [("2026-09-22T15:00:10Z", "atm", "ok")])


class TestRenderizar(unittest.TestCase):
    def setUp(self):
        self.h = panel.historial_vacio()
        panel.actualizar(self.h, _muestra("2026-09-22T15:00:00Z"))
        self.m = _muestra("2026-09-22T15:00:30Z", core_db=1, middleware=1, web_banking=1, api_movil=1, atm=1)
        panel.actualizar(self.h, self.m)

    def test_sin_color_muestra_estado_dependencias_y_resumen(self):
        txt = panel.renderizar(self.m, self.h, color=False)
        fila_atm = next(l for l in txt.splitlines() if l.strip().startswith("atm"))
        self.assertIn("CAÍDO", fila_atm)
        self.assertIn("middleware (no declarada)", fila_atm)
        fila_hsm = next(l for l in txt.splitlines() if l.strip().startswith("hsm"))
        self.assertIn("OK", fila_hsm)
        self.assertIn("5 de 7 servicios caídos", txt)
        self.assertIn("15:00:30  core-db", txt)
        self.assertNotIn("\033[", txt)

    def test_orden_de_dependencia(self):
        txt = panel.renderizar(self.m, self.h, color=False)
        filas = [l.split()[0] for l in txt.splitlines() if l.strip() and l.split()[0] in TODO_OK]
        self.assertEqual(filas, ["core-db", "hsm", "middleware", "web-banking", "api-movil", "swift-alliance", "atm"])

    def test_con_color_usa_verde_y_rojo(self):
        txt = panel.renderizar(self.m, self.h, color=True)
        self.assertIn(panel.ROJO, txt)
        self.assertIn(panel.VERDE, txt)

    def test_sin_muestra_lo_dice(self):
        self.assertIn("sin datos del monitor", panel.renderizar(None, panel.historial_vacio(), color=False))


if __name__ == "__main__":
    unittest.main()
