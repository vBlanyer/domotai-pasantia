"""deploy/instalar.sh, ejecutado de verdad sobre un directorio (MDR_INSTALAR_RAIZ) con las órdenes que
tocan el sistema (useradd, chown, systemctl) sustituidas por registros."""
import os, shutil, stat, subprocess, tempfile, unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(RAIZ, "deploy", "instalar.sh")


class TestInstalarSh(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.raiz = os.path.join(self.d, "sistema")
        # el paquete: lo mínimo que instalar.sh copia
        self.pkg = os.path.join(self.d, "mdr-9.9")
        for sub in ("prototipo", "bin", "visor/dist"):
            os.makedirs(os.path.join(self.pkg, sub))
        shutil.copytree(os.path.join(RAIZ, "deploy"), os.path.join(self.pkg, "deploy"))
        shutil.copy(SCRIPT, os.path.join(self.pkg, "instalar.sh"))
        with open(os.path.join(self.pkg, "VERSION"), "w") as f:
            f.write("9.9\n")
        # órdenes del sistema simuladas: apuntan lo que se les pide
        self.bin = os.path.join(self.d, "bin")
        os.makedirs(self.bin)
        self.registro = os.path.join(self.d, "registro")
        for orden in ("useradd", "chown", "systemctl"):
            ruta = os.path.join(self.bin, orden)
            with open(ruta, "w") as f:
                f.write(f'#!/bin/sh\necho "{orden} $*" >> "{self.registro}"\n'
                        + ('[ "$1" = "is-active" ] && exit 3\n' if orden == "systemctl" else "") + "exit 0\n")
            os.chmod(ruta, 0o755)

    def _correr(self, *args, entrada="", path_extra=None):
        env = {"PATH": f"{path_extra + ':' if path_extra else ''}{self.bin}:/usr/bin:/bin", "MDR_INSTALAR_RAIZ": self.raiz}
        return subprocess.run(["sh", os.path.join(self.pkg, "instalar.sh"), *args], input=entrada,
                              capture_output=True, text=True, env=env, timeout=60)

    def _ordenes(self):
        try:
            with open(self.registro) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def test_instala_y_deja_todo_en_su_sitio(self):
        r = self._correr()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Siguiente paso: sudo mdr configurar", r.stdout)
        j = lambda *p: os.path.join(self.raiz, *p)
        self.assertTrue(os.path.isdir(j("opt", "mdr", "prototipo")))
        self.assertEqual(stat.S_IMODE(os.stat(j("etc", "mdr", "triaje.env")).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(j("var", "lib", "mdr")).st_mode), 0o700)
        with open(j("var", "lib", "mdr", "postura.json")) as f:
            self.assertEqual(f.read().strip(), '{"nodos": {}}')
        self.assertTrue(os.path.isfile(j("etc", "systemd", "system", "mdr-triaje.service")))
        self.assertEqual(os.readlink(j("usr", "bin", "mdr")), "/opt/mdr/bin/mdr")
        o = self._ordenes()
        self.assertIn("useradd --system --home-dir /var/lib/mdr --no-create-home", o)
        self.assertIn("chown -R root:root", o)
        self.assertIn("systemctl daemon-reload", o)

    def test_actualizar_guarda_la_anterior_y_no_pisa_la_configuracion(self):
        self._correr()
        env = os.path.join(self.raiz, "etc", "mdr", "triaje.env")
        with open(env, "a") as f:
            f.write("TRIAJE_CONSOLA_OPERADORES='{\"t\":\"ana\"}'\n")
        r = self._correr()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Actualizado a 9.9", r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.raiz, "opt", "mdr.anterior", "prototipo")))
        with open(env) as f:
            self.assertIn("ana", f.read())

    def test_sin_la_consola_construida_no_instala(self):
        shutil.rmtree(os.path.join(self.pkg, "visor"))
        r = self._correr()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("visor/dist", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "opt", "mdr")))

    def test_dependencias_que_faltan_se_dicen_todas_con_la_orden(self):
        # en este equipo hay de todo: se fuerza un python3 sin PyYAML delante en el PATH
        falsos = os.path.join(self.d, "falsos")
        os.makedirs(falsos)
        py = os.path.join(falsos, "python3")
        with open(py, "w") as f:
            f.write("#!/bin/sh\ncase \"$2\" in *yaml*) exit 1;; esac\nexit 0\n")
        os.chmod(py, 0o755)
        r = self._correr(path_extra=falsos)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Faltan dependencias", r.stderr)
        self.assertIn("python3-", r.stderr)

    def test_desinstalar_pide_confirmacion_y_conserva_la_traza(self):
        self._correr()
        traza = os.path.join(self.raiz, "var", "lib", "mdr", "trazas-cliente.jsonl")
        open(traza, "w").close()
        r = self._correr("--desinstalar", entrada="no\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.raiz, "opt", "mdr")))
        r = self._correr("--desinstalar", "--purgar", entrada="si\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "opt", "mdr")))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "etc", "mdr")))
        self.assertFalse(os.path.lexists(os.path.join(self.raiz, "usr", "bin", "mdr")))
        self.assertTrue(os.path.isfile(traza))                 # la evidencia no se borra nunca



class TestMdrPorEnlace(unittest.TestCase):
    def test_mdr_funciona_llamado_por_el_enlace_que_crea_instalar(self):
        # instalar.sh deja /usr/bin/mdr -> /opt/mdr/bin/mdr: mdr debe encontrar su programa igual.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        enlace = os.path.join(d, "mdr")
        os.symlink(os.path.join(RAIZ, "bin", "mdr"), enlace)
        r = subprocess.run([enlace, "validar-perfil", os.path.join(RAIZ, "deploy", "perfil.ejemplo.yml")],
                           capture_output=True, text=True, cwd=d, env={**os.environ, "MDR_ENV": "/no/existe"}, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("perfil sin avisos", r.stdout)


if __name__ == "__main__":
    unittest.main()
