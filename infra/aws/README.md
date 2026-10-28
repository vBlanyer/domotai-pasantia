# infra/aws — IaC del despliegue (OpenTofu)

Infraestructura para correr el **MDR (daemon + visor)** y, opcional, el **LLM justificador en GPU** en
AWS. Implementa el plano de
[despliegue-aws-opentofu.md](../../documentacion/04-fase4-diseno-de-arquitectura/despliegue-aws-opentofu.md).
Briefing para la reunión con el tutor industrial:
[briefing-reunion-despliegue-aws.md](../../documentacion/04-fase4-diseno-de-arquitectura/briefing-reunion-despliegue-aws.md).

> **Estado:** IaC escrita (fase 1). **Pendiente de `tofu validate`**: el entorno de desarrollo no dejó
> instalar OpenTofu, así que la validación no se ha ejecutado aún. Ejecútala con los pasos de abajo.
> **No hacer `apply` en una cuenta real** sin acordar alcance/coste con el tutor industrial (la GPU del
> LLM es el grueso del coste; por eso `llm_habilitado = false` por defecto).

## Qué crea
- VPC con **subred privada** (sin IP pública), SG mínimos y **endpoints VPC** (SSM + S3): nada expuesto
  a Internet. El acceso del analista es por **SSM** (túnel), no por un puerto abierto.

> **Runtime vs bootstrap (importante):** el *runtime* del daemon no llama a Internet (RNF-01, propiedad
> del producto). Pero el *primer arranque* (dnf, git clone, descarga del modelo) **sí necesita egreso**.
> Por eso `egreso_bootstrap` (def. `false`): con `true` se crea IGW + subred pública + NAT para ese
> arranque; con `false` hay que desplegar desde una **AMI horneada** (repo+deps+modelo ya dentro) o
> **artefactos en S3** (el `git clone`/`curl` del cloud-init no funcionará sin egreso).
- EC2 **MDR** (daemon + visor, `systemd` de `deploy/`) + **EBS cifrado** para la traza (`--salida` fija).
- EC2 **GPU** con el LLM justificador — **solo si `llm_habilitado = true`** (`count` en `llm.tf`).
- Rol IAM mínimo (SSM + lectura de los secretos que se indiquen). Secretos y pesos del modelo: fuera del
  código (Secrets Manager); aquí solo el permiso de lectura.

## Validación offline (sin cuenta AWS, sin coste)
```sh
# 1. Instalar OpenTofu (binario único): https://opentofu.org/docs/intro/install/
tofu init
tofu fmt -check
tofu validate                      # correctitud de la configuración contra el esquema del proveedor

# 2. (Opcional) plan simulado contra LocalStack (AWS de mentira sobre Docker):
docker run -d -p 4566:4566 localstack/localstack
pip install terraform-local        # da el wrapper `tflocal` (o fija endpoints del proveedor a mano)
tflocal init && tflocal plan        # apply simulado de lo soportado (VPC/EC2/IAM/SG)
```

## Aplicar de verdad (fase 2 — con la cuenta de la empresa)
```sh
export AWS_PROFILE=<perfil-de-la-empresa>        # credenciales del tutor industrial
# egreso_bootstrap=true permite que el primer arranque instale deps y clone el repo (crea NAT):
tofu plan  -var 'region=<region>' -var 'llm_habilitado=false' -var 'egreso_bootstrap=true'
tofu apply -var 'region=<region>' -var 'llm_habilitado=false' -var 'egreso_bootstrap=true'
tofu output comando_tunel_visor                  # abre el visor por SSM en 127.0.0.1:8787
# Para incluir el LLM (coste GPU): -var 'llm_habilitado=true' -var 'llm_tipo=g4dn.xlarge'
tofu destroy ...                                 # apagar y no seguir pagando (incluido el NAT)
```

## Variables clave (`variables.tf`)
`region`, `proyecto`, `entorno`, `vpc_cidr`, `mdr_tipo`, `mdr_disco_gb`, `repo_url`/`repo_rama`
(qué desplegar), `llm_habilitado` (GPU on/off), `llm_tipo`, `llm_modelo_url`, `secretos_arns`
(ARNs de Secrets Manager a los que la instancia tendrá lectura).

## Estado de OpenTofu
Local por defecto (tesis). Para equipo/producción, configurar un backend `s3` con bloqueo en `main.tf`.
El `.gitignore` de esta carpeta evita commitear el estado y `.terraform/`.
