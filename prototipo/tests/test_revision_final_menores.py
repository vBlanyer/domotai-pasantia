"""Menores de la revisión final de la rama (16/11): cada uno con la prueba que lo fija."""
import os
import shutil
import subprocess
import tempfile
import unittest

from prototipo.accion import catalogo as catm
from prototipo.accion import conectividad as cx
from prototipo.motor import orden, perfil as perfilm
from prototipo.servicio import inventario_store

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = catm.cargar_catalogo(os.path.join(RAIZ, "catalogo.yml"))
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDJ5himPe7X53URUHbS8mCVzYlk3yQtq6pU0KZFfIZWV mdr-conector"


def _correr_envoltorio(texto, *args):
    """Ejecuta el envoltorio con binarios falsos que solo anotan; devuelve el código de salida."""
    d = tempfile.mkdtemp()
    try:
        b = os.path.join(d, "bin"); os.mkdir(b)
        for binario in {x for x, _ in catm.reglas(CAT)} | {"sh"}:
            with open(os.path.join(b, binario), "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(os.path.join(b, binario), 0o755)
        for real in ("grep", "cat"):
            os.symlink(shutil.which(real), os.path.join(b, real))
        ruta = os.path.join(d, "mdr-accion")
        with open(ruta, "w") as f:
            f.write(texto.replace("PATH=/usr/sbin:/usr/bin:/sbin:/bin", f"PATH={b}"))
        return subprocess.run(["sh", ruta, *args], capture_output=True, timeout=10).returncode
    finally:
        shutil.rmtree(d)


class TestValoresDeLista(unittest.TestCase):
    def test_un_valor_no_puede_empezar_por_guion(self):
        for malo in ("-d", "--status-all", ".oculto", "_x"):
            with self.subTest(valor=malo):
                with self.assertRaises(ValueError):
                    inventario_store._lista([malo], "cuentas")
                self.assertFalse(catm._VALOR_SEGURO.match(malo))
        self.assertEqual(inventario_store._lista(["appuser", "nginx.1"], "x"), ["appuser", "nginx.1"])


class TestUsuarioDelConector(unittest.TestCase):
    def test_el_envoltorio_protege_al_usuario_real_del_conector(self):
        env = catm.envoltorio(CAT, usuario="mdrsvc")
        self.assertEqual(_correr_envoltorio(env, "passwd", "-l", "mdrsvc"), 126)
        self.assertEqual(_correr_envoltorio(env, "passwd", "-l", "triaje"), 126)     # sigue siendo del sistema
        self.assertEqual(_correr_envoltorio(env, "passwd", "-l", "appuser"), 0)

    def test_el_paquete_web_pasa_el_usuario(self):
        env = catm.envoltorio_de_equipo(CAT, None, usuario="mdrsvc")
        self.assertIn("mdrsvc", env.split("SISTEMA=", 1)[1].split("\n", 1)[0])


class TestIpSinPrefijo(unittest.TestCase):
    def test_el_envoltorio_no_admite_prefijos(self):
        env = catm.envoltorio(CAT)
        for ip in ("0.0.0.0/0", "10.0.0.0/8", "10.0.0.0/24"):
            with self.subTest(ip=ip):
                self.assertEqual(_correr_envoltorio(env, "ss", "-K", "dst", ip), 126)
        self.assertEqual(_correr_envoltorio(env, "ss", "-K", "dst", "1.2.3.4"), 0)


class TestLimiteDeBanda(unittest.TestCase):
    def test_el_perfil_avisa_de_un_limite_de_banda_invalido(self):
        for malo in ("512kbps", "rapido", "1 mbit"):
            with self.subTest(valor=malo):
                avisos = perfilm.validar({"ip_gestion": "10.0.0.1", "continuidad": {"limite_banda": malo}})
                self.assertTrue(any("limite_banda" in a for a in avisos), avisos)
        for bueno in ("1mbit", "10Mbit", "512kbit"):
            avisos = perfilm.validar({"ip_gestion": "10.0.0.1", "continuidad": {"limite_banda": bueno}})
            self.assertFalse(any("limite_banda" in a for a in avisos), avisos)

    def test_la_orden_normaliza_la_unidad(self):
        perfil = {"activos": {"web": {"ip": "10.0.0.5", "interfaz": "eth1"}}, "continuidad": {"limite_banda": "10Mbit"}}
        o = orden.construir({"id_decision": "s1", "accion_final": "LIMITAR_BANDA", "activo": "web",
                             "origen_ip": "1.2.3.4"}, {}, perfil)
        self.assertEqual(o["params"]["rate"], "10mbit")


class TestScriptDeAlta(unittest.TestCase):
    def _script(self):
        acc = catm.PAPELES["servidor"]["acciones"]
        eq = {"nombre": "srv", "ip": "10.0.0.5", "papel": "servidor", "servicios": ["nginx"]}
        return cx.paquete("script", eq, "triaje", PUB, catm.reglas_de_equipo(CAT, acc, ["nginx"]), "hoy",
                          envoltorio=catm.envoltorio_de_equipo(CAT, acc, ["nginx"]))[1]

    def test_borra_los_temporales_si_falla(self):
        s = self._script()
        self.assertIn("""trap 'rm -f "$E" "$T"' EXIT""", s)
        self.assertLess(s.index("trap "), s.index("E=$(mktemp)"))

    def test_no_cambia_en_silencio_los_permisos_de_sbin(self):
        s = self._script()
        self.assertNotIn("install -d -m 755 /usr/local/sbin", s)
        self.assertIn("escribible por otros", s)

    def test_ansible_aparta_los_sudoers_antiguos(self):
        acc = catm.PAPELES["servidor"]["acciones"]
        eq = {"nombre": "srv", "ip": "10.0.0.5", "papel": "servidor"}
        yml = cx.paquete("ansible", eq, "triaje", PUB, catm.reglas_de_equipo(CAT, acc), "hoy",
                         envoltorio=catm.envoltorio_de_equipo(CAT, acc))[1]
        self.assertIn("mdr-sudoers-anterior", yml)
        self.assertIn("conector-triaje", yml)
        self.assertLess(yml.index("mdr-sudoers-anterior"), yml.index("dest: /etc/sudoers.d/mdr-triaje"))


class TestFicheroDePruebas(unittest.TestCase):
    def test_unittest_main_al_final(self):
        with open(os.path.join(RAIZ, "tests", "test_envoltorio.py"), encoding="utf-8") as f:
            texto = f.read()
        self.assertGreater(texto.index('if __name__ == "__main__":'), texto.rindex("\nclass "))


if __name__ == "__main__":
    unittest.main()
