"""#6 de la revisión del 15/11: con TRIAJE_CON_LLM=1 en triaje.env, arrancar-mdr.sh arranca el daemon con
el modelo de lenguaje (--con-llm). Sin la variable, con la plantilla, como hasta ahora."""
import os
import subprocess
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARRANCAR = os.path.join(RAIZ, "deploy", "arrancar-mdr.sh")


def _arrancar(extra_env, modo="escuchar"):
    """Ejecuta arrancar-mdr.sh con un python3 falso que anota sus argumentos; devuelve esos argumentos."""
    d = tempfile.mkdtemp()
    anotado = os.path.join(d, "args")
    falso = os.path.join(d, "python3")
    with open(falso, "w") as f:
        f.write(f'#!/bin/sh\nprintf "%s\\n" "$@" > {anotado}\n')
    os.chmod(falso, 0o755)
    alerts = os.path.join(d, "alerts.json")
    open(alerts, "w").close()
    env = {"PATH": d + ":" + os.environ["PATH"], "TRIAJE_PERFIL": "p.yml", "TRIAJE_HALLAZGOS": "h.json",
           "TRIAJE_SALIDA": os.path.join(d, "t.jsonl"), **extra_env}
    if modo == "escuchar":
        env["TRIAJE_ESCUCHAR"] = "127.0.0.1:0"
    else:
        env["TRIAJE_ALERTS"] = alerts
    try:
        subprocess.run(["sh", ARRANCAR], env=env, timeout=5, capture_output=True)
    except subprocess.TimeoutExpired:
        pass                                  # el modo alerts deja tail -F vivo: basta con lo anotado
    with open(anotado) as f:
        return f.read().split("\n")


class TestArrancarConLlm(unittest.TestCase):
    def test_arrancar_con_llm(self):
        for modo in ("escuchar", "alerts"):
            with self.subTest(modo=modo):
                self.assertIn("--con-llm", _arrancar({"TRIAJE_CON_LLM": "1"}, modo))
                self.assertNotIn("--con-llm", _arrancar({}, modo))
                self.assertNotIn("--con-llm", _arrancar({"TRIAJE_CON_LLM": "0"}, modo))


if __name__ == "__main__":
    unittest.main()
