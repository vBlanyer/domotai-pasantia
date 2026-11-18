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
    def test_guia_sin_frases_cortadas(self):
        # al repartir las guías quedaron frases sin su comienzo (líneas que empiezan por un espacio suelto)
        self.assertEqual(re.findall(r"(?m)^ \S.*$", _leer("DESPLIEGUE.md")), [])

    def test_salida_con_el_disco_de_la_traza(self):
        # la instantánea antes de destroy necesita el id del disco (vive en el módulo común)
        self.assertRegex(_leer("outputs.tf"), r'output "volumen_traza_id"(.|\n)*?module\.base\.volumen_traza_id')
        self.assertIn("tofu output -raw volumen_traza_id", _leer("DESPLIEGUE.md"))
        self.assertNotIn("tofu state show aws_ebs_volume.traza", _leer("DESPLIEGUE.md"))

    def test_sin_variante_en_los_documentos(self):
        for doc in ("DESPLIEGUE.md", "README.md", "COSTES.md"):
            self.assertNotIn("variante =", _leer(doc), doc)

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
        c = _leer("COSTES.md")
        self.assertIn("t3.xlarge", c)
        for uso in ("Encendido 24/7", "Parar y encender", "destroy"):
            self.assertIn(uso, c)
        self.assertRegex(c, r"\| `eu-west-1` \| 0,276 \$")   # por hora, con la máquina, los discos, el NAT y los endpoints

    def test_plantilla_de_variables(self):
        t = _leer("laboratorio.tfvars.ejemplo")
        for v in _variables():
            self.assertRegex(t, rf"(?m)^#?\s*{v}\s*=", v)
        self.assertIn(COMMIT_1_9_2, t)

    def test_guia_del_laboratorio(self):
        s = _leer("DESPLIEGUE.md")
        for txt in ("no se conecta a ningún cliente", "stop-instances", "banco.sh atacar", "comprobar-alertas",
                    "journalctl -u mdr-laboratorio", "laboratorio_commit", "systemctl restart mdr-laboratorio",
                    "reiniciar.sh", "se anotan como revertidas", COMMIT_1_9_2):
            self.assertIn(txt.lower(), s.lower())



class TestSimulacro(unittest.TestCase):
    """Simulacro del laboratorio: el arranque de AWS ejecutado en un contenedor Amazon Linux 2023 con systemd
    (simulacro/). Aislado de los contenedores del equipo y con la consola solo en 127.0.0.1."""
    S = "simulacro/simulacro.sh"

    def test_es_sh_valido(self):
        import subprocess
        self.assertEqual(subprocess.run(["sh", "-n", os.path.join(CARPETA, self.S)]).returncode, 0)

    def test_ejecuta_la_plantilla_real(self):
        s = _leer(self.S)
        self.assertIn("templates/laboratorio_user_data.sh.tftpl", s)
        self.assertIn(COMMIT_1_9_2, s)
        self.assertIn("MDR_DISCOS=", s)             # el disco de la traza, como en el simulacro del MDR

    def test_maquina_con_systemd_real(self):
        d = _leer("simulacro/Dockerfile")
        self.assertIn("FROM amazonlinux:2023", d)
        self.assertIn('CMD ["/usr/sbin/init"]', d)

    def test_aislado_del_equipo(self):
        # nunca la red del equipo ni su Docker: el simulacro no puede tocar los contenedores del usuario
        s = _leer(self.S)
        self.assertNotIn("--network host", s)
        self.assertNotIn("--net=host", s)
        self.assertNotIn("docker.sock", s)

    def test_consola_solo_en_localhost(self):
        s = _leer(self.S)
        # las publicaciones de puertos de docker run (no el «-p Propiedad=…» de systemd-run)
        publicados = re.findall(r'-p\s+"?([0-9$][^"\s]*)', s)
        self.assertTrue(publicados)
        for p in publicados:
            self.assertTrue(p.startswith("127.0.0.1:"), p)

    def test_limpia_siempre(self):
        s = _leer(self.S)
        self.assertRegex(s, r"trap .*EXIT")
        self.assertRegex(s, r"trap .*INT TERM")       # Ctrl-C también limpia (dash no corre EXIT con señales)
        self.assertIn("losetup -d", s)                 # el disco de bucle vive en el núcleo del equipo

    def test_instrucciones(self):
        r = _leer("README.md")
        s = r[r.index("## Cómo probarla"):]
        self.assertIn("sh infra/aws/laboratorio/simulacro/simulacro.sh", s)
        self.assertIn("--mantener", s)

    def test_lee_solo_la_ejecucion_actual_de_la_unidad(self):
        # dentro de un contenedor el «arranque» (-b) es el del núcleo del equipo y no cambia al reiniciar:
        # se lee el diario de la ejecución en curso de la unidad, por su identificador de invocación
        s = _leer(self.S)
        self.assertIn("_SYSTEMD_INVOCATION_ID", s)
        self.assertNotIn("journalctl -b", s)

    def test_tras_reiniciar_hace_de_aviso_del_disco(self):
        # en AWS systemd monta el disco y arranca la unidad al recibir el aviso del dispositivo; en el contenedor
        # ese aviso no llega y el simulacro hace su papel: montar y arrancar la unidad
        s = _leer(self.S)
        tras = s[s.index("docker restart"):]
        self.assertIn("mount /var/lib/mdr", tras)
        self.assertIn("systemctl start --no-block mdr-laboratorio", tras)


if __name__ == "__main__":
    unittest.main()
