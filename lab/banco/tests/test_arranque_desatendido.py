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


# docker falso para `comprobar-alertas`: un alerts.json de verdad en FALSO_DIR. El disparo (nc desde el
# auditor) añade una alerta 100200 si FALSO_LLEGA=1; las lecturas del fichero se ejecutan sobre la copia.
DOCKER_ALERTAS = r"""#!/bin/sh
A="$FALSO_DIR/alerts.json"
[ -f "$A" ] || [ "${FALSO_SIN_FICHERO:-0}" = 1 ] || printf '%b' "${FALSO_PREVIA:-}" > "$A"
for ultimo; do :; done
case "$ultimo" in
  *"| nc "*) [ "${FALSO_LLEGA:-0}" = 1 ] && echo '{"rule":{"level":6,"id":"100200"},"data":{"srcip":"10.100.0.20"}}' >> "$A"; exit 0 ;;
  *alerts.json*) eval "$(printf '%s' "$ultimo" | sed "s#/var/ossec/logs/alerts/alerts.json#$A#g")" ;;
esac
"""
PREVIA_SIN_100200 = '{"rule":{"id":"5715"}}\\n{"rule":{"id":"5402"}}\\n'
PREVIA_CON_100200 = '{"rule":{"id":"100200"},"data":{"srcip":"10.100.0.20"}}\\n'


class TestComprobarAlertas(unittest.TestCase):
    def test_falla_si_la_alerta_no_llega(self):
        r = _ejecutar(["comprobar-alertas"], DOCKER_ALERTAS,
                      {"FALSO_PREVIA": PREVIA_SIN_100200, "ALERTAS_ESPERA_MAX": "2"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_ok_cuando_llega(self):
        r = _ejecutar(["comprobar-alertas"], DOCKER_ALERTAS,
                      {"FALSO_PREVIA": PREVIA_SIN_100200, "FALSO_LLEGA": "1", "ALERTAS_ESPERA_MAX": "6"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK: Wazuh generó la alerta 100200", r.stdout)

    def test_no_cuenta_alertas_anteriores(self):
        r = _ejecutar(["comprobar-alertas"], DOCKER_ALERTAS,
                      {"FALSO_PREVIA": PREVIA_CON_100200, "ALERTAS_ESPERA_MAX": "2"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_sin_alerts_json_todavia(self):
        # Un Wazuh recién levantado puede no haber escrito aún ninguna alerta: no es un fallo.
        r = _ejecutar(["comprobar-alertas"], DOCKER_ALERTAS,
                      {"FALSO_SIN_FICHERO": "1", "FALSO_LLEGA": "1", "ALERTAS_ESPERA_MAX": "6"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_origen_del_evento(self):
        # El disparo sale del auditor (activo de gestión del perfil): con el MDR en marcha, el motor lo
        # trata como actividad legítima y no contiene nada.
        with open(BANCO, encoding="utf-8") as f:
            banco = f.read()
        orden = banco[banco.index("  comprobar-alertas)"):]
        orden = orden[:orden.index(";;")]
        self.assertIn("$P-auditor", orden)
        import json
        from lab.banco import pruebas
        from prototipo.motor import perfil as perfilm, triaje
        from prototipo.accion import catalogo as catm
        perfil = perfilm.cargar(pruebas.PERFIL)
        catalogo = catm.cargar_catalogo(os.path.join(RAIZ, "prototipo", "catalogo.yml"))
        with open(pruebas.HALLAZGOS, encoding="utf-8") as f:
            hallazgos = json.load(f)
        a = {"familia": "reconocimiento", "activo": "web-banking", "servicio": "ssh", "origen_ip": "10.100.0.20",
             "regla_id": "100200", "mitre": ["T1046"], "timestamp": "2026-11-17T00:00:00Z", "id_alerta": "x"}
        t = triaje.procesar(a, hallazgos, perfil, "bancario", catalogo, id_decision="x", timestamp=a["timestamp"])
        self.assertEqual(t["clase"], "fp_actividad_legitima")
        self.assertIsNone(t["accion_final"])
        with open(os.path.join(RAIZ, "lab", "banco", "README.md"), encoding="utf-8") as f:
            self.assertIn("comprobar-alertas", f.read())


SERVICIO = os.path.join(RAIZ, "lab", "banco", "servicio-mdr.sh")
UNIDAD = os.path.join(RAIZ, "lab", "banco", "mdr-laboratorio.service")


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


class TestServicio(unittest.TestCase):
    def test_rehace_el_laboratorio_en_orden(self):
        s = _leer(SERVICIO)
        pasos = ["banco.sh down", "lab.sh up banco", "banco.sh aprovisionar", "banco.sh test",
                 "banco.sh comprobar-alertas", "lab.banco.rehecho", "prototipo.servicio.stream"]
        posiciones = [s.index(p) for p in pasos]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_mismas_variables_que_reiniciar(self):
        import re
        s = _leer(SERVICIO)
        exports = re.findall(r"^export (TRIAJE_\w+=\S+)", _leer(os.path.join(RAIZ, "reiniciar.sh")), re.M)
        self.assertGreaterEqual(len(exports), 4)
        for e in exports:
            self.assertIn(f"export {e}", s)

    def test_traza_fija_en_el_disco(self):
        self.assertIn("/var/lib/mdr/trazas-laboratorio.jsonl", _leer(SERVICIO))

    def test_bash_estricto(self):
        s = _leer(SERVICIO)
        self.assertTrue(s.startswith("#!/bin/bash"))
        self.assertIn("set -euo pipefail", s)
        self.assertEqual(subprocess.run(["bash", "-n", SERVICIO]).returncode, 0)

    def test_unidad(self):
        u = _leer(UNIDAD)
        for linea in ("EnvironmentFile=/etc/mdr/triaje.env", "WorkingDirectory=/opt/mdr-laboratorio",
                      "ExecStart=/bin/bash /opt/mdr-laboratorio/lab/banco/servicio-mdr.sh",
                      "Requires=docker.service", "RequiresMountsFor=/var/lib/mdr", "Restart=always",
                      "RestartSec=30", "WantedBy=multi-user.target"):
            self.assertIn(linea, u)
        self.assertRegex(u, r"After=.*docker\.service")
        # un fallo persistente no rehace el banco sin fin (coste de CPU en AWS)
        self.assertIn("StartLimitIntervalSec=2h", u)
        self.assertIn("StartLimitBurst=5", u)

    def test_traza_fija_sin_ids_repetidos_tras_reinicio(self):
        import json
        from prototipo.servicio import traza
        with tempfile.TemporaryDirectory() as d:
            salida = os.path.join(d, "trazas-laboratorio.jsonl")
            for _ in range(2):                       # dos arranques sobre la misma traza
                subprocess.run(["python3", "-m", "prototipo.servicio.stream", "lab/portatil/alerta-muestra.jsonl",
                                "prototipo/perfiles/bancario.yml",
                                "lab/campañas/2026-09-22-banco-hallazgos/hallazgos.json",
                                "--sin-lab", "--una-vez", "--salida", salida],
                               cwd=RAIZ, stdin=subprocess.DEVNULL, capture_output=True, timeout=120, check=True)
            regs = traza.leer_registros(salida)
            ids = [r["id_decision"] for r in regs if str(r.get("id_decision") or "").startswith("s")]
            self.assertEqual(len(ids), 2)
            self.assertEqual(len(set(ids)), len(ids), ids)
            self.assertTrue(traza.verificar(regs)["valida"])


class TestRehecho(unittest.TestCase):
    """Tras rehacer el laboratorio (encender la máquina), las contenciones de la traza ya no existen:
    se anotan como revertidas para que el MDR no suprima los ataques repetidos ni la consola las muestre."""

    def _traza(self, d):
        from prototipo.servicio import traza
        ruta = os.path.join(d, "trazas-laboratorio.jsonl")
        bloqueo = {"tipo": "decision", "id_decision": "s7", "activo": "web-banking", "accion_final": "BLOQUEAR_IP",
                   "orden": {"accion_id": "BLOQUEAR_IP", "nodo_objetivo": "web-banking", "nodo_ip": "10.10.0.10",
                             "params": {"ip": "198.51.100.10"}},
                   "ejecucion": {"accion_id": "BLOQUEAR_IP", "nodo": "web-banking", "exito": True},
                   "verificacion": {"verificado": True},
                   "contexto": {"origen_ip": "198.51.100.10", "familia": "acceso_credenciales"},
                   "timestamp": "2026-11-17T10:00:00Z"}
        with traza.abrir_append(ruta) as f:
            traza.Cadena(f, traza.GENESIS, n=0, nombre=os.path.basename(ruta), ruta=ruta).escribir(bloqueo)
        return ruta

    def test_retira_las_contenciones_del_laboratorio_anterior(self):
        from prototipo.servicio import traza, stream
        from prototipo.accion import contenciones, catalogo as catm
        cat = catm.cargar_catalogo(os.path.join(RAIZ, "prototipo", "catalogo.yml"))
        with tempfile.TemporaryDirectory() as d:
            ruta = self._traza(d)
            self.assertEqual(len(contenciones.activas(traza.leer_registros(ruta), cat)), 1)
            r = subprocess.run(["python3", "-m", "lab.banco.rehecho", ruta], cwd=RAIZ, capture_output=True,
                               text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            regs = traza.leer_registros(ruta)
            self.assertEqual(contenciones.activas(regs, cat), [])
            mem = stream.MemoriaDecisiones.desde_traza(regs)
            self.assertIsNone(mem.buscar(("198.51.100.10", "web-banking", "acceso_credenciales")))
            self.assertTrue(traza.verificar(regs)["valida"])
            self.assertIn("laboratorio rehecho", regs[-1]["motivo"])
            self.assertIsNone(regs[-1]["comando_ejecutado"])      # no se ejecutó nada: el equipo se recreó

    def test_sin_traza_no_hace_nada(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "no-existe.jsonl")
            r = subprocess.run(["python3", "-m", "lab.banco.rehecho", ruta], cwd=RAIZ, capture_output=True,
                               text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(os.path.exists(ruta))


if __name__ == "__main__":
    unittest.main()
