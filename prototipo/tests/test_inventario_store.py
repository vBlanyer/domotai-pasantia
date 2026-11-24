"""El inventario de Conectividad sigue a cada equipo del perfil por su IP (24/11: renombrar «web-packing» en el
perfil dejaba su papel huérfano y obligaba a repetir el alta)."""
import unittest

from prototipo.servicio import inventario_store as inv

PERFIL = {"activos": {"web-banking": {"ip": "10.10.0.10"}, "core-db": {"ip": "10.50.0.10"}},
          "topologia": {"fw-core": {"rol": "firewall_perimetral", "ip": "10.100.0.1"}}}
PAPEL = {"papel": "servidor", "acciones": ["BLOQUEAR_IP"], "nuevo": False}


class TestSeguirPorIp(unittest.TestCase):
    def test_apunta_la_ip_de_cada_equipo_del_perfil(self):
        nuevo, renombrados, cambiado = inv.seguir_por_ip(PERFIL, {"equipos": {"core-db": dict(PAPEL), "fw-core": dict(PAPEL)}})
        self.assertTrue(cambiado)
        self.assertEqual((nuevo["equipos"]["core-db"]["ip"], nuevo["equipos"]["fw-core"]["ip"]), ("10.50.0.10", "10.100.0.1"))
        self.assertEqual(renombrados, [])

    def test_si_la_ip_tiene_otro_nombre_en_el_perfil_el_papel_se_mueve(self):
        inventario = {"equipos": {"web-packing": {**PAPEL, "ip": "10.10.0.10"}}}
        nuevo, renombrados, cambiado = inv.seguir_por_ip(PERFIL, inventario)
        self.assertTrue(cambiado)
        self.assertEqual(renombrados, [("web-packing", "web-banking")])
        self.assertNotIn("web-packing", nuevo["equipos"])
        self.assertEqual(nuevo["equipos"]["web-banking"]["papel"], "servidor")

    def test_no_pisa_el_papel_que_ya_tiene_el_nombre_nuevo(self):
        inventario = {"equipos": {"web-packing": {**PAPEL, "ip": "10.10.0.10"},
                                  "web-banking": {**PAPEL, "papel": "puesto", "ip": "10.10.0.10"}}}
        nuevo, renombrados, _ = inv.seguir_por_ip(PERFIL, inventario)
        self.assertEqual(renombrados, [])
        self.assertEqual(nuevo["equipos"]["web-banking"]["papel"], "puesto")

    def test_sin_cambios_no_hay_nada_que_guardar(self):
        inventario = {"equipos": {"core-db": {**PAPEL, "ip": "10.50.0.10"}}}
        self.assertFalse(inv.seguir_por_ip(PERFIL, inventario)[2])

    def test_los_equipos_nuevos_de_conectividad_no_se_tocan(self):
        nuevo_eq = {"nuevo": True, "estado": "activo", "ip": "10.70.0.10", "papel": "servidor", "zona": "DMZ"}
        nuevo, renombrados, cambiado = inv.seguir_por_ip(PERFIL, {"equipos": {"pagos-qr": dict(nuevo_eq)}})
        self.assertEqual((nuevo["equipos"]["pagos-qr"], renombrados, cambiado), (nuevo_eq, [], False))


if __name__ == "__main__":
    unittest.main()
