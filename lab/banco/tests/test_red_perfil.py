"""La sección `red` de bancario.yml describe la red del laboratorio: cada enlace de Containerlab
tiene que aparecer como enlace hijo→padre del perfil (en un sentido u otro)."""
import os, unittest, yaml
from prototipo import red, perfil as perfilm

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "..")


class TestRedDelBancoCoincideConElLaboratorio(unittest.TestCase):
    def test_cada_enlace_del_laboratorio_esta_en_el_perfil(self):
        with open(os.path.join(RAIZ, "lab", "topologias", "banco.clab.yml"), encoding="utf-8") as f:
            clab = yaml.safe_load(f)
        r = red.red_de(perfilm.cargar(os.path.join(RAIZ, "prototipo", "perfiles", "bancario.yml")))
        self.assertEqual(r["avisos"], [])
        for enlace in clab["topology"]["links"]:
            a, b = (e.split(":")[0] for e in enlace["endpoints"])
            self.assertTrue(r["enlaces"].get(a) == b or r["enlaces"].get(b) == a, f"{a} <-> {b}")

    def test_todo_equipo_del_banco_tiene_zona_o_es_troncal(self):
        r = red.red_de(perfilm.cargar(os.path.join(RAIZ, "prototipo", "perfiles", "bancario.yml")))
        self.assertNotIn(red.SIN_UBICAR, [z for z, _ in r["zonas"]])
        self.assertEqual([z for z, _ in r["zonas"]], ["DMZ", "Core", "Sucursal", "SOC"])
