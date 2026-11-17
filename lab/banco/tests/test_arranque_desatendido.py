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


ESPERA = os.path.join(RAIZ, "lab", "scripts", "esperar-wazuh.sh")


def _esperar(docker, env):
    """Carga esperar-wazuh.sh y llama a esperar_wazuh con un docker falso."""
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(f'. "{ESPERA}"\nesperar_wazuh prueba-wazuh\n')
    try:
        return _ejecutar([], docker, env, script=f.name)
    finally:
        os.unlink(f.name)


class TestEsperaWazuh(unittest.TestCase):
    def test_se_agota_con_error(self):
        nunca = "#!/bin/sh\ncase \"$1\" in logs) echo 'ultima linea del registro';; esac\nexit 1\n"
        t0 = time.monotonic()
        r = _esperar(nunca, {"WAZUH_ESPERA_MAX": "2", "WAZUH_ESPERA_PASO": "1"})
        self.assertNotEqual(r.returncode, 0)
        self.assertLess(time.monotonic() - t0, 10)
        self.assertIn("no arrancó", r.stderr)
        self.assertIn("ultima linea del registro", r.stderr)

    def test_termina_cuando_wazuh_arranca(self):
        vivo = "#!/bin/sh\necho 'wazuh-analysisd is running...'\nexit 0\n"
        r = _esperar(vivo, {"WAZUH_ESPERA_MAX": "5", "WAZUH_ESPERA_PASO": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_las_tres_esperas_usan_la_funcion(self):
        for rel in ("lab/scripts/wazuh-run.sh", "lab/lab.sh"):
            with open(os.path.join(RAIZ, rel), encoding="utf-8") as g:
                t = g.read()
            # ninguna espera a Wazuh sin tope (la del FTP de lab.sh test ya tiene el suyo)
            self.assertNotRegex(t, r"until docker exec[^\n]*wazuh-control", rel)
            self.assertIn("esperar-wazuh.sh", t, rel)
            self.assertIn("esperar_wazuh", t, rel)


if __name__ == "__main__":
    unittest.main()
