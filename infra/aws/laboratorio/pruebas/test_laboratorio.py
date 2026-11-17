"""Variante laboratorio de infra/aws (el banco, su Wazuh y el MDR en una máquina; no se conecta a ningún
cliente): pruebas estáticas sobre sus .tf, su plantilla de arranque y sus documentos (sin red ni cuenta).
El grafo se prueba contra AWS Emulator (infra/aws/emulador/probar.sh laboratorio) y el arranque del
laboratorio, en vivo, con lab/banco/servicio-mdr.sh. Las descubre prototipo/tests/test_infra_aws.py."""
import os
import re
import unittest

CARPETA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # infra/aws/laboratorio
MDR = os.path.join(os.path.dirname(CARPETA), "mdr")
COMMIT_1_9_2 = "2c64820df320f0eab32583f7de1b4f2d99546d78"   # el de la etiqueta v1.9.2


def _leer(rel):
    with open(os.path.join(CARPETA, rel), encoding="utf-8") as f:
        return f.read()


def _variables():
    return dict(re.findall(r'variable "([a-z_0-9]+)" \{(.*?)\n\}', _leer("variables.tf"), re.S))


class TestLaboratorio(unittest.TestCase):
    T = "templates/laboratorio_user_data.sh.tftpl"
    MENSAJES = (
        "La variante laboratorio necesita un MDR >= 1.9.2: la 1.9.1 no trae los arreglos del laboratorio.",
        "laboratorio_commit: los 40 caracteres hexadecimales del commit de la etiqueta v<mdr_version>.",
    )

    def test_usa_el_modulo_base(self):
        self.assertRegex(_leer("main.tf"), r'source\s*=\s*"\.\./modulos/base"')

    def test_siempre_con_egreso(self):
        self.assertRegex(_leer("main.tf"), r"egreso\s*=\s*true")
        v = _variables()
        for nombre in ("egreso_bootstrap", "variante", "llm_habilitado", "perfil_url", "red_cliente_cidrs"):
            self.assertNotIn(nombre, v)

    def test_variables_y_valores_por_defecto(self):
        v = _variables()
        self.assertRegex(v["laboratorio_tipo"], r'default\s*=\s*"t3\.xlarge"')
        self.assertRegex(v["laboratorio_disco_gb"], r"default\s*=\s*40\b")
        self.assertRegex(v["mdr_version"], r'default\s*=\s*"1\.9\.2"')
        self.assertRegex(v["proyecto"], r'default\s*=\s*"mdr-laboratorio"')

    def test_solo_falta_el_commit(self):
        # Review Focus 1: un `tofu plan` sin -var-file solo pide lo que de verdad falta.
        sin_defecto = [n for n, cuerpo in _variables().items() if "default" not in cuerpo]
        self.assertEqual(sin_defecto, ["laboratorio_commit"])

    def test_precondiciones(self):
        lab = _leer("laboratorio.tf")
        for m in self.MENSAJES:
            self.assertIn(m, lab)

    def test_arranque_del_laboratorio(self):
        t = _leer(self.T)
        self.assertIn("set -euo pipefail", t)
        self.assertNotIn("|| true", t)
        for s in ("--branch v${mdr_version}", "git rev-parse HEAD", "${laboratorio_commit}", "sha256sum -c",
                  "visor/dist", "0.79.0", "construir-imagen.sh", "systemctl enable --now mdr-laboratorio",
                  "/root/mdr-token-admin", "mdr-laboratorio.service"):
            self.assertIn(s, t)
        self.assertLess(t.index("git rev-parse HEAD"), t.index("construir-imagen.sh"))

    def test_commit_distinto_para(self):
        t = _leer(self.T)
        i = t.index("git rev-parse HEAD")
        self.assertIn("exit 1", t[i:i + 400])
        self.assertNotIn("docker", t[t.index("git clone"):t.index("exit 1", i)])

    @unittest.skipUnless(os.path.isdir(MDR), "sin la variante mdr/ no hay con qué comparar")
    def test_mismo_disco_que_el_mdr(self):
        def bloque(texto):
            return texto[texto.index('DISCO=""'):texto.index('mountpoint -q "$ESTADO" || mount "$ESTADO"')]
        with open(os.path.join(MDR, "templates", "mdr_user_data.sh.tftpl"), encoding="utf-8") as f:
            self.assertEqual(bloque(_leer(self.T)), bloque(f.read()))

    def test_costes_del_laboratorio(self):
        c = _leer("../COSTES.md")
        self.assertIn("t3.xlarge", c)
        for uso in ("Encendido 24/7", "Parar y encender", "destroy"):
            self.assertIn(uso, c)
        self.assertIn("E · laboratorio", c)

    def test_guia_del_laboratorio(self):
        d = _leer("../DESPLIEGUE.md")
        s = d[d.index("## Variante laboratorio"):]
        for txt in ("no se conecta a ningún cliente", "stop-instances", "banco.sh atacar", "comprobar-alertas",
                    "journalctl -u mdr-laboratorio", "laboratorio_commit", "systemctl restart mdr-laboratorio",
                    "reiniciar.sh", "se anotan como revertidas", COMMIT_1_9_2):
            self.assertIn(txt.lower(), s.lower())


if __name__ == "__main__":
    unittest.main()
