import unittest

from prototipo import validar_reglas


def _cruda(groups, rid="1"):
    return {"id": "x", "rule": {"id": rid, "level": 5, "groups": groups},
            "predecoder": {"hostname": "h"}, "data": {"srcip": "1.1.1.1"},
            "timestamp": "2026-01-01T00:00:00Z"}


class TestCobertura(unittest.TestCase):
    """#2: el validador dice qué fracción de una muestra de alertas del cliente cubre el motor."""
    def test_cuenta_por_familia_y_marca_las_sin_cobertura(self):
        crudas = [
            _cruda(["sshd", "authentication_failed"]),   # acceso_credenciales (con playbook)
            _cruda(["recon"]),                           # reconocimiento (con playbook)
            _cruda(["cosa_rara"], rid="99999"),          # otra -> SIN cobertura
            _cruda(["triaje"]),                          # telemetría propia -> descartada
        ]
        r = validar_reglas.cobertura(crudas)
        self.assertEqual(r["total"], 4)
        self.assertEqual(r["propias"], 1)
        self.assertEqual(r["por_familia"]["acceso_credenciales"], 1)
        self.assertEqual(r["por_familia"]["reconocimiento"], 1)
        self.assertEqual(r["cubiertas"], 2)
        self.assertEqual(len(r["sin_cobertura"]), 1)
        self.assertEqual(r["sin_cobertura"][0]["regla_id"], "99999")
        self.assertIn("acceso_credenciales", r["soportadas"])

    def test_muestra_vacia(self):
        r = validar_reglas.cobertura([])
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["cubiertas"], 0)
        self.assertEqual(r["sin_cobertura"], [])


if __name__ == "__main__":
    unittest.main()
