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
            if os.path.isfile(f) and f.endswith((".tf", ".tftpl", ".sh", ".py", ".md", ".ejemplo")):
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
        for f in glob.glob(os.path.join(INFRA, "*.tf")):
            with open(f, encoding="utf-8") as g:
                declarados |= set(re.findall(r'^resource "([a-z0-9_]+)"', g.read(), re.M))
        inventariados = set()
        for f in glob.glob(os.path.join(INFRA, "inventario", "escenario-*.json")):
            with open(f, encoding="utf-8") as g:
                inventariados |= {r["tipo"] for r in json.load(g)["recursos"]}
        self.assertEqual(declarados - inventariados, set(), "recursos sin inventariar: regenera el inventario")
        with open(os.path.join(INFRA, "inventario", "README.md"), encoding="utf-8") as g:
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
        for doc in ("DESPLIEGUE.md", "README.md"):
            self.assertIsNone(re.search(r"tofu output (?!-raw)comando_", _leer(doc)), doc)

    def test_emulador_no_copia_el_backend_de_produccion(self):
        self.assertIn('rm -f "$d/backend.tf"', _leer("emulador/probar.sh"))

    def test_comprobar_no_da_verde_sin_el_arranque(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("comprobar", os.path.join(INFRA, "emulador", "comprobar.py"))
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
        for f in ("emulador/inventario.py", "inventario/README.md"):
            self.assertNotIn("solo primer arranque", _leer(f), f)
        self.assertIn("aunque no haya GPU", _leer("inventario/README.md"))

    def test_instantanea_de_la_traza_reproducible(self):
        d = _leer("DESPLIEGUE.md")
        self.assertRegex(d, r"create-snapshot --region")
        self.assertIn("tofu state show aws_ebs_volume.traza", d)
        self.assertIn("file://", d)                              # los tokens no van en la línea de órdenes
        self.assertIn("*.plan", _leer(".gitignore"))


class TestLaboratorio(unittest.TestCase):
    """Variante «laboratorio» (plan-aws-laboratorio.md): el banco, Wazuh y el MDR en una máquina."""
    T = "templates/laboratorio_user_data.sh.tftpl"
    MENSAJES = (
        "La variante laboratorio necesita egreso_bootstrap = true (descarga Docker, Containerlab y la imagen de Wazuh).",
        "La variante laboratorio necesita un MDR >= 1.9.2: la 1.9.1 no trae los arreglos del laboratorio.",
        "La variante laboratorio no lleva GPU (llm_habilitado = false).",
        "laboratorio_commit: los 40 caracteres hexadecimales del commit de la etiqueta v<mdr_version>.",
    )

    def test_variables_y_valores_por_defecto(self):
        v = _leer("variables.tf")
        self.assertRegex(v, r'variable "variante"[^}]*default\s*=\s*"mdr"')
        self.assertRegex(v, r'variable "variante"(.|\n)*?contains\(\["mdr", "laboratorio"\], var\.variante\)')
        self.assertRegex(v, r'variable "laboratorio_tipo"[^}]*default\s*=\s*"t3\.xlarge"')
        self.assertRegex(v, r'variable "laboratorio_disco_gb"[^}]*default\s*=\s*40\b')
        self.assertRegex(v, r'variable "laboratorio_commit"[^}]*default\s*=\s*""')

    def test_precondiciones(self):
        mdr = _leer("mdr.tf")
        for m in self.MENSAJES:
            self.assertIn(m, mdr)

    def test_arranque_del_laboratorio(self):
        t = _leer(self.T)
        self.assertIn("set -euo pipefail", t)
        self.assertNotIn("|| true", t)
        for s in ("--branch v${mdr_version}", "git rev-parse HEAD", "${laboratorio_commit}", "sha256sum -c",
                  "visor/dist", "0.79.0", "construir-imagen.sh", "systemctl enable --now mdr-laboratorio",
                  "/root/mdr-token-admin", "mdr-laboratorio.service"):
            self.assertIn(s, t)
        self.assertLess(t.index("git rev-parse HEAD"), t.index("construir-imagen.sh"))

    def test_mismo_disco_que_el_mdr(self):
        def bloque(texto):
            return texto[texto.index('DISCO=""'):texto.index('mountpoint -q "$ESTADO" || mount "$ESTADO"')]
        self.assertEqual(bloque(_leer(self.T)), bloque(_leer("templates/mdr_user_data.sh.tftpl")))

    def test_commit_distinto_para(self):
        t = _leer(self.T)
        i = t.index("git rev-parse HEAD")
        tramo = t[i:i + 400]
        self.assertIn("exit 1", tramo)
        self.assertNotIn("docker", t[t.index("git clone"):t.index("exit 1", i)])

    def test_costes_del_laboratorio(self):
        c = _leer("COSTES.md")
        self.assertIn("t3.xlarge", c)
        for uso in ("Encendido 24/7", "Parar y encender", "destroy"):
            self.assertIn(uso, c)
        self.assertIn("E · laboratorio", c)

    def test_guia_del_laboratorio(self):
        d = _leer("DESPLIEGUE.md")
        self.assertIn("## Variante laboratorio", d)
        s = d[d.index("## Variante laboratorio"):]
        for txt in ("no se conecta a ningún cliente", "stop-instances", "banco.sh atacar", "comprobar-alertas",
                    "journalctl -u mdr-laboratorio", "laboratorio_commit"):
            self.assertIn(txt.lower(), s.lower())


if __name__ == "__main__":
    unittest.main()
