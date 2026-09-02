import os, json, tempfile, unittest
from evaluacion import cargar

FILAS = [
    {"id_alerta":"1","particion":"evaluacion","etiqueta":"VP","nivel_wazuh":10,"familia":"acceso_credenciales"},
    {"id_alerta":"2","particion":"entrenamiento","etiqueta":"FP","nivel_wazuh":5,"familia":"acceso_credenciales"},
    {"id_alerta":"3","particion":"evaluacion","etiqueta":"no_soportada","nivel_wazuh":3,"familia":"plataforma"},
]

class TestCargar(unittest.TestCase):
    def setUp(self):
        fd, self.ruta = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for r in FILAS:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def tearDown(self):
        os.remove(self.ruta)

    def test_filtra_por_particion(self):
        filas = cargar.cargar(self.ruta, "evaluacion")
        self.assertEqual({f["id_alerta"] for f in filas}, {"1", "3"})

    def test_particion_none_devuelve_todas(self):
        self.assertEqual(len(cargar.cargar(self.ruta, None)), 3)

    def test_conserva_ground_truth(self):
        f = cargar.cargar(self.ruta, "evaluacion")[0]
        self.assertIn("etiqueta", f)
        self.assertIn("nivel_wazuh", f)
