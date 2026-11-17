# Despliegue oficial del MDR en AWS

Guía paso a paso para el **primer despliegue en la cuenta de la empresa**. Antes de empezar, revisa qué
se va a crear ([inventario/](inventario/)) y cuánto cuesta ([COSTES.md](COSTES.md)). Lo que ninguna
prueba local ha podido comprobar está al final, en «Qué se comprueba por primera vez».

Necesitas: OpenTofu ≥ 1.10, AWS CLI v2, acceso a la cuenta con permisos para crear VPC, EC2, IAM, S3 y
Secrets Manager, y el plugin de Session Manager para la AWS CLI (para el túnel a la consola).

## 0. Cuotas de la cuenta

Compruébalas **antes** del primer `apply`: una ampliación de cuota puede tardar días.

| Cuota | Código | Mínimo necesario |
|---|---|---|
| Instancias bajo demanda estándar (vCPU) | `ec2` · `L-1216C47A` | 2 (MDR `t3.small`); 4 con la variante laboratorio (`t3.xlarge`) |
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
aws s3 cp mdr-1.9.1.tar.gz s3://<bucket-artefactos>/          # del release de GitHub
sha256sum mdr-1.9.1.tar.gz                                     # → mdr_paquete_sha256
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
cd infra/aws
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

## Variante laboratorio (entorno de pruebas de la empresa)

Con `variante = "laboratorio"` la misma instancia levanta **el laboratorio del banco** (15 equipos en
Containerlab), **su Wazuh** y **el MDR**, como en local, para probar el MDR antes de ponerlo delante de un
cliente. **No se conecta a ningún cliente**: los ataques, las alertas y las contenciones ocurren dentro de
la máquina. Qué se crea: escenario E del [inventario](inventario/); coste: [COSTES.md](COSTES.md) (E).

Requisitos, además de los pasos 0 y 3:

- un MDR **≥ 1.9.2** publicado (la 1.9.1 no trae los arreglos del laboratorio; `tofu plan` lo rechaza);
- `laboratorio_commit`, el commit de su etiqueta: `git rev-parse v1.9.2^{commit}` en el repositorio. El
  arranque clona la etiqueta y **se para** si el commit no es ese;
- 4 vCPU de cuota estándar (`t3.xlarge`) y `egreso_bootstrap = true` (descarga Docker, Containerlab y
  la imagen de Wazuh). Sin GPU.

En `produccion.tfvars` (o un `laboratorio.tfvars` aparte): `variante = "laboratorio"`,
`egreso_bootstrap = true`, `mdr_version = "1.9.2"`, `mdr_paquete_sha256` del paquete, `mdr_paquete_url = ""`
(el release de GitHub) y `laboratorio_commit`. Los secretos son opcionales, como en la variante MDR.

```sh
tofu plan  -var-file=laboratorio.tfvars -out laboratorio.plan     # compáralo con el escenario E
tofu apply laboratorio.plan
```

**Esperar a que esté listo.** El arranque instala lo necesario y deja en marcha la unidad
`mdr-laboratorio`, que levanta el banco, aprovisiona el conector, comprueba que todo está sano y que Wazuh
genera alertas (`banco.sh test` y `banco.sh comprobar-alertas`) y arranca el MDR. Tarda unos minutos:

```sh
aws ssm start-session --region <region> --target "$(tofu output -raw mdr_instance_id)"
sudo journalctl -u mdr-laboratorio -f        # listo cuando aparece «MDR en marcha»
```

**Entrar a la consola**: igual que en el paso 6 (`tofu output -raw comando_tunel_visor` y el token).

**Atacar y observar** (en la sesión SSM, como root, desde `/opt/mdr-laboratorio`):

```sh
sudo -i
cd /opt/mdr-laboratorio
sh lab/banco/banco.sh atacar             # menú de ataques de las 10 familias
sh lab/banco/banco.sh atacar continuo    # ataques variados sin fin (Ctrl+C para parar)
sh lab/banco/banco.sh vigilar            # servicios en verde/rojo
sh lab/banco/banco.sh restaurar          # deja el banco sano tras una prueba
sh lab/banco/banco.sh comprobar-alertas  # Wazuh sigue generando alertas
```

**Parar y encender** para ahorrar (el disco de la traza se conserva y la cadena continúa):

```sh
aws ec2 stop-instances  --region <region> --instance-ids "$(tofu output -raw mdr_instance_id)"
aws ec2 start-instances --region <region> --instance-ids "$(tofu output -raw mdr_instance_id)"
```

Al encender, `mdr-laboratorio` rehace el laboratorio desde cero (la red de Containerlab y Wazuh no
sobreviven a un reinicio) antes de arrancar el MDR: unos minutos. Las contenciones de la sesión anterior
ya no existen (los equipos se recrean), así que se anotan como revertidas en la traza: el MDR vuelve a
decidir los ataques repetidos y la consola no las lista como activas. Si algo falla, la unidad lo
reintenta (cada 30 s, hasta 5 veces en 2 h) y el motivo queda en `journalctl -u mdr-laboratorio`.

**En la instancia, no uses `reiniciar.sh`, `lab.sh up`/`down` ni `banco.sh down`**: el servicio ya
gestiona el laboratorio y el daemon, y esas órdenes lo cortan a medias. Para reiniciarlo todo:
`sudo systemctl restart mdr-laboratorio`.

**Apagar del todo**: `tofu destroy -var-file=laboratorio.tfvars`, como en el paso 7.

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
