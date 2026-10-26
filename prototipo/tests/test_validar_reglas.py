import contextlib, io, json, os, tempfile, unittest

from prototipo.herramientas import validar_reglas


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

    def test_tolera_entradas_malformadas_sin_crashear(self):
        # La herramienta caracteriza un export REAL (posiblemente sucio): una línea no-dict o un
        # contenedor hostil no debe abortar el informe (como la barrera de stream._parsear).
        crudas = [
            _cruda(["sshd", "authentication_failed"]),   # válida
            [1, 2],                                      # no-dict
            {"rule": None},                              # contenedor hostil
            "cadena",                                    # no-dict
        ]
        r = validar_reglas.cobertura(crudas)
        self.assertEqual(r["total"], 4)
        self.assertEqual(r["malformadas"], 3)
        self.assertEqual(r["por_familia"].get("acceso_credenciales"), 1)
        self.assertEqual(r["cubiertas"], 1)
        self.assertEqual(r["cubiertas"] + len(r["sin_cobertura"]) + r["propias"] + r["malformadas"],
                         r["total"])                     # invariante

    def test_reporta_el_nivel_de_cada_familia(self):
        # explotacion_conocida tria y encamina (no contiene); el reporte lo distingue de 'actuar'.
        r = validar_reglas.cobertura([_cruda(["exploit"])])
        self.assertEqual(r["por_familia"]["explotacion_conocida"], 1)
        self.assertEqual(r["nivel"]["explotacion_conocida"], "triar_y_enrutar")
        self.assertEqual(r["nivel"]["acceso_credenciales"], "actuar")


class TestMainFrontera(unittest.TestCase):
    def test_linea_json_anidada_cuenta_como_malformada(self):
        # json.loads lanza RecursionError (no ValueError) con anidamiento profundo: la línea
        # debe contarse como malformada, no abortar la CLI sobre un export hostil.
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("[" * 60000 + "]" * 60000 + "\n")
            ruta = f.name
        try:
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                rc = validar_reglas._main([ruta])
            self.assertEqual(rc, 0)
            self.assertIn("1 malformadas", salida.getvalue())
        finally:
            os.unlink(ruta)



class TestSalidaSinEscapes(unittest.TestCase):
    def test_un_grupo_hostil_no_inyecta_escapes_en_la_terminal(self):
        # B3 de la auditoría: los grupos del export del cliente se imprimían tal cual — una
        # secuencia ANSI podía alterar u ocultar lo que ve el operador en su terminal.
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"id": "x", "rule": {"id": "99999", "level": 5,
                                                    "groups": ["x\u001b[2Jy"]},
                                "predecoder": {"hostname": "h"}}) + "\n")
            ruta = f.name
        try:
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                validar_reglas._main([ruta])
            self.assertNotIn("\x1b", salida.getvalue())
        finally:
            os.unlink(ruta)


if __name__ == "__main__":
    unittest.main()
