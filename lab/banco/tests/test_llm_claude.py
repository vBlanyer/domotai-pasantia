import json
import os
import subprocess
import threading
import unittest

from lab.scripts import llm_claude
from prototipo import justificador_llm, stream

ESQUEMA = {"type": "object", "properties": {"explicacion": {"type": "string"}},
           "required": ["explicacion"], "additionalProperties": False}


def _completado(salida, rc=0):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=salida, stderr="")


class TestComando(unittest.TestCase):
    def test_sin_herramientas_ni_ajustes_ni_sesion(self):
        cmd = llm_claude.comando("/bin/claude", "haiku")
        self.assertEqual(cmd[:2], ["/bin/claude", "-p"])
        for flag, valor in (("--model", "haiku"), ("--tools", ""), ("--setting-sources", ""),
                            ("--output-format", "json")):
            self.assertEqual(cmd[cmd.index(flag) + 1], valor)
        self.assertIn("--no-session-persistence", cmd)
        self.assertNotIn("--json-schema", cmd)

    def test_con_esquema_pasa_json_schema(self):
        cmd = llm_claude.comando("/bin/claude", "haiku", ESQUEMA)
        self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), ESQUEMA)


class TestGenerar(unittest.TestCase):
    def _generar(self, salida, esquema=None, **kw):
        llamadas = []
        def run(cmd, **opts):
            llamadas.append((cmd, opts))
            return salida if isinstance(salida, subprocess.CompletedProcess) else _completado(salida)
        texto = llm_claude.generar("el prompt", esquema, binario="/bin/claude", _run=run, **kw)
        return texto, llamadas

    def test_texto_libre(self):
        texto, llamadas = self._generar(json.dumps({"is_error": False, "result": "una explicación"}))
        self.assertEqual(texto, "una explicación")
        cmd, opts = llamadas[0]
        self.assertEqual(opts["input"], "el prompt")                 # por stdin, no por argv
        self.assertNotEqual(os.path.realpath(opts["cwd"]), os.path.realpath(os.getcwd()))
        self.assertNotIn("ANTHROPIC_API_KEY", opts["env"])           # siempre con la sesión, nunca con API

    def test_con_esquema_devuelve_el_objeto_validado(self):
        salida = json.dumps({"is_error": False, "result": "texto suelto",
                             "structured_output": {"explicacion": "fuerza bruta SSH"}})
        texto, _ = self._generar(salida, ESQUEMA)
        self.assertEqual(json.loads(texto), {"explicacion": "fuerza bruta SSH"})

    def test_fallos_devuelven_none(self):
        self.assertIsNone(self._generar(json.dumps({"is_error": True, "result": "límite"}))[0])
        self.assertIsNone(self._generar("no es json")[0])
        self.assertIsNone(self._generar(json.dumps({"is_error": False, "result": "x"}), ESQUEMA)[0])
        def lento(cmd, **opts):
            raise subprocess.TimeoutExpired(cmd, 1)
        self.assertIsNone(llm_claude.generar("p", binario="/bin/claude", _run=lento))

    def test_sin_binario_devuelve_none(self):
        from unittest import mock
        with mock.patch.object(llm_claude, "binario_claude", return_value=None):
            self.assertIsNone(llm_claude.generar("p", _run=lambda *a, **k: self.fail("no debe ejecutar")))


class TestContratoConElPrototipo(unittest.TestCase):
    """El servidor de pruebas habla con el cliente REAL del prototipo (generador_servidor y el
    sondeo de stream), no con una imitación de su petición."""

    def setUp(self):
        self.peticiones = []
        def generar_fn(prompt, esquema):
            self.peticiones.append((prompt, esquema))
            if "falla" in prompt:
                return None
            return json.dumps({"explicacion": "ok"}) if esquema else "justificación libre"
        self.srv = llm_claude.crear_servidor("haiku", 0, generar_fn)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self._modelo_previo = justificador_llm._MODELO_SERVIDOR
        justificador_llm._MODELO_SERVIDOR = None

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        justificador_llm._MODELO_SERVIDOR = self._modelo_previo

    def test_sondeo_de_salud(self):
        self.assertTrue(stream._servidor_responde(self.url))

    def test_texto_libre_y_etiqueta_del_modelo(self):
        self.assertEqual(justificador_llm.generador_servidor("explica la alerta", url=self.url),
                         "justificación libre")
        self.assertEqual(self.peticiones, [("explica la alerta", None)])
        self.assertEqual(justificador_llm._MODELO_SERVIDOR, "claude-code-haiku")

    def test_esquema_llega_y_vuelve_como_contenido(self):
        salida = justificador_llm.generador_servidor("explica", url=self.url, esquema=ESQUEMA)
        self.assertEqual(json.loads(salida), {"explicacion": "ok"})
        self.assertEqual(self.peticiones[0][1], ESQUEMA)

    def test_un_fallo_degrada_a_plantilla(self):
        self.assertEqual(justificador_llm.generador_servidor("esto falla", url=self.url), "")


if __name__ == "__main__":
    unittest.main()
