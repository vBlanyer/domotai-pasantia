"""La sección `red` de bancario.yml describe la red del laboratorio: cada enlace de Containerlab
tiene que aparecer como enlace hijo→padre del perfil (en un sentido u otro)."""
import os, unittest, yaml
from prototipo import red, perfil as perfilm

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "..")


class TestRedDelBancoCoincideConElLaboratorio(unittest.TestCase):
    def test_los_enlaces_del_perfil_son_los_del_laboratorio(self):
        """El perfil describe exactamente los enlaces del lab (sin extras, sin inversiones radicales)."""
        with open(os.path.join(RAIZ, "lab", "topologias", "banco.clab.yml"), encoding="utf-8") as f:
            clab = yaml.safe_load(f)
        r = red.red_de(perfilm.cargar(os.path.join(RAIZ, "prototipo", "perfiles", "bancario.yml")))
        self.assertEqual(r["avisos"], [])

        # Verificar que cada enlace del lab está en el perfil (en un sentido u otro)
        for enlace in clab["topology"]["links"]:
            a, b = (e.split(":")[0] for e in enlace["endpoints"])
            self.assertTrue(r["enlaces"].get(a) == b or r["enlaces"].get(b) == a, f"{a} <-> {b}")

        # Verificar que los enlaces del perfil son exactamente los del lab (como pares no ordenados)
        pares = {frozenset(e.split(":")[0] for e in l["endpoints"]) for l in clab["topology"]["links"]}
        self.assertEqual({frozenset(p) for p in r["enlaces"].items()}, pares)

        # Verificar que solo 'internet' es raíz (value sin corresponding key)
        self.assertEqual(set(r["enlaces"].values()) - set(r["enlaces"]), {"internet"})

    def test_todo_equipo_del_banco_tiene_zona_o_es_troncal(self):
        """Todos los equipos están en una zona o son troncales (fw-edge, fw-core, internet)."""
        r = red.red_de(perfilm.cargar(os.path.join(RAIZ, "prototipo", "perfiles", "bancario.yml")))

        # Verificar que no hay zona por defecto "Sin ubicar"
        self.assertNotIn(red.SIN_UBICAR, [z for z, _ in r["zonas"]])

        # Verificar estructura exacta de zonas
        self.assertEqual(r["zonas"],
                        [["DMZ", ["web-banking", "api-movil", "swift-alliance"]],
                         ["Core", ["middleware", "core-db", "hsm"]],
                         ["Sucursal", ["taquilla", "atm"]],
                         ["SOC", ["sw-soc", "mdr-siem", "auditor"]]])

        # Verificar que exactamente los troncales no tienen zona asignada
        self.assertEqual({n for n, v in r["nodos"].items() if v.get("zona") is None},
                        {"internet", "fw-edge", "fw-core"})
