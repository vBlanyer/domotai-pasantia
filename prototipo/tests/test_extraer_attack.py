import unittest
from prototipo import extraer_attack as ex


def _tecnica(ext_id, name, desc, sub=False, deprecated=False, revoked=False, tactic="credential-access"):
    o = {"type": "attack-pattern", "name": name, "description": desc,
         "x_mitre_is_subtechnique": sub, "x_mitre_deprecated": deprecated, "revoked": revoked,
         "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": tactic}],
         "external_references": [{"source_name": "mitre-attack", "external_id": ext_id}]}
    return o


BUNDLE = {"objects": [
    _tecnica("T1110.001", "Password Guessing",
             "Adversaries may guess passwords (Citation: Foo2020) to access accounts. See [SSH](https://x)."),
    _tecnica("T1021.004", "Remote Services: SSH", "Adversaries may use SSH for lateral movement."),
    _tecnica("T9999", "Deprecada", "no deberia salir", deprecated=True),
    _tecnica("T8888", "Revocada", "tampoco", revoked=True),
    _tecnica("T7777", "Fuera de perimetro", "no esta en la allowlist"),
    {"type": "course-of-action", "name": "Mitigacion X",
     "external_references": [{"source_name": "mitre-attack", "external_id": "M1234"}]},
]}


class TestLimpiar(unittest.TestCase):
    def test_quita_citas_y_enlaces_markdown(self):
        t = ex._limpiar("Texto (Citation: Foo2020) con [enlace](https://x) y fin.")
        self.assertNotIn("Citation", t)
        self.assertNotIn("https://", t)
        self.assertIn("enlace", t)          # conserva el texto del enlace, no la url
        self.assertIn("Texto", t)

    def test_trunca_a_longitud_maxima(self):
        t = ex._limpiar("a " * 500, tope=120)
        self.assertLessEqual(len(t), 121)


class TestExtraer(unittest.TestCase):
    def test_id_externo(self):
        o = _tecnica("T1110", "Brute Force", "x")
        self.assertEqual(ex._id_externo(o), "T1110")

    def test_extrae_solo_allowlist_no_deprecadas(self):
        # T9999 (deprecada) y T8888 (revocada) van en la allowlist pero deben excluirse por su estado
        fichas = ex.extraer_tecnicas(BUNDLE["objects"], {"T1110.001", "T1021.004", "T9999", "T8888"})
        ids = {f["id"] for f in fichas}
        self.assertEqual(ids, {"mitre-T1110.001", "mitre-T1021.004"})   # deprecada/revocada excluidas
        f = next(f for f in fichas if f["id"] == "mitre-T1110.001")
        self.assertEqual(f["tipo"], "mitre")
        self.assertIn("T1110.001", f["titulo"]); self.assertIn("Password Guessing", f["titulo"])
        self.assertNotIn("Citation", f["texto"])

    def test_no_incluye_lo_fuera_de_allowlist(self):
        fichas = ex.extraer_tecnicas(BUNDLE["objects"], {"T1110.001"})
        self.assertEqual([f["id"] for f in fichas], ["mitre-T1110.001"])


class TestCompilar(unittest.TestCase):
    def test_une_curado_y_extraidas_dedup_por_id(self):
        curado = [{"id": "regla-5760", "tipo": "regla", "titulo": "5760", "texto": "x"},
                  {"id": "mitre-T1110.001", "tipo": "mitre", "titulo": "vieja", "texto": "hecha a mano"}]
        extraidas = [{"id": "mitre-T1110.001", "tipo": "mitre", "titulo": "T1110.001 Password Guessing", "texto": "oficial"}]
        corpus = ex.compilar_corpus(curado, extraidas)
        ids = [d["id"] for d in corpus]
        self.assertEqual(ids.count("mitre-T1110.001"), 1)                # deduplicado
        t = next(d for d in corpus if d["id"] == "mitre-T1110.001")
        self.assertEqual(t["texto"], "oficial")                          # la extraída gana
        self.assertIn("regla-5760", ids)                                 # el curado se conserva


if __name__ == "__main__":
    unittest.main()
