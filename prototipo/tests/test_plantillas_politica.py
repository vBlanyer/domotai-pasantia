"""Tarea 6 del plan de politica.yml: la plantilla del perfil queda solo con lo técnico y las reglas pasan
a deploy/politica.ejemplo.yml. Juntas deben decir exactamente lo mismo que el perfil de ejemplo anterior."""
import os, unittest, yaml

from prototipo.accion import catalogo as catm
from prototipo.motor import perfil as perfilm
from prototipo.motor import politica_empresa as pe

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAT = catm.cargar_catalogo(os.path.join(RAIZ, "prototipo", "catalogo.yml"))


def _yaml(nombre):
    with open(os.path.join(RAIZ, "deploy", nombre), encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestPlantillas(unittest.TestCase):
    def setUp(self):
        self.perfil, self.politica = _yaml("perfil.ejemplo.yml"), _yaml("politica.ejemplo.yml")

    def test_el_perfil_de_ejemplo_no_lleva_reglas_de_politica(self):
        pol, _ = pe.extraer_politica(self.perfil)
        self.assertEqual(pol, {})
        self.assertEqual(perfilm.validar(self.perfil), [])

    def test_la_politica_de_ejemplo_es_valida_con_ese_perfil(self):
        self.assertEqual(pe.validar_politica(self.politica, self.perfil, CAT), [])
        self.assertIn("pendiente", pe.cabecera(self.politica)["aprobada_por"])

    def test_juntas_equivalen_al_perfil_de_ejemplo_anterior(self):
        f = pe.fusionar_perfil_y_politica(self.perfil, self.politica)
        self.assertEqual(f["origenes_legitimos"], ["10.99.0.10"])
        self.assertEqual(f["terceros_confiables"], [])
        self.assertEqual(f["rafaga"], {"umbral": 9, "ventana_s": 60})
        self.assertEqual(f["continuidad"], {
            "impacto_ninguno": "humano_siempre", "impacto_localizado": "humano_siempre",
            "impacto_alcanza_servicio": "humano_siempre", "reversibilidad_obligatoria": True,
            "no_cortar_gestion": True, "umbral_confianza": 0.9, "revisar_no_soportada_nivel": 10,
            "actores": {"activo_interno": "humano_siempre", "dispositivo_red": "humano_siempre"}})
        self.assertEqual(f["excepciones"], [{"activo": "db01", "servicio": 5432, "regla": "nunca_automatica"}])


if __name__ == "__main__":
    unittest.main()
