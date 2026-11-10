import os, tempfile, unittest
from prototipo.herramientas import analistas, entorno


class Registro:
    """Ejecutor falso: apunta las órdenes y contesta lo que se le diga."""
    def __init__(self, respuestas=None):
        self.ordenes, self.respuestas = [], respuestas or {}

    def __call__(self, args, **kw):
        self.ordenes.append(list(args))
        rc = self.respuestas.get(args[0], 0)
        return type("R", (), {"returncode": rc, "stdout": "", "stderr": "error simulado" if rc else ""})()


class TestTokens(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.env = os.path.join(d, "triaje.env")
        with open(self.env, "w") as f:
            f.write("TRIAJE_PERFIL=/etc/mdr/perfil.yml\n#TRIAJE_CONSOLA_OPERADORES='{}'\n")

    def test_alta_genera_un_token_nuevo_y_lo_guarda(self):
        t = analistas.alta(self.env, "ana", generar=lambda: "tok-ana")
        self.assertEqual(t, "tok-ana")
        self.assertEqual(entorno.operadores(entorno.leer(self.env)), {"tok-ana": "ana"})
        analistas.alta(self.env, "leo", generar=lambda: "tok-leo")
        self.assertEqual(analistas.lista(self.env), ["ana", "leo"])

    def test_nombre_repetido_o_invalido_se_rechaza(self):
        analistas.alta(self.env, "ana", generar=lambda: "t1")
        for malo in ("ana", "Ana López", "", "x" * 40, "root;rm"):
            with self.assertRaises(ValueError):
                analistas.alta(self.env, malo, generar=lambda: "t2")

    def test_baja_quita_todos_sus_tokens(self):
        analistas.alta(self.env, "ana", generar=lambda: "t1")
        analistas.alta(self.env, "leo", generar=lambda: "t2")
        analistas.baja(self.env, "ana")
        self.assertEqual(analistas.lista(self.env), ["leo"])
        with self.assertRaises(ValueError):
            analistas.baja(self.env, "ana", forzar=True)

    def test_dar_de_baja_al_ultimo_exige_forzar_porque_abre_la_consola(self):
        analistas.alta(self.env, "ana", generar=lambda: "t1")
        with self.assertRaises(ValueError) as cm:
            analistas.baja(self.env, "ana")
        self.assertIn("abierta", str(cm.exception))
        analistas.baja(self.env, "ana", forzar=True)
        self.assertEqual(analistas.lista(self.env), [])

    def test_comprobar_alta_falla_antes_de_tocar_el_sistema(self):
        analistas.alta(self.env, "ana", generar=lambda: "t1")
        with self.assertRaises(ValueError):
            analistas.comprobar_alta(self.env, "ana")
        with self.assertRaises(ValueError):
            analistas.comprobar_alta(self.env, "Ana López")
        analistas.comprobar_alta(self.env, "leo")             # válido: no lanza

    def test_el_token_por_defecto_es_largo_y_distinto(self):
        a, b = analistas.alta(self.env, "ana"), analistas.alta(self.env, "leo")
        self.assertGreaterEqual(len(a), 40)
        self.assertNotEqual(a, b)


class TestCuentaSSH(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.pub = os.path.join(self.d, "ana.pub")
        with open(self.pub, "w") as f:
            f.write("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDZZ ana@portatil\n")

    def test_prepara_el_tunel_y_crea_la_cuenta_limitada(self):
        conf = os.path.join(self.d, "sshd_config.d", "mdr-analistas.conf")
        os.makedirs(os.path.dirname(conf))
        run = Registro({"getent": 2})                         # el grupo aún no existe
        analistas.preparar_tunel(conf, ejecutar=run, puerto=8787)
        with open(conf) as f:
            texto = f.read()
        self.assertIn("Match Group mdr-analistas", texto)
        self.assertIn("PermitOpen 127.0.0.1:8787", texto)
        for linea in ("AllowStreamLocalForwarding no", "AllowAgentForwarding no", "PermitTunnel no"):
            self.assertIn(linea, texto)
        self.assertIn(["groupadd", "--system", "mdr-analistas"], run.ordenes)
        self.assertIn(["sshd", "-t"], run.ordenes)
        casa = os.path.join(self.d, "home-ana")
        run2 = Registro({"id": 1})                            # la cuenta no existe
        analistas.crear_cuenta("ana", self.pub, ejecutar=run2, casa=casa)
        self.assertEqual(run2.ordenes[1][:2], ["useradd", "--create-home"])
        self.assertIn("mdr-analistas", run2.ordenes[1])
        with open(os.path.join(casa, ".ssh", "authorized_keys")) as f:
            self.assertIn("ssh-ed25519", f.read())

    def test_si_sshd_rechaza_la_configuracion_se_retira(self):
        conf = os.path.join(self.d, "mdr-analistas.conf")
        with self.assertRaises(SystemExit):
            analistas.preparar_tunel(conf, ejecutar=Registro({"sshd": 1}), puerto=8787)
        self.assertFalse(os.path.exists(conf))

    def test_una_clave_que_no_es_publica_no_se_instala(self):
        malo = os.path.join(self.d, "privada")
        with open(malo, "w") as f:
            f.write("-----BEGIN OPENSSH PRIVATE KEY-----\n")
        with self.assertRaises(ValueError):
            analistas.crear_cuenta("ana", malo, ejecutar=Registro({"id": 1}), casa=self.d)


if __name__ == "__main__":
    unittest.main()
