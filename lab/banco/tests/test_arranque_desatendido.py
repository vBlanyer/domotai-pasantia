"""Scripts del laboratorio preparados para arrancar sin nadie delante (variante «laboratorio» de AWS,
plan-aws-laboratorio.md): terminan con error cuando algo falla. Se prueban con un `docker` falso delante
del PATH: no tocan el laboratorio real."""
import os
import stat
import subprocess
import tempfile
import time
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BANCO = os.path.join(RAIZ, "lab", "banco", "banco.sh")

# docker falso para `banco.sh test`: curl, ping y la última muestra de salud según el entorno.
DOCKER_TEST = r"""#!/bin/sh
case "$*" in
  *curl*) [ "${FALSO_CURL:-0}" = 0 ] && { echo '   HTTP 200'; exit 0; }; exit 7 ;;
  *ping*) exit "${FALSO_PING:-0}" ;;
  *salud.jsonl*) [ -n "${FALSO_SALUD:-}" ] && printf '%s\n' "$FALSO_SALUD"; exit 0 ;;
esac
exit 0
"""


def _ejecutar(args, docker, env=None, script=BANCO, timeout=60):
    """Ejecuta `sh <script> *args` con un `docker` falso (cuerpo sh `docker`) delante del PATH."""
    with tempfile.TemporaryDirectory() as d:
        falso = os.path.join(d, "docker")
        with open(falso, "w") as f:
            f.write(docker)
        os.chmod(falso, os.stat(falso).st_mode | stat.S_IEXEC)
        entorno = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"], FALSO_DIR=d)
        entorno.update(env or {})
        return subprocess.run(["sh", script, *args], capture_output=True, text=True, env=entorno,
                              cwd=RAIZ, timeout=timeout)


SANO = '{"estados": {"core-db": "ok", "web-banking": "ok"}}'


class TestTest(unittest.TestCase):
    def test_pasa_con_todo_sano(self):
        r = _ejecutar(["test"], DOCKER_TEST, {"FALSO_SALUD": SANO})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_falla_si_un_servicio_esta_caido(self):
        r = _ejecutar(["test"], DOCKER_TEST, {"FALSO_SALUD": '{"estados": {"core-db": "caido"}}'})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CAIDOS", r.stdout)
        self.assertIn("1 comprobación", r.stderr)

    def test_falla_si_un_cortafuegos_no_responde(self):
        r = _ejecutar(["test"], DOCKER_TEST, {"FALSO_SALUD": SANO, "FALSO_PING": "1"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_falla_sin_datos_de_salud(self):
        r = _ejecutar(["test"], DOCKER_TEST, {"FALSO_SALUD": ""})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
