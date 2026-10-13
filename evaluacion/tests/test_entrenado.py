import datetime
import unittest

from evaluacion import entrenado


def _alerta(ip, seg, base=datetime.datetime(2026, 10, 13, 12, 0, 0), regla="5760", nivel=5):
    return {"origen_ip": ip, "regla_id": regla, "nivel_wazuh": nivel,
            "timestamp": (base + datetime.timedelta(seconds=seg)).strftime("%Y-%m-%dT%H:%M:%S")}


class TestRasgoVentanaLarga(unittest.TestCase):
    # Experimento A (ataque lento): el árbol no tenía ninguna ventana > 120 s, así que no podía VER
    # un ataque repartido en minutos. n_origen_600s cuenta los fallos del mismo origen en ±600 s.
    def test_ventana_larga_ve_una_rafaga_lenta_que_la_de_60s_no_ve(self):
        # 12 intentos, uno cada 20 s (span 220 s): ninguna ventana de ±60 s llega al umbral 9,
        # pero la de ±600 s los cuenta todos -> es lo que permite separar un ataque lento.
        filas = [_alerta("192.168.1.1", 20 * i) for i in range(12)]
        entrenado.rasgos_rafaga(filas)
        medio = filas[6]
        self.assertLess(medio["n_origen_60s"], 9)       # la ráfaga a 60 s NO lo delata
        self.assertEqual(medio["n_origen_600s"], 12)    # la ventana larga SÍ

    def test_ventana_larga_cuenta_pocos_fallos_aislados(self):
        # El contraste: un admin que teclea mal 2 veces en 90 s -> ventana larga baja (no es ataque).
        filas = [_alerta("192.168.1.1", 0), _alerta("192.168.1.1", 90)]
        entrenado.rasgos_rafaga(filas)
        self.assertEqual(filas[0]["n_origen_600s"], 2)

    def test_ventana_larga_en_rasgos(self):
        self.assertIn("n_origen_600s", entrenado.RASGOS)

    def test_sin_timestamp_la_ventana_larga_es_1(self):
        filas = [{"origen_ip": "192.168.1.1", "regla_id": "5760", "nivel_wazuh": 5, "timestamp": "sin-fecha"}]
        entrenado.rasgos_rafaga(filas)
        self.assertEqual(filas[0]["n_origen_600s"], 1)


if __name__ == "__main__":
    unittest.main()
