# Corrección del despliegue en AWS — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Estado (17/11/2026): hecho** (commits `75dc63e`..HEAD). Alcance acordado con el usuario: los puntos de AWS de
> [`OBSERVACIONES-REVISION.md`](../../OBSERVACIONES-REVISION.md) (#6–#12, #18, #19), «por si se prueba
> en AWS». Sin `apply` real: no hay cuenta. Commits locales en `main`, sin push.

**Goal:** Que `tofu apply` en `infra/aws/` levante un MDR que funcione a la primera: la versión actual, instalada como en un cliente, con la traza firmada, la consola con token, la traza en su disco y, si se activa, el modelo de lenguaje con su embedder en GPU.

**Architecture:** El arranque de la instancia del MDR deja de clonar el repositorio: descarga el paquete del release (`mdr-<versión>.tar.gz`), comprueba su huella SHA-256 y ejecuta `instalar.sh`, que deja el código de root y en solo lectura y trae la consola compilada (#11, #18). El disco de la traza se monta en `/var/lib/mdr` antes de instalar, y el servicio exige ese montaje (#10). El arranque completa `/etc/mdr/triaje.env` (perfil, clave HMAC, un analista) y arranca el servicio (#19). La GPU se construye sobre una AMI con drivers NVIDIA, compila llama.cpp con CUDA y sirve el generador (8080) y bge-m3 (8082) (#8, #9), y `arrancar-mdr.sh` añade `--con-llm` cuando se pide (#6).

**Tech Stack:** OpenTofu ≥ 1.6, proveedor AWS ~> 5.60, bash (cloud-init en Amazon Linux 2023), sh POSIX (`deploy/`), Python 3 unittest.

**Spec:** [`OBSERVACIONES-REVISION.md`](../../OBSERVACIONES-REVISION.md), puntos 6–12, 18 y 19, y su anexo «simulacro de despliegue en AWS».

## Global Constraints

- El *runtime* del daemon no llama a Internet (RNF-01). El egreso es solo para el primer arranque (`egreso_bootstrap`) o vía el endpoint S3.
- Fail-closed: un paquete con otra huella, un disco que no aparece o un secreto indicado que no se puede leer **paran el arranque** (`exit 1`), nunca siguen en silencio.
- Nada de `|| true` en los arranques: un paso que falla, falla.
- Ningún secreto en la IaC ni en el estado de OpenTofu: solo ARNs.
- El motor de decisión no cambia: `evaluacion/tests` da las mismas cifras.
- Paquete por defecto: `v1.9.1`, `https://github.com/vBlanyer/domotai-pasantia/releases/download/v1.9.1/mdr-1.9.1.tar.gz`, SHA-256 `7c686657021aba4041d6eede34808a08831b832534b151736a42c1022adda519` (comprobado contra el asset publicado).
- llama.cpp fijado a una etiqueta (por defecto `b12445`), no a `master`.
- CI: `tofu fmt -check -recursive`, `tofu init -backend=false`, `tofu validate` deben seguir en verde.

## Review Focus

1. **Instancia reemplazada con el EBS de una traza anterior y sin `secreto_traza_arn`:** la clave HMAC nueva no verificaría la cadena vieja. El arranque debe avisar en el log y en `/etc/mdr/triaje.env` (comentario), no fallar en silencio. → `test_avisa_si_la_traza_existe_y_la_clave_es_nueva` (tarea 2).
2. **`secreto_traza_arn` o `secreto_operadores_arn` indicado pero ilegible** (sin permiso, ARN mal escrito): parar, no generar uno nuevo. → `test_secreto_indicado_ilegible_para` (tarea 2).
3. **Huella del paquete distinta** (asset sustituido o URL de otra versión): parar antes de `instalar.sh`. → simulacro (tarea 4) y `test_arranque_instala_el_paquete` (tarea 2).
4. **`llm_habilitado = true` sin URL ni huella de los modelos:** `tofu plan` debe fallar con un mensaje claro, no crear una GPU que no arranca. → `test_gpu_exige_modelos` (tarea 3).
5. **`$$(` en una plantilla:** `templatefile` solo escapa `$${`, así que `$$(seq 1 30)` llega a bash como el PID y rompe el bucle del disco (encontrado al planificar). → `test_plantillas_sin_doble_dolar_suelto` (tarea 2).

---

### Tarea 1: `--con-llm` desde el entorno (#6, común a AWS y al equipo local)

**Files:** Modify `deploy/arrancar-mdr.sh`, `deploy/triaje.env.ejemplo`; Test `prototipo/tests/test_despliegue_llm.py`

**Interfaces:** Produces: `TRIAJE_CON_LLM=1` en `triaje.env` ⇒ el daemon arranca con `--con-llm` (en los dos modos, `TRIAJE_ESCUCHAR` y `TRIAJE_ALERTS`). El modelo y el embedder se leen de `LLAMA_URL` y `LLAMA_EMBED_URL`, que ya existen en el código.

- [ ] Test `test_arrancar_con_llm`: ejecuta `deploy/arrancar-mdr.sh` con un `python3` falso al frente del `PATH` que anota sus argumentos, `TRIAJE_ESCUCHAR=127.0.0.1:0`, perfil, hallazgos y salida; con `TRIAJE_CON_LLM=1` los argumentos contienen `--con-llm`; sin la variable, no. Verlo fallar.
- [ ] Implementar (añadir `--con-llm` a los argumentos de los dos `python3 -m prototipo.servicio.stream`). Documentar en `triaje.env.ejemplo` el bloque comentado `LLAMA_URL`, `LLAMA_EMBED_URL`, `TRIAJE_CON_LLM`.
- [ ] Suite del prototipo; commit `fix(deploy): TRIAJE_CON_LLM arranca el daemon con el modelo de lenguaje (#6)`.

### Tarea 2: el arranque del MDR instala el paquete (#7, #10, #11, #12, #18, #19)

**Files:** Modify `infra/aws/templates/mdr_user_data.sh.tftpl` (reescritura), `infra/aws/variables.tf`, `infra/aws/mdr.tf`, `infra/aws/iam.tf`, `infra/aws/outputs.tf`; Test `prototipo/tests/test_infra_aws.py`

**Interfaces:**
- Variables nuevas: `mdr_version` (string, def. `"1.9.1"`), `mdr_paquete_url` (string, def. `""` ⇒ la URL del release de esa versión; admite `https://` y `s3://`), `mdr_paquete_sha256` (string, def. la huella de Global Constraints; validación: 64 hex), `perfil_url` (string, def. `""` ⇒ perfil mínimo), `red_cliente_cidrs` (list(string), def. `[]` ⇒ `[var.vpc_cidr]`), `secreto_traza_arn` y `secreto_operadores_arn` (string, def. `""`). Se eliminan `repo_url` y `repo_rama`.
- `iam.tf`: la política de lectura cubre `secretos_arns` ∪ los dos ARNs nuevos no vacíos.
- `mdr.tf`: `aws_volume_attachment.traza` con `stop_instance_before_detaching = true` (#12).
- `outputs.tf`: `comando_token_admin` = la sesión SSM y `sudo cat /root/mdr-token-admin`.

Orden del arranque (bash, `set -euo pipefail`, sin `|| true`):
1. `dnf install -y python3 python3-pyyaml tar openssl`.
2. Disco: esperar hasta 120 s a uno de `$${MDR_DISCOS:-/dev/nvme1n1 /dev/nvme2n1 /dev/sdf /dev/xvdf}`; si no aparece, `exit 1`. `mkfs.xfs` solo si no tiene sistema de ficheros; montarlo en `/var/lib/mdr` (fstab sin `nofail`).
3. Paquete: descargar (`curl -fsSL` o `aws s3 cp`), `sha256sum -c` con la huella, extraer y `./instalar.sh`.
4. Drop-in `/etc/systemd/system/mdr-triaje.service.d/traza.conf` con `RequiresMountsFor=/var/lib/mdr`.
5. Perfil: `perfil_url` (s3/https) a `/etc/mdr/perfil.yml`, o `python3 -m prototipo.herramientas.perfil_minimo --gestion <IP privada por IMDSv2> --rango <cidr>… --salida /etc/mdr/perfil.yml` desde `/opt/mdr`.
6. `triaje.env`: `TRIAJE_PERFIL=/etc/mdr/perfil.yml`, `TRIAJE_ALERTS=/var/lib/mdr/alerts.json` (creado, de `triaje`), `TRIAJE_TRAZA_CLAVE` (del secreto, o `openssl rand -hex 32` con aviso si ya hay una traza en el disco), operadores (del secreto, o `mdr analista alta admin` con el token en `/root/mdr-token-admin`, 0600) y, si hay `llm_url`, `LLAMA_URL`, `LLAMA_EMBED_URL` y `TRIAJE_CON_LLM=1`.
7. `systemctl daemon-reload && systemctl enable --now mdr-triaje`.

- [ ] Tests en `test_infra_aws.py` (estáticos, sin red): `test_arranque_instala_el_paquete` (contiene `instalar.sh` y `sha256sum -c`; no contiene `git clone` ni `chown -R triaje`), `test_version_actual` (sin `v1.4` en `variables.tf`; `mdr_version` = `1.9.1` y la huella de Global Constraints), `test_disco_obligatorio` (`RequiresMountsFor=/var/lib/mdr`, sin `nofail`, `exit 1` tras la espera), `test_traza_firmada_y_consola_con_token` (`TRAZA_CLAVE` y `analista alta`), `test_avisa_si_la_traza_existe_y_la_clave_es_nueva`, `test_secreto_indicado_ilegible_para`, `test_variables_del_modelo` (`LLAMA_URL`, `LLAMA_EMBED_URL`, `TRIAJE_CON_LLM`; sin `TRIAJE_LLM_URL`), `test_destroy_apaga_antes_de_desmontar`, `test_plantillas_sin_doble_dolar_suelto` (ninguna plantilla contiene `$$` que no vaya seguido de `{`). Verlos fallar.
- [ ] Implementar; `tofu fmt -check -recursive`, `tofu init -backend=false`, `tofu validate`.
- [ ] Commit `fix(aws): el arranque instala el paquete verificado, firma la traza y protege la consola (#7 #10 #11 #12 #18 #19)`.

### Tarea 3: la GPU arranca de verdad (#8, #9)

**Files:** Modify `infra/aws/templates/llm_user_data.sh.tftpl` (reescritura), `infra/aws/llm.tf`, `infra/aws/network.tf`, `infra/aws/variables.tf`, `infra/aws/mdr.tf` (`local.llm_url`, `llm_embed_url`); Test `prototipo/tests/test_infra_aws.py`

**Interfaces:** Variables: `llm_modelo_url`, `llm_modelo_sha256`, `embed_modelo_url`, `embed_modelo_sha256` (string, def. `""`), `llama_cpp_ref` (def. `"b12445"`). `aws_instance.llm` con `lifecycle { precondition }`: con `llm_habilitado` las cuatro de modelo son obligatorias. AMI: `Deep Learning Base OSS Nvidia Driver GPU AMI (Amazon Linux 2023)*` de `amazon`. SG `llm`: entrada 8080 y 8082 solo desde el SG del MDR. El MDR recibe `llm_url = http://<ip>:8080` y `llm_embed_url = http://<ip>:8082`.

Arranque: `dnf install -y git cmake gcc-c++`; `git clone --branch <ref> --depth 1` de llama.cpp; `cmake -B build -DGGML_CUDA=ON && cmake --build build -j --target llama-server`; descargar los dos modelos y comprobar su huella; dos unidades `llama-gen.service` (`-m generador.gguf --host 0.0.0.0 --port 8080 -ngl 99`) y `llama-embed.service` (`-m bge-m3.gguf --embedding --pooling cls --host 0.0.0.0 --port 8082`), `enable --now`.

- [ ] Tests: `test_gpu_sin_fallos_silenciosos` (sin `|| true`; `GGML_CUDA=ON`; `--port 8080` y `--port 8082`; `--pooling cls`; `sha256sum -c`), `test_gpu_exige_modelos` (la precondición nombra las cuatro variables), `test_sg_embedder` (`network.tf` abre 8082 desde el SG del MDR). Verlos fallar.
- [ ] Implementar; `tofu validate`. La compilación con CUDA no se puede probar sin GPU: se anota en el README como no probado.
- [ ] Commit `fix(aws): la GPU compila llama.cpp con CUDA y sirve el modelo y el embedder del RAG (#8 #9)`.

### Tarea 4: simulacro del arranque en `amazonlinux:2023`

**Files:** Create `infra/aws/simulacro/simulacro.sh`

`simulacro.sh` renderiza la plantilla del MDR con `tofu console` (`templatefile(...)` con valores de prueba: paquete `file://` de `dist/`, su huella, sin secretos, sin modelo), y la ejecuta en `docker run --privileged amazonlinux:2023` con un disco de bucle (`losetup`) pasado por `MDR_DISCOS`, y `systemctl` y `aws` falsos que anotan lo que se les pide. Comprueba: instalación en `/opt/mdr` de root, `triaje.env` con `TRAZA_CLAVE` y operadores, `/root/mdr-token-admin` 0600, perfil mínimo escrito, `/var/lib/mdr` montado, el drop-in, `enable --now mdr-triaje`. Segundo caso: sin disco ⇒ código de salida ≠ 0. Tercer caso: huella cambiada ⇒ ≠ 0 y nada instalado.

- [ ] Escribir y ejecutar los tres casos; corregir lo que salga (cada corrección con su test estático en la tarea que toque).
- [ ] Commit `test(aws): simulacro del arranque del MDR en amazonlinux:2023`.

### Tarea 5: documentación

- [ ] `infra/aws/README.md`: instalación por paquete, variables nuevas, cómo crear los dos secretos, cómo leer el token, simulacro, y lo no probado (GPU con CUDA, `apply` real).
- [ ] `OBSERVACIONES-REVISION.md` (estado de #6–#12, #18, #19), `CHANGELOG.md` ([Sin publicar]), manual de producción si menciona AWS.
- [ ] Commit `docs: despliegue en AWS corregido`.

## Fuera de este plan

El `apply` real (no hay cuenta), el backend `s3` del estado de OpenTofu, una AMI horneada para desplegar sin egreso, y el endurecimiento de la unidad systemd (#20).
