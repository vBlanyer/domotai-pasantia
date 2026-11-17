"""Variante MDR (producción) de infra/aws: pruebas estáticas sobre sus .tf, plantillas y documentos (sin red
ni cuenta). El arranque se ejerce de verdad en infra/aws/simulacro/ y el grafo contra AWS Emulator
(infra/aws/emulador/probar.sh mdr). Las descubre prototipo/tests/test_infra_aws.py."""
import glob
import os
import re
import unittest

CARPETA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # infra/aws/mdr
INFRA = CARPETA
BASE = os.path.join(os.path.dirname(CARPETA), "modulos", "base")
SHA_1_9_2 = "e35afcd4f4e70725ffb59585ed4353a3ebed273dcf6a29fe5dee4a676983aba0"


def _leer(rel):
    with open(os.path.join(CARPETA, rel), encoding="utf-8") as f:
        return f.read()


def _base(rel):
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


class TestEstructuraMdr(unittest.TestCase):
    """La variante MDR en su carpeta, sobre el módulo común (plan-aws-dos-carpetas.md, tarea 1)."""

    def test_usa_el_modulo_base(self):
        self.assertRegex(_leer("main.tf"), r'source\s*=\s*"\.\./modulos/base"')

    def test_sin_variante(self):
        v = _leer("variables.tf")
        self.assertNotIn('variable "variante"', v)
        self.assertNotIn("laboratorio_", v)

    def test_gpu_solo_con_llm(self):
        llm = _leer("llm.tf")
        for r in ('resource "aws_instance" "llm"', 'resource "aws_iam_role" "gpu"',
                  'resource "aws_iam_instance_profile" "gpu"', 'resource "aws_iam_role_policy_attachment" "gpu_ssm"',
                  'resource "aws_iam_role_policy" "gpu_s3"', 'resource "aws_security_group" "llm"'):
            self.assertIn(r, llm)
            cuerpo = llm[llm.index(r):]
            cuerpo = cuerpo[:cuerpo.index("\n}\n")]
            self.assertRegex(cuerpo, r"count\s*=\s*var\.llm_habilitado", r)

    def test_plan_sin_variables_no_pide_nada(self):
        # Review Focus 1: un `tofu plan` sin -var-file en mdr/ no se para pidiendo variables.
        v = _leer("variables.tf")
        for nombre, cuerpo in re.findall(r'variable "([a-z_0-9]+)" \{(.*?)\n\}', v, re.S):
            self.assertIn("default", cuerpo, nombre)


class TestArranqueMdr(unittest.TestCase):
    T = "templates/mdr_user_data.sh.tftpl"

    def test_arranque_instala_el_paquete(self):
        t = _leer(self.T)
        self.assertIn("instalar.sh", t)
        self.assertIn("sha256sum -c", t)
        self.assertNotIn("git clone", t)                     # #11: la consola compilada no está en git
        self.assertNotIn("chown -R triaje", t)               # #18: el código es de root, en solo lectura
        # lo que instalar.sh exige (lo destapó el simulacro: sin openssh-clients no instala)
        dnf = re.search(r"^dnf install -y (.+)$", t, re.M).group(1).split()
        for paquete in ("python3", "python3-pyyaml", "openssh-clients"):
            self.assertIn(paquete, dnf)

    def test_version_actual(self):
        v = _leer("variables.tf")
        self.assertNotIn("v1.4", v)                          # #7
        self.assertNotIn("repo_rama", v)
        self.assertRegex(v, r'variable "mdr_version"[^}]*default\s*=\s*"1\.9\.2"')
        self.assertIn(SHA_1_9_2, v)
        plantilla = _leer("produccion.tfvars.ejemplo")
        self.assertRegex(plantilla, r'(?m)^mdr_version\s*=\s*"1\.9\.2"')
        self.assertIn(SHA_1_9_2, plantilla)

    def test_disco_obligatorio(self):
        t = _leer(self.T)
        self.assertIn("RequiresMountsFor=/var/lib/mdr", t)   # #10: sin disco, el servicio no arranca
        # …pero la instancia sí (nofail): sin él, un EBS ausente la deja en modo de emergencia, sin SSM
        self.assertRegex(t, r"xfs defaults,nofail 0 2")
        self.assertRegex(t, r"if \[ -z \"\$DISCO\" \]; then[^}]*?exit 1")

    def test_traza_firmada_y_consola_con_token(self):
        t = _leer(self.T)                                    # #19
        self.assertIn("TRIAJE_TRAZA_CLAVE", t)
        self.assertIn("analista alta admin", t)
        self.assertIn("/root/mdr-token-admin", t)
        self.assertIn("systemctl enable --now mdr-triaje", t)

    def test_avisa_si_la_traza_existe_y_la_clave_es_nueva(self):
        t = _leer(self.T)
        self.assertIn('[ -s "$ESTADO/trazas-cliente.jsonl" ] && TRAZA_PREVIA=si', t)   # antes de instalar
        self.assertRegex(t, r'if \[ "\$TRAZA_PREVIA" = si \]; then\n\s*echo "AVISO')

    def test_secreto_indicado_ilegible_para(self):
        t = _leer(self.T)
        self.assertIn("set -euo pipefail", t)
        self.assertNotIn("|| true", t)
        # una asignación directa: si la lectura falla (tras reintentar), set -e para el arranque
        self.assertRegex(t, r"\n\s*[A-Z]+=\$\((reintentar )?aws secretsmanager get-secret-value")

    def test_variables_del_modelo(self):
        t = _leer(self.T)                                    # #6
        for v in ("LLAMA_URL", "LLAMA_EMBED_URL", "TRIAJE_CON_LLM"):
            self.assertIn(v, t)
        for f in glob.glob(os.path.join(INFRA, "**", "*"), recursive=True):
            if os.path.isfile(f) and f.endswith((".tf", ".tftpl", ".sh", ".py", ".md", ".ejemplo")) \
                    and os.sep + "pruebas" + os.sep not in f:
                with open(f, encoding="utf-8") as g:
                    self.assertNotIn("TRIAJE_LLM_URL", g.read(), f)

    def test_destroy_apaga_antes_de_desmontar(self):
        self.assertRegex(_leer("mdr.tf"), r"stop_instance_before_detaching\s*=\s*true")   # #12

    def test_plantillas_sin_doble_dolar_suelto(self):
        # templatefile solo escapa «$${»: «$$(» llega tal cual y bash lo lee como el PID
        for f in glob.glob(os.path.join(INFRA, "templates", "*.tftpl")):
            with open(f, encoding="utf-8") as g:
                self.assertIsNone(re.search(r"\$\$(?!\{)", g.read()), f)


class TestGpu(unittest.TestCase):
    T = "templates/llm_user_data.sh.tftpl"

    def test_gpu_sin_fallos_silenciosos(self):
        t = _leer(self.T)                                    # #9
        self.assertIn("set -euo pipefail", t)
        self.assertNotIn("|| true", t)
        self.assertIn("-DGGML_CUDA=ON", t)
        self.assertIn("sha256sum -c", t)
        self.assertIn("--port 8080", t)                      # el generador
        self.assertIn("--port 8082", t)                      # #8: el embedder del RAG
        self.assertIn("--pooling cls", t)
        self.assertIn("systemctl enable --now llama-gen llama-embed", t)

    def test_gpu_exige_modelos(self):
        llm = _leer("llm.tf")
        self.assertIn("precondition", llm)
        for v in ("llm_modelo_url", "llm_modelo_sha256", "embed_modelo_url", "embed_modelo_sha256"):
            self.assertIn(f"var.{v}", llm)
            self.assertRegex(_leer("variables.tf"), rf'variable "{v}"')
        self.assertIn("Deep Learning Base OSS Nvidia Driver GPU AMI (Amazon Linux 2023)", llm)

    def test_sg_embedder(self):
        net = _leer("llm.tf")
        self.assertRegex(net, r"from_port\s*=\s*8082\s*\n\s*to_port\s*=\s*8082")


class TestRevisionFinal(unittest.TestCase):
    """Hallazgos importantes de la revisión final de la rama (17/11)."""
    MDR = "templates/mdr_user_data.sh.tftpl"
    GPU = "templates/llm_user_data.sh.tftpl"

    def test_gpu_no_con_un_paquete_sin_con_llm(self):           # I1: v1.9.1 no trae TRIAJE_CON_LLM
        self.assertRegex(_leer("llm.tf"), r'var\.mdr_version\s*!=\s*"1\.9\.1"')

    def test_espera_al_modelo_y_reinicia(self):                  # I2: el daemon sondea el modelo una vez
        t = _leer(self.MDR)
        self.assertIn("systemd-run --unit=mdr-espera-modelo", t)
        self.assertIn("/health", t)
        self.assertIn("systemctl restart mdr-triaje", t)

    def test_generador_con_contexto_acotado(self):               # I3: sin -c reserva 128k de contexto
        self.assertIn("--port 8080 -ngl 99 -c 8192", _leer(self.GPU))

    def test_gpu_con_rol_propio_sin_secretos(self):              # I4
        self.assertIn("aws_iam_instance_profile.gpu[0].name", _leer("llm.tf"))
        self.assertNotIn("secretsmanager", _leer("llm.tf"))

    def test_sin_egreso_exige_s3_y_endpoint_de_secretos(self):   # I5
        mdr = _leer("mdr.tf")
        self.assertRegex(mdr, r'var\.egreso_bootstrap \|\| startswith\(local\.paquete_url, "s3://"\)')
        self.assertIn("var.egreso_bootstrap", _leer("llm.tf"))
        self.assertIn('"com.amazonaws.${var.region}.secretsmanager"', _base("red.tf"))

    def test_dueños_de_la_traza_tras_recrear(self):              # I7: otro UID para triaje
        self.assertIn('find "$ESTADO" -xdev ! -user triaje -exec chown triaje:triaje {} +', _leer(self.MDR))

    def test_reintentos_y_permisos_antes_de_la_instancia(self):  # I8
        t = _leer(self.MDR)
        self.assertIn("reintentar()", t)
        self.assertRegex(t, r"=\$\(reintentar aws secretsmanager get-secret-value")
        self.assertIn("reintentar curl", t)
        for f in ("mdr.tf", "llm.tf"):
            self.assertIn("depends_on", _leer(f))

    def test_nmap_para_el_asistente(self):                       # I9
        dnf = re.search(r"^dnf install -y (.+)$", _leer(self.MDR), re.M).group(1).split()
        self.assertIn("nmap", dnf)

    def test_el_disco_es_el_ebs_por_su_id(self):                 # I10: no un disco efímero
        t = _leer(self.MDR)
        self.assertIn("/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${volumen}", t)
        self.assertNotIn("/dev/nvme1n1", t)
        self.assertRegex(_base("outputs.tf"), r'volumen_traza_nvme(.|\n)*?replace\(aws_ebs_volume\.traza\.id, "-", ""\)')
        self.assertIn("volumen = module.base.volumen_traza_nvme", _leer("mdr.tf"))


class TestDespliegueProduccion(unittest.TestCase):
    """Entregables para el despliegue oficial (plan del emulador, tareas 3–6)."""

    def test_tfvars_cubre_las_variables(self):
        variables = re.findall(r'^variable "([a-z_0-9]+)"', _leer("variables.tf"), re.M)
        plantilla = _leer("produccion.tfvars.ejemplo")
        for v in variables:
            self.assertRegex(plantilla, rf"(?m)^#?\s*{v}\s*=", f"falta {v} en produccion.tfvars.ejemplo")

    def test_inventario_al_dia(self):
        import json
        declarados = set()
        for f in glob.glob(os.path.join(INFRA, "*.tf")) + glob.glob(os.path.join(BASE, "*.tf")):
            with open(f, encoding="utf-8") as g:
                declarados |= set(re.findall(r'^resource "([a-z0-9_]+)"', g.read(), re.M))
        inventariados = set()
        for f in glob.glob(os.path.join(INFRA, "..", "inventario", "escenario-*.json")):
            with open(f, encoding="utf-8") as g:
                inventariados |= {r["tipo"] for r in json.load(g)["recursos"]}
        self.assertEqual(declarados - inventariados, set(), "recursos sin inventariar: regenera el inventario")
        with open(os.path.join(INFRA, "..", "inventario", "README.md"), encoding="utf-8") as g:
            leible = g.read()
        for tipo in declarados:
            self.assertIn(tipo, leible)

    def test_backend_remoto_de_ejemplo(self):
        b = _leer("backend.tf.ejemplo")
        self.assertIn('backend "s3"', b)
        self.assertIn("encrypt", b)


class TestRevisionEmulador(unittest.TestCase):
    """Hallazgos de la revisión final del plan del emulador (17/11)."""

    def test_salidas_con_raw(self):                              # sin -raw, las comillas salen escapadas
        for doc in ("../DESPLIEGUE.md", "../README.md"):
            self.assertIsNone(re.search(r"tofu output (?!-raw)comando_", _leer(doc)), doc)

    def test_emulador_no_copia_el_backend_de_produccion(self):
        self.assertIn('rm -f "$d/backend.tf"', _leer("../emulador/probar.sh"))

    def test_comprobar_no_da_verde_sin_el_arranque(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("comprobar", os.path.join(INFRA, "..", "emulador", "comprobar.py"))
        comprobar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(comprobar)
        estado = {"values": {"root_module": {"resources": [
            {"address": "aws_instance.mdr", "type": "aws_instance",
             "values": {"associate_public_ip_address": False, "metadata_options": [{"http_tokens": "required"}],
                        "root_block_device": [{"encrypted": True}], "user_data": "a" * 40}},
            {"address": "data.aws_instance.comprobar_mdr", "type": "aws_instance", "values": {}},
        ]}}}
        fallos = [n for n, ok in comprobar.comprobaciones("A", estado) if not ok]
        self.assertTrue(any("arranque" in n for n in fallos), fallos)

    def test_bucket_del_estado_en_us_east_1(self):               # allí LocationConstraint da error
        self.assertIn("us-east-1", _leer("backend.tf.ejemplo"))

    def test_plantilla_sin_marcadores_que_rompan_el_arranque(self):
        t = _leer("produccion.tfvars.ejemplo")
        self.assertNotIn("<bucket>", t)                          # todo lo que hay que rellenar dice <rellenar…>
        self.assertRegex(t, r'(?m)^perfil_url\s*=\s*""')         # opcional: vacío salvo que se suba un perfil

    def test_nat_no_es_solo_del_primer_arranque(self):           # se cobra mientras egreso_bootstrap = true
        for f in ("../emulador/inventario.py", "../inventario/README.md"):
            self.assertNotIn("solo primer arranque", _leer(f), f)
        self.assertIn("aunque no haya GPU", _leer("../inventario/README.md"))

    def test_instantanea_de_la_traza_reproducible(self):
        d = _leer("../DESPLIEGUE.md")
        self.assertRegex(d, r"create-snapshot --region")
        self.assertIn("tofu state show aws_ebs_volume.traza", d)
        self.assertIn("file://", d)                              # los tokens no van en la línea de órdenes
        self.assertIn("*.plan", _leer("../.gitignore"))


if __name__ == "__main__":
    unittest.main()
