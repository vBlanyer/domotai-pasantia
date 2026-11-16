"""#13 de la revisión del 15/11 (tarea 4): el conector, la prueba de Conectividad, el paquete de alta y el
aprovisionamiento del laboratorio usan el envoltorio `mdr-accion`."""
import os
import unittest

from prototipo.accion import catalogo as catm
from prototipo.accion import conectividad as cx
from prototipo.accion import conector, fallos

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = catm.cargar_catalogo(os.path.join(RAIZ, "catalogo.yml"))
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDJ5himPe7X53URUHbS8mCVzYlk3yQtq6pU0KZFfIZWV mdr-conector"
ENV = catm.ENVOLTORIO_RUTA


class TestConector(unittest.TestCase):
    def test_comando_con_envoltorio(self):
        linea = conector.comando_ssh_clave("10.0.0.5", "iptables -L -n")
        self.assertIn(f"LC_ALL=C sudo -S {ENV} iptables -L -n", linea)
        self.assertTrue(conector._args_ssh_directo("10.0.0.5", "iptables -L -n")[-1]
                        .endswith(f"sudo -S {ENV} iptables -L -n"))
        self.assertTrue(conector.comando_ssh_clave("10.0.0.5", "true", sudo=False).endswith('"true"'))
        self.assertTrue(conector._args_ssh_directo("10.0.0.5", "sudo -S -l", sudo=False)[-1] == "sudo -S -l")

    def test_el_rechazo_del_envoltorio_es_f6(self):
        self.assertEqual(fallos.patron("mdr-accion: orden fuera del catálogo; no se ejecuta"), "F6")


def _ejecutor(respuestas):
    """Ejecutor falso: (rc, salida) por comando; lo no previsto, éxito vacío."""
    def ej(ip, comando):
        return respuestas.get(comando, (0, ""))
    return ej


class TestPruebaDeConectividad(unittest.TestCase):
    ESPERADAS = catm.reglas_de_equipo(CAT, ["OBS_CONEXIONES", "BLOQUEAR_IP"])
    REGLAS_TXT = "\n".join(f"{b} {a}".strip() for b, a in ESPERADAS)
    SUDO_L = f"User triaje may run the following commands on x:\n    (root) NOPASSWD: {ENV}\n"

    NIEGA = (1, "sudo: a password is required")

    def _probar(self, ejecutor, sudo_l, testigo=None):
        listar = _ejecutor({"sudo -S -l": (0, sudo_l), "sudo -S true": testigo or self.NIEGA})
        return cx.probar(ejecutor, "10.0.0.5", listar=listar, esperadas=self.ESPERADAS)

    # Revisión final: lo que sudo responde DE VERDAD en un equipo con el sudoers antiguo (sin regla
    # para mdr-accion y stdin cerrado): pide contraseña, sin nombrar el envoltorio.
    SUDO_L_ANTIGUO = ("User triaje may run the following commands on x:\n"
                      "    (root) NOPASSWD: /sbin/iptables -A INPUT -s * -j DROP, /sbin/iptables -L -n\n")

    def test_alta_antigua_se_diagnostica_y_falta_todo(self):
        for salida in ("sudo: a password is required", "sudo: no password was provided"):
            with self.subTest(salida=salida):
                r = self._probar(_ejecutor({"iptables -L -n": (1, salida)}), self.SUDO_L_ANTIGUO)
                self.assertEqual(r["estado"], "sin_aprovisionar")
                self.assertIn("paquete de alta", r["pasos"][-1]["detalle"])
                self.assertEqual(sorted(r["reglas"]["faltan"]), sorted(self.REGLAS_TXT.splitlines()))
                self.assertIn("iptables -A INPUT -s * -j DROP", r["reglas"]["sobran"])

    def test_un_fallo_con_envoltorio_no_es_alta_antigua(self):
        r = self._probar(_ejecutor({"iptables -L -n": (1, "iptables: not found")}), self.SUDO_L)
        self.assertEqual(r["estado"], "fallo")

    def test_testigo_de_sudo_va_sin_envoltorio(self):
        # un equipo con NOPASSWD: ALL: el envoltorio rechaza «true», pero sudo lo permitiría
        ej = _ejecutor({"true": (126, "rechazo"), "--reglas": (0, self.REGLAS_TXT)})
        r = self._probar(ej, self.SUDO_L, testigo=(0, ""))
        self.assertEqual(r["estado"], "privilegio_de_mas")

    def test_envoltorio_en_otra_ruta_es_privilegio_de_mas(self):
        ej = _ejecutor({"true": (126, "rechazo"), "--reglas": (0, self.REGLAS_TXT)})
        r = self._probar(ej, self.SUDO_L + "    (root) NOPASSWD: /home/triaje/mdr-accion\n")
        self.assertEqual(r["estado"], "privilegio_de_mas")
        self.assertIn("/home/triaje/mdr-accion", r["reglas"]["sobran"])

    def test_deriva_sin_envoltorio(self):
        for salida in (f"Sorry, user triaje is not allowed to execute '{ENV} iptables -L -n' as root on x.",
                       f"sudo: {ENV}: command not found"):
            with self.subTest(salida=salida):
                r = cx.probar(_ejecutor({"iptables -L -n": (1, salida)}), "10.0.0.5")
                self.assertEqual(r["estado"], "sin_aprovisionar")
                self.assertIn("paquete de alta", r["pasos"][-1]["detalle"])

    def test_envoltorio_que_coincide(self):
        ej = _ejecutor({"true": (126, "mdr-accion: orden fuera del catálogo; no se ejecuta"), "--reglas": (0, self.REGLAS_TXT)})
        r = self._probar(ej, self.SUDO_L)
        self.assertEqual((r["estado"], r["reglas"]["estado"]), ("verificada", "coinciden"))

    def test_deriva_envoltorio_con_reglas_de_mas(self):
        ej = _ejecutor({"true": (126, "rechazo"), "--reglas": (0, self.REGLAS_TXT + "\npasswd -l *")})
        r = self._probar(ej, self.SUDO_L)
        self.assertEqual(r["estado"], "privilegio_de_mas")
        self.assertIn("passwd -l *", r["reglas"]["sobran"])

    def test_sudo_permite_algo_ademas_del_envoltorio(self):
        ej = _ejecutor({"true": (126, "rechazo"), "--reglas": (0, self.REGLAS_TXT)})
        r = self._probar(ej, self.SUDO_L + "    (root) NOPASSWD: /sbin/iptables -A INPUT -s * -j DROP\n")
        self.assertEqual(r["estado"], "privilegio_de_mas")
        self.assertIn("iptables -A INPUT -s * -j DROP", r["reglas"]["sobran"])

    def test_envoltorio_con_reglas_de_menos_avisa(self):
        menos = "\n".join(self.REGLAS_TXT.splitlines()[1:])
        r = self._probar(_ejecutor({"true": (126, "rechazo"), "--reglas": (0, menos)}), self.SUDO_L)
        self.assertEqual(r["estado"], "verificada")
        self.assertEqual(len(r["reglas"]["faltan"]), 1)


class TestPaquete(unittest.TestCase):
    EQ = {"nombre": "srv-web01", "ip": "172.16.10.10", "papel": "servidor", "servicios": ["nginx"]}

    def _paquete(self, formato):
        acciones = catm.PAPELES["servidor"]["acciones"]
        reglas = catm.reglas_de_equipo(CAT, acciones, servicios=["nginx"])
        env = catm.envoltorio_de_equipo(CAT, acciones, servicios=["nginx"])
        return cx.paquete(formato, self.EQ, "triaje", PUB, reglas, "16/11/2026", envoltorio=env)[1], env

    def test_paquete_instala_el_envoltorio(self):
        for formato in ("script", "ansible", "sudoers"):
            with self.subTest(formato=formato):
                texto, env = self._paquete(formato)
                lineas_sudo = [l.strip() for l in texto.splitlines() if "NOPASSWD:" in l]
                self.assertEqual(lineas_sudo, [f"triaje ALL=(root) NOPASSWD: {ENV}"])
                self.assertNotIn("/sbin/iptables -A", texto)
        script, env = self._paquete("script")
        self.assertIn(env, script)                                   # el envoltorio va entero en el script
        self.assertIn(f"install -m 755 -o root -g root", script)
        ansible, env = self._paquete("ansible")
        self.assertIn(f"dest: {ENV}", ansible)
        self.assertIn('mode: "0755"', ansible)

    def test_el_envoltorio_del_equipo_es_el_de_su_papel(self):
        acciones = catm.PAPELES["puesto"]["acciones"]
        env = catm.envoltorio_de_equipo(CAT, acciones, cuentas=["appuser"])
        reglas = catm.reglas_de_equipo(CAT, acciones, cuentas=["appuser"])
        bloque = env.split("cat <<'FIN_REGLAS'\n", 1)[1].split("\nFIN_REGLAS", 1)[0]
        self.assertEqual(bloque.splitlines(), [f"{b} {a}".strip() for b, a in reglas])


class TestAprovisionarLaboratorio(unittest.TestCase):
    def test_aprovisionar_instala_el_envoltorio(self):
        with open(os.path.join(os.path.dirname(RAIZ), "lab", "scripts", "aprovisionar-minimo-privilegio.sh"), encoding="utf-8") as f:
            texto = f.read()
        self.assertIn("--envoltorio", texto)
        self.assertIn(ENV, texto)
        self.assertNotIn("--sudoers", texto)


if __name__ == "__main__":
    unittest.main()
