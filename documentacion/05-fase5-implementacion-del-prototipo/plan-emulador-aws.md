# Probar el despliegue de AWS contra AWS Emulator — plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Estado (17/11/2026): propuesto, pendiente de aprobación.** Sin cuenta de AWS ni coste. Commits
> locales en `main`, sin push.

**Goal:** Ejecutar `tofu plan`, `apply` y `destroy` de `infra/aws/` contra **AWS Emulator** (un emulador local de la API de AWS) para comprobar lo que hoy nadie ha probado: que el **grafo de recursos** se crea entero y en orden, y que las precondiciones y los `count` se comportan como dice el código.

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

- [ ] Arrancar `aws-emulator --telemetry off --idle-timeout 900` en segundo plano; esperar a `curl --cacert ~/.aws/emulator/9297/ca.pem https://127.0.0.1:9297/__admin/health`; `aws sts get-caller-identity` debe dar la cuenta `000000000000`.
- [ ] Copiar `infra/aws/*.tf` y `templates/` a una carpeta temporal y generar en ella `override.tf`: proveedor con `endpoints` de los servicios usados (ec2, iam, sts, s3, secretsmanager, ssm), `custom_ca_bundle` con el `ca.pem` del emulador, `skip_credentials_validation`/`skip_requesting_account_id` si hicieran falta, y la AMI de prueba en lugar de la búsqueda.
- [ ] Comprobar si el proveedor de OpenTofu también acepta `AWS_ENDPOINT_URL`; si sí, usarlo y simplificar el `override`. Anotar lo que funcionó.
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

### Tarea 3: documentar

- [ ] `infra/aws/README.md`: la tabla de las tres capas (qué prueba cada una), cómo ejecutar `probar.sh`, el resultado de los escenarios y **qué no prueba** el emulador.
- [ ] Commit `test(aws): plan, apply y destroy contra AWS Emulator`.

## Qué no prueba (ni el emulador ni el simulacro): solo un despliegue real

- Que la **búsqueda de la AMI** encuentre Amazon Linux 2023 y la Deep Learning AMI en la región elegida.
- La **evaluación real de IAM** (el emulador no evalúa políticas) y su retraso de propagación.
- El **arranque en una instancia Nitro de verdad**: nombres de dispositivo NVMe, cloud-init, systemd real.
- **Red real**: que `dnf` llegue a los repositorios sin egreso, el DNS privado de los endpoints, el túnel SSM.
- La **GPU**: drivers, CUDA, la compilación de llama.cpp y la memoria.
- **Cuotas y costes** de la cuenta.
