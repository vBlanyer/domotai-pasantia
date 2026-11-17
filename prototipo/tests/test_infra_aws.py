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

    def test_version_actual(self):
        v = _leer("variables.tf")
        self.assertNotIn("v1.4", v)                          # #7
        self.assertNotIn("repo_rama", v)
        self.assertRegex(v, r'variable "mdr_version"[^}]*default\s*=\s*"1\.9\.1"')
        self.assertIn(SHA_1_9_1, v)

    def test_disco_obligatorio(self):
        t = _leer(self.T)
        self.assertIn("RequiresMountsFor=/var/lib/mdr", t)   # #10
        self.assertNotIn("nofail", t)
        self.assertRegex(t, r"if \[ -z \"\$DISCO\" \]; then[^}]*?exit 1")

    def test_traza_firmada_y_consola_con_token(self):
        t = _leer(self.T)                                    # #19
        self.assertIn("TRIAJE_TRAZA_CLAVE", t)
        self.assertIn("analista alta admin", t)
        self.assertIn("/root/mdr-token-admin", t)
        self.assertIn("systemctl enable --now mdr-triaje", t)

    def test_avisa_si_la_traza_existe_y_la_clave_es_nueva(self):
        t = _leer(self.T)
        self.assertRegex(t, r"-s \"\$ESTADO/trazas-cliente\.jsonl\"[^\n]*\n[^\n]*AVISO")

    def test_secreto_indicado_ilegible_para(self):
        t = _leer(self.T)
        self.assertIn("set -euo pipefail", t)
        self.assertNotIn("|| true", t)
        self.assertRegex(t, r"=\$\(aws secretsmanager get-secret-value")   # un fallo para el arranque

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


if __name__ == "__main__":
    unittest.main()
