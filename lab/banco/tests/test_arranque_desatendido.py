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

    def test_el_banco_da_mas_margen_al_ssh_del_conector(self):
        # Bajo una fuerza bruta contra el sshd del equipo, a los 5 s el MDR lo daba por caído (18/11).
        for ruta in (SERVICIO, os.path.join(RAIZ, "reiniciar.sh")):
            self.assertIn("export TRIAJE_SSH_PLAZO_CONEXION=15", _leer(ruta))

    def test_la_imagen_trae_ss_para_cortar_sesiones(self):
        # MATAR_CONEXION es `ss -K`: sin iproute2 fallaba siempre con «ss: not found» (18/11).
        self.assertRegex(_leer(os.path.join(RAIZ, "lab", "banco", "Dockerfile")), r"apk add[^\n]*\biproute2\b")

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
            # lo que numera el MDR en cada arranque (aquí, la decisión que pide analista y no puede preguntar
            # sin terminal queda como error con su id): BCO-AAAAMMDD-NNNN, el prefijo del perfil del banco
            import re
            ids = [r["id_decision"] for r in regs if re.match(r"^BCO-\d{8}-\d{4,}$", str(r.get("id_decision") or ""))]
            self.assertEqual(len(ids), 2)
            self.assertEqual(len(set(ids)), len(ids), ids)
            self.assertTrue(traza.verificar(regs)["valida"])


class TestReiniciarRetomaLaTraza(unittest.TestCase):
    """reiniciar.sh retoma la traza más reciente: la cola de Aprobaciones vuelve tras el reinicio (se
    restaura desde la traza que se retoma) y la numeración continúa. `--traza-nueva` empieza otra."""

    def _correr(self, *args, trazas=()):
        import shutil, subprocess, tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copy(os.path.join(RAIZ, "reiniciar.sh"), d)
        os.makedirs(os.path.join(d, "run"))
        for i, t in enumerate(trazas):
            ruta = os.path.join(d, "run", t)
            open(ruta, "w").close()
            os.utime(ruta, (1000 + i, 1000 + i))           # la última de la lista es la más reciente
        bin_ = os.path.join(d, "bin"); os.makedirs(bin_)
        for nombre, cuerpo in (("docker", 'case "$*" in *"ps --format"*) echo clab-red-cliente-wazuh;; esac'),
                               ("python3", 'echo "ARGS $*"'), ("pkill", "true")):
            with open(os.path.join(bin_, nombre), "w") as f:
                f.write(f"#!/bin/sh\n{cuerpo}\n")
            os.chmod(os.path.join(bin_, nombre), 0o755)
        cp = subprocess.run(["sh", "reiniciar.sh", *args], cwd=d, capture_output=True, text=True, timeout=20,
                            env={**os.environ, "PATH": bin_ + os.pathsep + os.environ["PATH"]})
        return next((l for l in cp.stdout.splitlines() if l.startswith("ARGS ")), cp.stdout + cp.stderr)

    def test_retoma_la_traza_mas_reciente(self):
        linea = self._correr(trazas=("trazas-2026-11-23-0823.jsonl", "trazas-2026-11-23-0955.jsonl"))
        self.assertIn("--salida run/trazas-2026-11-23-0955.jsonl", linea)

    def test_traza_nueva_empieza_otra_y_no_pasa_la_opcion_al_daemon(self):
        linea = self._correr("--traza-nueva", "--con-llm", trazas=("trazas-2026-11-23-0955.jsonl",))
        self.assertNotIn("0955", linea)
        self.assertNotIn("--traza-nueva", linea)
        self.assertIn("--con-llm", linea)

    def test_sin_trazas_empieza_una(self):
        self.assertRegex(self._correr(), r"--salida run/trazas-\d{4}-\d{2}-\d{2}-\d{4}\.jsonl")


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


# docker falso que apunta cada orden en $FALSO_DIR/ordenes y lista tres nodos del banco en `docker ps`.
DOCKER_APUNTA = r"""#!/bin/sh
echo "$*" >> "$FALSO_DIR/ordenes"
case "$1" in
  ps) printf 'clab-banco-taquilla\nclab-banco-internet\nclab-banco-web-banking\nclab-red-cliente-wazuh\n' ;;
esac
exit 0
"""


def _ordenes(args, env=None):
    with tempfile.TemporaryDirectory() as d:
        r = _ejecutar(args, DOCKER_APUNTA, dict(env or {}, FALSO_DIR=d))
        ruta = os.path.join(d, "ordenes")
        return r, (open(ruta).read().splitlines() if os.path.exists(ruta) else [])


class TestAliasDeAtaque(unittest.TestCase):
    """23/11: el lanzador añadía una IP por ataque rotado (`ip addr add`) y nadie la quitaba: 409 IPs pegadas
    en taquilla, middleware e internet, que el asistente de red encontraba como equipos."""

    def test_restaurar_quita_las_ip_secundarias_de_todos_los_nodos_del_banco(self):
        r, ordenes = _ordenes(["restaurar"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        quitar = [o for o in ordenes if "ip addr del" in o and "secondary" in o]
        self.assertEqual(sorted(o.split()[1] for o in quitar),
                         ["clab-banco-internet", "clab-banco-taquilla", "clab-banco-web-banking"])
        self.assertFalse([o for o in quitar if "wazuh" in o])                  # el Wazuh compartido no se toca


class TestClavesPropias(unittest.TestCase):
    """23/11: todos los nodos del banco compartían la clave SSH de host de la imagen: fijar la huella de un
    equipo no lo distinguía de otro, y el asistente no podía saber qué IPs son de la misma máquina."""

    def test_cada_nodo_genera_la_suya_una_sola_vez(self):
        r, ordenes = _ordenes(["claves-propias"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        claves = [o for o in ordenes if "ssh-keygen -A" in o]
        nodos = {o.split()[1] for o in claves}
        for n in ("web-banking", "atm", "core-db", "fw-core", "fw-edge", "mdr-siem", "pagos-qr", "taquilla"):
            self.assertIn(f"clab-banco-{n}", nodos)
        for o in claves:
            self.assertIn(".claves_propias", o)                # marca: un segundo `up` no las vuelve a cambiar
            self.assertIn("rm -f /etc/ssh/ssh_host_", o)
            # En vivo (23/11) el sshd nuevo arrancaba antes de que el viejo soltara el puerto 22 y moría: los
            # 14 nodos se quedaron SIN sshd. Hay que esperar a que el viejo termine antes de arrancarlo.
            self.assertLess(o.index("pkill"), o.index("while pgrep"))
            self.assertLess(o.index("while pgrep"), o.index("/usr/sbin/sshd -E"))
        self.assertIn("aprovisionar", r.stdout)                # recuerda volver a fijar las huellas

    def test_up_las_genera_antes_de_arrancar_sshd(self):
        texto = open(BANCO, encoding="utf-8").read()
        up = texto[texto.index("\n  up)"):texto.index("\n    ;;", texto.index("\n  up)"))]
        self.assertIn("claves_propias", up)
        self.assertLess(up.index("claves_propias"), up.index("/usr/sbin/sshd"))


class TestClienteNuevo(unittest.TestCase):
    """El banco como un cliente nuevo (23/11): sin aprovisionar, y el MDR con un perfil mínimo, para darlo de
    alta con el asistente de red y Conectividad como en el laboratorio oficina."""

    def test_desaprovisionar_deshace_lo_que_instala_aprovisionar(self):
        r, ordenes = _ordenes(["desaprovisionar"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        equipos = {o.split()[1] for o in ordenes if "deluser triaje" in o}
        for n in ("web-banking", "core-db", "atm", "taquilla", "fw-core", "fw-edge", "pagos-qr"):
            self.assertIn(f"clab-banco-{n}", equipos)
        for o in ordenes:
            if "deluser triaje" in o:
                self.assertIn("/etc/sudoers.d/conector-triaje", o)
                self.assertIn("/usr/local/sbin/mdr-accion", o)
                self.assertIn(">>> conector-triaje", o)               # el bloque de /etc/sudoers, si lo hay
        gestion = [o for o in ordenes if o.split()[1:2] == ["clab-banco-mdr-siem"] and "known_hosts_triaje" in o]
        self.assertTrue(gestion, ordenes)
        self.assertIn("/root/.ssh/triaje", gestion[0])                # la clave del conector también

    def test_mdr_nuevo_arranca_con_perfil_minimo_y_los_permisos_de_laboratorio(self):
        texto = open(BANCO, encoding="utf-8").read()
        i = texto.index("\n  mdr-nuevo)")
        bloque = texto[i:texto.index("\n    ;;", i)]
        self.assertIn("perfil_minimo --gestion 10.100.0.10", bloque)
        for r in ("10.10.0.0/24", "10.20.0.0/24", "10.30.0.0/24", "10.40.0.0/24", "10.50.0.0/24", "10.60.0.0/24",
                  "10.200.0.0/24", "10.210.0.0/24"):
            self.assertIn(f"--rango {r}", bloque)
        for v in ("TRIAJE_ASISTENTE_ABIERTO=1", "TRIAJE_CONECTIVIDAD_ABIERTA=1", "TRIAJE_POLITICA_ABIERTA=1",
                  "TRIAJE_NODO_GESTION=clab-banco-mdr-siem"):
            self.assertIn(v, bloque)
        self.assertIn("run/banco-nuevo", bloque)
        self.assertNotIn("bancario.yml", bloque)                      # no parte del perfil que ya lo sabe todo
