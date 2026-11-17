"""Despliegue en AWS (infra/aws): puntos #6–#12, #18 y #19 de OBSERVACIONES-REVISION.md. Pruebas estáticas
sobre las plantillas de arranque y los .tf (sin red ni cuenta); el arranque se ejerce de verdad en el
simulacro de infra/aws/simulacro/."""
import glob
import os
import re
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INFRA = os.path.join(RAIZ, "infra", "aws")
SHA_1_9_1 = "7c686657021aba4041d6eede34808a08831b832534b151736a42c1022adda519"


def _leer(rel):
    with open(os.path.join(INFRA, rel), encoding="utf-8") as f:
        return f.read()


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
        self.assertRegex(v, r'variable "mdr_version"[^}]*default\s*=\s*"1\.9\.1"')
        self.assertIn(SHA_1_9_1, v)

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
            if os.path.isfile(f):
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
        net = _leer("network.tf")
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
        self.assertIn("aws_iam_instance_profile.gpu.name", _leer("llm.tf"))
        iam = _leer("iam.tf")
        gpu = iam[iam.index('resource "aws_iam_role" "gpu"'):]
        self.assertNotIn("secretsmanager", gpu.split('resource "aws_iam_instance_profile" "gpu"')[0])

    def test_sin_egreso_exige_s3_y_endpoint_de_secretos(self):   # I5
        mdr = _leer("mdr.tf")
        self.assertRegex(mdr, r'var\.egreso_bootstrap \|\| startswith\(local\.paquete_url, "s3://"\)')
        self.assertIn("var.egreso_bootstrap", _leer("llm.tf"))
        self.assertIn('"com.amazonaws.${var.region}.secretsmanager"', _leer("network.tf"))

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
        self.assertRegex(_leer("mdr.tf"), r'volumen\s*=\s*replace\(aws_ebs_volume\.traza\.id, "-", ""\)')


if __name__ == "__main__":
    unittest.main()
