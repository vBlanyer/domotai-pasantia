import threading
import time
import unittest
from prototipo import tablero


class TestEstadoYLector(unittest.TestCase):
    def test_registrar_pendiente_y_resolver_devuelve_la_respuesta(self):
        estado = tablero.EstadoTablero()
        lector = tablero.LectorWeb(estado)
        salida = {}
        hilo = threading.Thread(target=lambda: salida.setdefault("r", lector("Elige [1-3]: ")))
        hilo.start()
        pid = None
        for _ in range(200):                       # esperar a que el lector registre la pendiente
            p = estado.pendientes()
            if p:
                pid = p[0]["id"]; break
            time.sleep(0.005)
        self.assertIsNotNone(pid)
        self.assertTrue(estado.resolver(pid, "1"))
        hilo.join(timeout=2)
        self.assertEqual(salida["r"], "1")
        self.assertEqual(estado.pendientes(), [])  # se quita al resolverse

    def test_clasifica_escalada_y_menu_como_lector(self):
        estado = tablero.EstadoTablero()
        estado.registrar_pendiente(*("escalada", "¿aprobar? [s/N] "))
        # el tipo lo pone LectorWeb; aqui comprobamos la regla directamente
        self.assertEqual(tablero.LectorWeb(estado)._tipo("¿aprobar? [s/N] "), "escalada")
        self.assertEqual(tablero.LectorWeb(estado)._tipo("Elige [1-3]: "), "menu")

    def test_resolver_id_desconocido_es_falso(self):
        self.assertFalse(tablero.EstadoTablero().resolver("999", "1"))

    def test_timeout_devuelve_respuesta_segura_vacia(self):
        estado = tablero.EstadoTablero()
        r = tablero.LectorWeb(estado, timeout=0.05)("Elige [1-3]: ")
        self.assertEqual(r, "")

    def test_anotar_linea_reinicia_en_cada_incidente(self):
        estado = tablero.EstadoTablero()
        estado.anotar_linea("⚠ Incidente A"); estado.anotar_linea("  detalle")
        pid, _ = estado.registrar_pendiente("menu", "x")
        self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ Incidente A", "  detalle"])
        estado.anotar_linea("⚠ Incidente B")   # nueva marca -> reinicia
        pid2, _ = estado.registrar_pendiente("menu", "y")
        self.assertEqual([p["lineas"] for p in estado.pendientes() if p["id"] == pid2][0],
                         ["⚠ Incidente B"])

    def test_escribir_web_imprime_y_acumula(self):
        estado = tablero.EstadoTablero()
        vistas = []
        esc = tablero.escribir_web(estado, escribir=vistas.append)
        esc("⚠ Incidente"); esc("linea 2")
        self.assertEqual(vistas, ["⚠ Incidente", "linea 2"])
        pid, _ = estado.registrar_pendiente("menu", "x")
        self.assertEqual(estado.pendientes()[0]["lineas"], ["⚠ Incidente", "linea 2"])


if __name__ == "__main__":
    unittest.main()
