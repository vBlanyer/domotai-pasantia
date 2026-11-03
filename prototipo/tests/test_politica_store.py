"""Tests del almacén de la copia operativa y su auditoría."""
import copy
import json
import os
import tempfile
import unittest
from datetime import datetime

from prototipo.servicio import politica_store


class TestPoliticaStore(unittest.TestCase):
    def test_aplicar_cambio_add_y_borra(self):
        original = {}
        ov = politica_store.aplicar_cambio(original, "zona", "Core", "humano_siempre")
        self.assertEqual(ov["politicas_por_zona"]["Core"]["automatizacion"], "humano_siempre")
        self.assertEqual(original, {})
        snapshot = copy.deepcopy(ov)
        ov2 = politica_store.aplicar_cambio(ov, "zona", "Core", None)
        self.assertNotIn("Core", ov2.get("politicas_por_zona", {}))
        self.assertEqual(ov, snapshot)

    def test_dimensiones(self):
        ov = politica_store.aplicar_cambio({}, "familia", "fuerza_bruta", "supervisada")
        self.assertIn("fuerza_bruta", ov["automatizacion_por_familia"])
        ov = politica_store.aplicar_cambio(ov, "activo", "10.0.0.1", "humano_siempre")
        self.assertIn("10.0.0.1", ov["overrides_por_activo"])

    def test_guardar_y_cargar_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "overlay.yml")
            self.assertEqual(politica_store.cargar_overlay(ruta), {})
            ov = politica_store.aplicar_cambio({}, "zona", "Core", "humano_siempre")
            politica_store.guardar_overlay(ruta, ov)
            self.assertEqual(politica_store.cargar_overlay(ruta), ov)
            self.assertEqual(os.listdir(d), ["overlay.yml"])

    def test_auditoria_append_parseable(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "audit.jsonl")
            politica_store.registrar_auditoria(ruta, "ana", "zona", "Core", None, "humano_siempre")
            politica_store.registrar_auditoria(ruta, "ana", "zona", "Core", "humano_siempre", None)
            with open(ruta, encoding="utf-8") as f:
                lineas = f.read().splitlines()
            self.assertEqual(len(lineas), 2)
            for l in lineas:
                r = json.loads(l)
                self.assertEqual(set(r), {"operador", "dimension", "clave", "antes", "despues", "timestamp"})
                datetime.fromisoformat(r["timestamp"])


if __name__ == "__main__":
    unittest.main()
