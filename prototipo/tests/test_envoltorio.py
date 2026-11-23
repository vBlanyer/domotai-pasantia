"""#13 de la revisión del 15/11: el envoltorio `mdr-accion`. En sudoers un comodín `*` admite espacios, así que
`iptables -A INPUT -s * -j DROP` dejaba pasar `--modprobe=<programa>` (root). El envoltorio valida cada
argumento por su tipo y solo ejecuta las plantillas del catálogo; el sudoers permite únicamente el envoltorio.

Las pruebas ejecutan el envoltorio generado con `sh` y un PATH de binarios falsos que anotan lo que reciben."""
import os
import shutil
import subprocess
import tempfile
import unittest

from prototipo.accion import catalogo as catm

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = catm.cargar_catalogo(os.path.join(RAIZ, "catalogo.yml"))


class _Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.bin = os.path.join(self.d, "bin")
        os.mkdir(self.bin)
        self.log = os.path.join(self.d, "llamadas.log")
        for binario in {b for b, _ in catm.reglas(CAT)} | {"sh", "id"}:
            ruta = os.path.join(self.bin, binario)
            with open(ruta, "w") as f:
                f.write(f'#!/bin/sh\necho "{binario} $*" >> {self.log}\n')
            os.chmod(ruta, 0o755)
        for real in ("grep", "cat"):                       # lo que el envoltorio usa para validar y listar
            os.symlink(shutil.which(real), os.path.join(self.bin, real))

    def _envoltorio(self, allowlist=None):
        ruta = os.path.join(self.d, "mdr-accion")
        with open(ruta, "w") as f:
            f.write(catm.envoltorio(CAT, allowlist=allowlist, path=self.bin))
        os.chmod(ruta, 0o755)
        return ruta

    def _correr(self, *args, allowlist=None):
        cp = subprocess.run(["sh", self._envoltorio(allowlist), *args], capture_output=True, text=True, timeout=10)
        llamadas = open(self.log).read().splitlines() if os.path.exists(self.log) else []
        if os.path.exists(self.log):
            os.unlink(self.log)
        return cp.returncode, llamadas, cp.stderr


class TestEnvoltorio(_Base):
    def test_envoltorio_permite_lo_legitimo(self):
        casos = [
            ("iptables", "-A", "INPUT", "-s", "1.2.3.4", "-j", "DROP"),
            ("iptables", "-D", "INPUT", "-s", "10.0.0.7", "-j", "DROP"),
            ("iptables", "-A", "FORWARD", "-d", "198.51.100.10", "-j", "DROP"),
            # cuarentena que deja pasar la gestión, su reversión, y la reversión de una cuarentena antigua
            ("iptables", "-A", "FORWARD", "-s", "10.10.0.10", "!", "-d", "10.100.0.10", "-j", "DROP"),
            ("iptables", "-D", "FORWARD", "-s", "10.10.0.10", "!", "-d", "10.100.0.10", "-j", "DROP"),
            ("iptables", "-D", "FORWARD", "-s", "10.10.0.10", "-j", "DROP"),
            ("iptables", "-A", "INPUT", "-p", "tcp", "--dport", "5432", "-j", "DROP"),
            ("tc", "qdisc", "replace", "dev", "eth0", "root", "tbf", "rate", "1mbit", "burst", "32kbit", "latency", "400ms"),
            ("tc", "qdisc", "del", "dev", "eth1", "root"),
            ("passwd", "-l", "appuser"),
            ("service", "nginx", "stop"),
            ("ss", "-K", "dst", "1.2.3.4"),
            ("iptables", "-L", "-n"),
            ("ss", "-tunap"),
            ("ip", "addr"),
        ]
        for args in casos:
            with self.subTest(args=args):
                rc, llamadas, err = self._correr(*args)
                self.assertEqual(rc, 0, err)
                self.assertEqual(llamadas, [" ".join(args)])

    def test_envoltorio_rechaza_tokens_de_mas(self):
        for args in (("iptables", "-A", "INPUT", "-s", "1.2.3.4", "--modprobe=/tmp/x", "-j", "DROP"),
                     ("iptables", "-A", "INPUT", "-s", "1.2.3.4", "-j", "ACCEPT", "-j", "DROP"),
                     ("iptables", "-A", "INPUT", "-s", "1.2.3.4", "-j", "DROP", "-v"),
                     ("iptables", "-F", "INPUT"), ("sh", "-c", "id"), ("/sbin/iptables", "-L", "-n"), ()):
            with self.subTest(args=args):
                rc, llamadas, _ = self._correr(*args)
                self.assertEqual((rc, llamadas), (126, []))

    def test_envoltorio_rechaza_argumento_con_espacio(self):
        for ip in ("1.2.3.4 --modprobe=/tmp/x", "1.2.3.4\n--modprobe=/tmp/x", "1.2.3.400", "-1.2.3.4", "", "1.2.3.4/33"):
            with self.subTest(ip=ip):
                rc, llamadas, _ = self._correr("iptables", "-A", "INPUT", "-s", ip, "-j", "DROP")
                self.assertEqual((rc, llamadas), (126, []))
        for args in (("iptables", "-A", "INPUT", "-p", "tcp", "--dport", "0", "-j", "DROP"),
                     ("iptables", "-A", "INPUT", "-p", "tcp", "--dport", "70000", "-j", "DROP"),
                     ("tc", "qdisc", "del", "dev", "-eth0", "root"),
                     ("tc", "qdisc", "replace", "dev", "eth0", "root", "tbf", "rate", "1mbit;id", "burst", "32kbit",
                      "latency", "400ms")):
            with self.subTest(args=args):
                self.assertEqual(self._correr(*args)[:2], (126, []))

    def test_envoltorio_cuentas_y_servicios(self):
        for cuenta in ("root", "daemon", "sshd", "triaje", "-a"):
            with self.subTest(cuenta=cuenta):
                self.assertEqual(self._correr("passwd", "-l", cuenta)[:2], (126, []))
        lista = {"service": ["nginx"], "passwd": ["appuser"]}
        self.assertEqual(self._correr("service", "nginx", "stop", allowlist=lista)[0], 0)
        self.assertEqual(self._correr("service", "sshd", "stop", allowlist=lista)[:2], (126, []))
        self.assertEqual(self._correr("passwd", "-l", "otro", allowlist=lista)[:2], (126, []))
        self.assertEqual(self._correr("passwd", "-l", "appuser", allowlist=lista)[0], 0)

    def test_reglas_coinciden_con_el_catalogo(self):
        for allowlist in (None, {"service": ["nginx", "apache2"], "passwd": ["appuser"]}):
            with self.subTest(allowlist=allowlist):
                rc, _, _ = 0, None, None
                cp = subprocess.run(["sh", self._envoltorio(allowlist), "--reglas"], capture_output=True, text=True)
                self.assertEqual(cp.returncode, 0)
                esperadas = [f"{b} {a}".strip() for b, a in catm.reglas(CAT, allowlist)]
                self.assertEqual(cp.stdout.splitlines(), esperadas)

    def test_el_path_es_fijo(self):
        texto = catm.envoltorio(CAT)
        self.assertIn('PATH=/usr/sbin:/usr/bin:/sbin:/bin', texto)
        self.assertNotIn("$PATH", texto)

    def test_sudoers_solo_permite_el_envoltorio(self):
        lineas = [l for l in catm.sudoers_envoltorio("triaje").splitlines() if l and not l.startswith("#")]
        self.assertEqual(lineas, ["triaje ALL=(root) NOPASSWD: /usr/local/sbin/mdr-accion"])

    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck no instalado")
    def test_shellcheck(self):
        ruta = self._envoltorio({"service": ["nginx"]})
        cp = subprocess.run(["shellcheck", "-s", "sh", ruta], capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stdout)



class TestCLI(unittest.TestCase):
    def test_cli_imprime_el_envoltorio_con_allowlist(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as out:
            rc = catm._main(["--envoltorio", "--allowlist", "service=nginx,passwd=appuser:root"])
        self.assertEqual(rc, 0)
        texto = out.getvalue()
        self.assertTrue(texto.startswith("#!/bin/sh"))
        self.assertIn("service nginx stop", texto)
        self.assertIn("passwd -l appuser", texto)
        self.assertNotIn("passwd -l root", texto)               # una cuenta del sistema nunca entra en la lista


class TestListaSoloDeCuentasDelSistema(unittest.TestCase):
    def test_no_reabre_el_comodin(self):
        reglas = catm.reglas(CAT, {"passwd": ["root", "daemon"]})
        self.assertFalse([r for r in reglas if r[0] == "passwd"], reglas)


if __name__ == "__main__":
    unittest.main()
