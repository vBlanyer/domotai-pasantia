# Probar el despliegue de AWS contra AWS Emulator — plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Estado (17/11/2026): propuesto, pendiente de aprobación.** Sin cuenta de AWS ni coste. Commits
> locales en `main`, sin push.

**Goal:** Ejecutar `tofu plan`, `apply` y `destroy` de `infra/aws/` contra **AWS Emulator** (un emulador local de la API de AWS) para comprobar lo que hoy nadie ha probado: que el **grafo de recursos** se crea entero y en orden, y que las precondiciones y los `count` se comportan como dice el código. Y dejar listo lo que necesita el **despliegue oficial**: el inventario de lo que se crea (JSON), la estimación de costes, la plantilla de variables de producción, el estado remoto y la guía paso a paso con las cuotas.

**Entregables para producción:** el código de `infra/aws/` (ya existe; es lo que se aplica), más
`produccion.tfvars.ejemplo`, `backend.tf.ejemplo`, `inventario/*.json`, `COSTES.md` y `DESPLIEGUE.md`.
Lo que crea el emulador (estado, identificadores) no sirve para producción y se descarta.

**Architecture:** Tres capas de prueba, cada una con lo suyo. (1) `tofu validate` y las pruebas estáticas: sintaxis y contenido (hecho). (2) El simulacro en `amazonlinux:2023`: el **script de arranque** de verdad (hecho). (3) **Nuevo:** el emulador: la **API de control** de AWS (crear VPC, roles, instancias, discos, endpoints) con el mismo `infra/aws/` sin modificar. Un guion lanza el emulador, apunta OpenTofu a él con un fichero `override` que **solo vive en una copia temporal**, y recorre cuatro escenarios.

**Tech Stack:** AWS Emulator (paquete `.deb`, `127.0.0.1:9297`, HTTPS con su propia CA), OpenTofu, AWS CLI v2 (≥ 2.35), sh.

**Spec:** la conversación del 17/11 y la documentación del emulador:
`what-is-service.html`, `fidelity.html`, `point-sdk-to-emulator.html`, `setting-up.html`
(https://docs.aws.amazon.com/emulator/latest/userguide/).

## Global Constraints

- **No es 1:1 con AWS** y el informe del resultado lo dirá así (ver «Qué no prueba»).
- `infra/aws/*.tf` no se toca para acomodar al emulador: los ajustes (endpoints, AMI) van en un `override.tf` generado en una copia temporal. Si un fallo es del código y no del emulador, se arregla en `infra/aws/` con su prueba.
- Telemetría del emulador **desactivada** (`--telemetry off`): no sale nada de este equipo.
- La instalación del emulador (y la actualización de AWS CLI) necesita `sudo`: la hace el usuario.
- Credenciales reales de AWS fuera del entorno durante la prueba (`unset AWS_PROFILE …`).
- Región del emulador: una sola; se usa `us-west-2`, la que AWS verifica.

## Review Focus

1. **Operación no implementada (HTTP 501 `NotImplemented`):** distinguir «el emulador no la tiene» de «nuestro código está mal»; nunca «arreglar» el código para esquivar al emulador.
2. **La búsqueda de AMIs** (`data "aws_ami"` por nombre y dueño `amazon`) probablemente no devuelve nada en un emulador vacío: se sustituye por una AMI de prueba en el `override`, y se anota que esa búsqueda **no** queda probada.
3. **Precondiciones:** el escenario «GPU con 1.9.1» debe fallar en `plan` con el mensaje esperado, no crear nada.
4. **Restos:** el emulador es en memoria; el guion lo para siempre al salir y no deja estado de OpenTofu en el repositorio.
5. **Las políticas IAM no se evalúan** en el emulador: comprobar que la GPU *no tiene* la política de secretos se hace leyendo sus políticas, no intentando leer un secreto.

---

### Tarea 0 (usuario): instalar el emulador

```sh
curl -fsSLo aws-emulator.deb https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest/aws-emulator_amd64.deb
sudo apt-get install -y ./aws-emulator.deb
aws-emulator -v
aws --version          # ≥ 2.35.0; si no, actualizar AWS CLI v2
```

Requisitos: Linux de 64 bits, glibc ≥ 2.17. WSL2 no aparece en la documentación: se comprueba en la tarea 1.

### Tarea 1: arrancar y conectar

**Files:** Create `infra/aws/emulador/probar.sh`

- [ ] Arrancar `aws-emulator --telemetry off --idle-timeout 900` en segundo plano; esperar a `curl --cacert ~/.aws/emulator/9297/ca.pem https://127.0.0.1:9297/__admin/health`.
- [ ] Copiar `infra/aws/*.tf` y `templates/` a una carpeta temporal y generar en ella `override.tf`: proveedor con `shared_credentials_files` = `~/.aws/emulator/9297/emulator_credentials`, `custom_ca_bundle` = su `ca.pem` y un bloque `endpoints` (ec2, iam, sts, s3, secretsmanager, ssm) a `https://127.0.0.1:9297`; `AWS_CONFIG_FILE=/dev/null` y `AWS_EC2_METADATA_DISABLED=true` en el entorno. **Comprobado el 17/11** con una prueba mínima (VPC, subred y rol IAM: `apply` y `destroy` correctos, cuenta `000000000000`). Más la AMI de prueba en lugar de la búsqueda.
- [ ] Las comprobaciones del `user_data` y de las políticas del rol de la GPU se hacen con la AWS CLI v2 instalada en `~/.local` (sin `sudo`) o, si no, con fuentes de datos de OpenTofu (`data "aws_instance"`, `data "aws_iam_role_policies"`) en el `override`.
- [ ] Al salir (trap): `tofu destroy`, parar el emulador y borrar la carpeta temporal.

### Tarea 2: cuatro escenarios

| # | Variables | Qué se espera |
|---|---|---|
| A | `egreso_bootstrap=true` (paquete por defecto de GitHub) | `apply` crea VPC, subredes, IGW, NAT, SGs, endpoints de SSM y S3, rol e instancia del MDR, EBS y su enganche; `destroy` lo quita todo |
| B | `egreso_bootstrap=false`, paquete `s3://`, los dos secretos | además el endpoint de Secrets Manager y las políticas de secretos y de S3; sin NAT |
| C | `llm_habilitado=true` con `mdr_version=1.9.1` | `plan` falla con «El paquete 1.9.1 no activa el modelo…»; no se crea nada |
| D | `llm_habilitado=true`, `mdr_version=1.9.2` (ficticia), modelos `s3://` con huellas | además la GPU con **su** rol (sin política de secretos) y el SG con 8080 y 8082 |

- [ ] En A y B, leer el `user_data` de la instancia del MDR desde el emulador (`aws ec2 describe-instance-attribute --attribute userData`), decodificarlo y pasarle `bash -n`; comprobar que lleva el id del EBS (`nvme-Amazon_Elastic_Block_Store_vol…`).
- [ ] En D, `aws iam list-role-policies` del rol de la GPU no incluye `leer-secretos`.
- [ ] Cada fallo se clasifica: **del emulador** (501, operación ausente) → se anota; **de nuestro código** → se arregla en `infra/aws/` con su prueba estática, y se repite.

### Tarea 3: inventario de lo que se crea (JSON)

**Files:** Create `infra/aws/inventario/escenario-{a,b,d}.json` y `infra/aws/inventario/README.md`

- [ ] Por cada escenario que aplica (A, B, D): `tofu plan -out` contra el emulador y `tofu show -json` filtrado a lo que sirve para revisar: por recurso, `address`, `type` y la configuración que importa (tipo de instancia, tamaño y cifrado de discos, puertos de los SG, acciones de las políticas IAM, servicios de los endpoints). Sin identificadores del emulador ni el `user_data` (se resume como «plantilla de arranque, N líneas»).
- [ ] `inventario/README.md`: la misma lista como tabla legible, por escenario, con una línea de «por qué existe» por recurso.
- [ ] Prueba `test_inventario_al_dia`: los tipos de recurso del inventario coinciden con los `resource` de los `.tf` (un recurso nuevo sin inventariar falla).

### Tarea 4: estimación de costes

**Files:** Create `infra/aws/COSTES.md`

- [ ] Por cada recurso del inventario que se cobra (instancias, EBS, NAT y su IP, endpoints de interfaz, Secrets Manager, GPU), el precio **oficial actual** de la región por defecto (`eu-west-1`) y de `us-east-1`, consultado en las páginas de precios de AWS o su API pública de precios **el día de hacerlo**, con fecha y fuente. Nunca de memoria.
- [ ] Tabla por escenario: solo MDR con egreso, solo MDR sin egreso, MDR + GPU; coste por hora, por día de prueba (8 h y 24 h) y por mes. Y lo que se paga aunque esté apagado (discos, secretos, IP).
- [ ] Una línea de comparación con el equipo local de ~3000 $ (cuántos días de GPU en AWS equivalen), marcada como orientativa.

### Tarea 5: plantilla de variables de producción

**Files:** Create `infra/aws/produccion.tfvars.ejemplo`, `infra/aws/backend.tf.ejemplo`

- [ ] `produccion.tfvars.ejemplo`: **todas** las variables de `variables.tf`, cada una con su valor de ejemplo o `<rellenar>` y un comentario de una línea; agrupadas (región y red, versión y paquete, perfil, secretos, GPU).
- [ ] `backend.tf.ejemplo`: el estado de OpenTofu en S3 con bloqueo, para producción (hoy es local).
- [ ] Prueba `test_tfvars_cubre_las_variables`: cada `variable` de `variables.tf` aparece en la plantilla. Y `tofu validate` con la plantilla copiada a `.tfvars` (valores de ejemplo válidos).

### Tarea 6: cuotas y guía de despliegue en producción

**Files:** Create `infra/aws/DESPLIEGUE.md`

- [ ] **Cuotas** a revisar en la cuenta real antes del primer `apply`, con el comando exacto (`aws service-quotas get-service-quota …`) y lo mínimo que hace falta: vCPU de instancias G (la GPU; en cuentas nuevas suele ser 0 y la ampliación tarda), vCPU estándar, IP elásticas, VPC y endpoints de interfaz por VPC.
- [ ] **Pasos en orden:** cuotas → secretos en Secrets Manager → paquete (y perfil) a S3 con su huella → estado en S3 (`backend.tf`) → `produccion.tfvars` → `tofu plan` (revisar contra el inventario) → `apply` → leer el token y abrir el túnel → comprobar `/healthz` y la consola → cómo apagar (`destroy`) y qué queda cobrándose.
- [ ] Enlaces a `COSTES.md`, `inventario/` y a la lista de «Qué no prueba» de este plan.

### Tarea 7: documentar

- [ ] `infra/aws/README.md`: la tabla de las tres capas (qué prueba cada una), cómo ejecutar `probar.sh`, el resultado de los escenarios, **qué no prueba** el emulador y los enlaces a `DESPLIEGUE.md`, `COSTES.md`, `inventario/` y la plantilla de variables.
- [ ] `CHANGELOG.md` ([Sin publicar]).
- [ ] Commits: `test(aws): plan, apply y destroy contra AWS Emulator`, `docs(aws): inventario, costes, plantilla de variables y guía de despliegue`.

## Qué no prueba (ni el emulador ni el simulacro): solo un despliegue real

- Que la **búsqueda de la AMI** encuentre Amazon Linux 2023 y la Deep Learning AMI en la región elegida.
- La **evaluación real de IAM** (el emulador no evalúa políticas) y su retraso de propagación.
- El **arranque en una instancia Nitro de verdad**: nombres de dispositivo NVMe, cloud-init, systemd real.
- **Red real**: que `dnf` llegue a los repositorios sin egreso, el DNS privado de los endpoints, el túnel SSM.
- La **GPU**: drivers, CUDA, la compilación de llama.cpp y la memoria.
- **Cuotas y costes** de la cuenta.
