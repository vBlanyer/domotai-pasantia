# Despliegue oficial del MDR en AWS (producción)

Guía paso a paso para el **primer despliegue en la cuenta de la empresa** de la variante de producción
(`infra/aws/mdr/`; la guía corta para empezar es [../INSTALAR.md](../INSTALAR.md)). Antes de empezar,
revisa qué se va a crear ([inventario/](inventario/)) y cuánto cuesta ([COSTES.md](COSTES.md)). Lo que ninguna
prueba local ha podido comprobar está al final, en «Qué se comprueba por primera vez».

Necesitas: OpenTofu ≥ 1.10, AWS CLI v2, acceso a la cuenta con permisos para crear VPC, EC2, IAM, S3 y
Secrets Manager, y el plugin de Session Manager para la AWS CLI (para el túnel a la consola).

## 0. Cuotas de la cuenta

Compruébalas **antes** del primer `apply`: una ampliación de cuota puede tardar días.

| Cuota | Código | Mínimo necesario |
|---|---|---|
| Instancias bajo demanda estándar (vCPU) | `ec2` · `L-1216C47A` | 2 (MDR `t3.small`) |
| Instancias bajo demanda G y VT (vCPU) — solo con GPU | `ec2` · `L-DB2E81BA` | 4 (`g4dn.xlarge`). **En cuentas nuevas suele ser 0** |
| IP elásticas — solo con `egreso_bootstrap` | `ec2` · `L-0263D0A3` | 1 |
| VPC por región | `vpc` · `L-F678F1CE` | 1 libre |
| Endpoints de interfaz por VPC | `vpc` · `L-29B6F2EB` | 4 (3 de SSM + Secrets Manager) |

```sh
aws service-quotas get-service-quota --region <region> --service-code ec2 --quota-code L-DB2E81BA \
    --query 'Quota.Value'
# Pedir más (p. ej. 4 vCPU de GPU):
aws service-quotas request-service-quota-increase --region <region> --service-code ec2 \
    --quota-code L-DB2E81BA --desired-value 4
```

Comprueba los códigos en la consola de *Service Quotas* si AWS los cambia.

## 1. Paquete y perfil en S3

```sh
aws s3 mb s3://<bucket-artefactos> --region <region>
aws s3 cp mdr-1.9.2.tar.gz s3://<bucket-artefactos>/          # del release de GitHub
sha256sum mdr-1.9.2.tar.gz                                     # → mdr_paquete_sha256
aws s3 cp perfil.yml s3://<bucket-artefactos>/                 # el perfil del cliente (opcional)
```

Con GPU, sube también los dos modelos (`.gguf` del generador y de bge-m3) y anota sus `sha256sum`.
**La GPU necesita un MDR ≥ 1.9.2** (la 1.9.1 no activa el modelo; `tofu plan` lo rechaza).

## 2. Secretos

```sh
umask 077
openssl rand -hex 32 > traza-clave.txt
printf '{"%s":"ana"}' "$(openssl rand -hex 24)" > operadores.json   # un token por analista
aws secretsmanager create-secret --region <region> --name mdr/traza-clave \
    --secret-string file://traza-clave.txt
aws secretsmanager create-secret --region <region> --name mdr/operadores \
    --secret-string file://operadores.json
```

Los valores van por fichero (`file://`) para que no queden en el historial del shell. Entrega a cada
analista su token por un canal seguro y borra los ficheros (`shred -u traza-clave.txt operadores.json`).

Anota los **ARN completos** que devuelven. La clave de la traza no debe perderse nunca: sin ella la
traza firmada deja de poder verificarse. Si cifras los secretos con una clave KMS propia, el rol del MDR
necesita también `kms:Decrypt` sobre ella.

## 3. Estado de OpenTofu en S3

Copia `backend.tf.ejemplo` a `backend.tf`, crea el bucket del estado como dice el fichero (con
versionado y sin acceso público) y rellena su nombre y región.

## 4. Variables

Copia `produccion.tfvars.ejemplo` a `produccion.tfvars` (git lo ignora) y rellena los `<rellenar>`:
región, URLs de S3 y su huella, y los dos ARN.

## 5. Plan y apply

```sh
cd infra/aws/mdr
tofu init
tofu plan  -var-file=produccion.tfvars -out despliegue.plan
```

Revisa el plan contra el [inventario](inventario/) del escenario que corresponda (sin egreso y con
secretos = escenario B). Si cuadra:

```sh
tofu apply despliegue.plan
```

El arranque de la instancia tarda unos minutos (instala paquetes y el MDR). Su registro queda en
`/var/log/mdr-arranque.log`.

## 6. Entrar a la consola

```sh
tofu output -raw comando_tunel_visor   # imprime la orden del túnel SSM a http://127.0.0.1:8787
```

Abre la consola y entra con el token de un analista (el que pusiste en `mdr/operadores`; sin ese secreto,
`tofu output -raw comando_token_admin` dice cómo leer el del admin). Comprueba:

- `/healthz` responde y el Panel muestra la plataforma operativa;
- Trazas: «Cadena íntegra»;
- en la instancia (`aws ssm start-session …`): `sudo mdr estado`.

Para que lleguen alertas, el SIEM del cliente escribe en `/var/lib/mdr/alerts.json` o envía por red al
receptor del daemon (`TRIAJE_ESCUCHAR`; ver el manual de producción).

## 7. Apagar

```sh
tofu destroy -var-file=produccion.tfvars
```

`destroy` apaga la instancia antes de soltar el disco de la traza (no hace falta hacerlo a mano).
**El disco de la traza se borra con `destroy`**: haz antes una instantánea si hay que conservar la
evidencia:

```sh
tofu state show aws_ebs_volume.traza | grep ' id '      # el id del disco (vol-…)
aws ec2 create-snapshot --region <region> --volume-id <vol-…> --description "traza MDR"
```
 Lo que sigue cobrándose después
de `destroy`: los secretos, los buckets de S3 (artefactos y estado) y las instantáneas que hagas.

## Qué se comprueba por primera vez en el despliegue real

Las pruebas locales (`tofu validate`, pruebas estáticas, simulacro del arranque en `amazonlinux:2023` y
`plan`/`apply`/`destroy` contra AWS Emulator) no pueden comprobar:

- que la región tenga Amazon Linux 2023 y, con GPU, la Deep Learning AMI;
- la evaluación real de IAM (el emulador no evalúa políticas) y su retraso de propagación (el arranque
  reintenta);
- el arranque en una instancia Nitro real (nombres NVMe, cloud-init, systemd);
- la red real: `dnf` sin egreso a través del endpoint de S3, el DNS privado de los endpoints, el túnel SSM;
- la GPU: drivers, CUDA, la compilación de llama.cpp y la memoria;
- las cuotas y el coste reales.

Si el primer arranque falla, el motivo está en `/var/log/mdr-arranque.log` (o
`/var/log/llm-arranque.log` en la GPU); el arranque solo se ejecuta una vez por instancia, así que tras
corregir hay que recrearla (`tofu apply -replace=aws_instance.mdr …`).
