# infra/aws — despliegue en AWS (OpenTofu)

Infraestructura para correr el **MDR (daemon + consola)** y, opcional, el **modelo de lenguaje en GPU**
en AWS. Implementa el plano de
[despliegue-aws-opentofu.md](../../documentacion/04-fase4-diseno-de-arquitectura/despliegue-aws-opentofu.md).
Briefing para la reunión con el tutor industrial:
[briefing-reunion-despliegue-aws.md](../../documentacion/04-fase4-diseno-de-arquitectura/briefing-reunion-despliegue-aws.md).

> **Estado (17/11/2026):** corregido según los puntos #6–#12, #18 y #19 de
> [OBSERVACIONES-REVISION.md](../../OBSERVACIONES-REVISION.md) y el plan
> [plan-despliegue-aws.md](../../documentacion/05-fase5-implementacion-del-prototipo/plan-despliegue-aws.md).
> Comprobado: `tofu validate`, pruebas estáticas (`prototipo/tests/test_infra_aws.py`) y el
> **simulacro** del arranque del MDR en `amazonlinux:2023` (más abajo). **No probado:** un `apply` en una
> cuenta real y el arranque de la GPU (compilar llama.cpp con CUDA necesita una GPU). **No hacer `apply`
> en una cuenta real** sin acordar alcance y coste (la GPU es el grueso del coste; por eso
> `llm_habilitado = false` por defecto).

## Qué crea

- VPC con **subred privada** (sin IP pública), grupos de seguridad mínimos y **endpoints VPC** (SSM y S3):
  nada expuesto a Internet. El analista entra por **SSM** (túnel), no por un puerto abierto.
- EC2 **MDR**. Su arranque instala el MDR **como en un cliente**:
  1. monta el **EBS cifrado** de la traza en `/var/lib/mdr` (si no aparece, el arranque se para, y la
     unidad del servicio exige ese montaje);
  2. descarga el **paquete del release** (`mdr-<versión>.tar.gz`, con la consola compilada), comprueba su
     **SHA-256** y ejecuta `instalar.sh`: el código queda de root y en solo lectura;
  3. escribe el perfil (el indicado o un perfil mínimo para empezar con el asistente de red), la clave
     que **firma la traza** y el acceso a la **consola con token**, y arranca el servicio.
- EC2 **GPU** (solo si `llm_habilitado = true`): AMI de AWS con el driver NVIDIA y CUDA, llama.cpp en
  una etiqueta fija compilado con CUDA, y dos servicios en la red privada: el **generador** (8080) y
  **bge-m3**, el embedder del RAG (8082). Los dos modelos se comprueban por su huella.
- Rol IAM mínimo: SSM, lectura de los secretos indicados y de los objetos de S3 indicados.

> **Primer arranque y egreso.** El *runtime* del daemon no llama a Internet (RNF-01). El primer arranque
> sí descarga (dnf, el paquete, los modelos): con `egreso_bootstrap = true` se crea un NAT para ese
> arranque; con `false` (por defecto), sube el paquete (y los modelos) a S3 y pásalos como `s3://…`.

## Variables principales (`variables.tf`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `region` | `eu-west-1` | Región |
| `egreso_bootstrap` | `false` | NAT para el primer arranque |
| `mdr_version` | `1.9.1` | Versión del release a instalar |
| `mdr_paquete_url` | (release de GitHub) | `https://` o `s3://` del `mdr-<versión>.tar.gz` |
| `mdr_paquete_sha256` | huella de `mdr-1.9.1.tar.gz` | Si no coincide, el arranque se para. Cámbiala junto con la versión |
| `perfil_url` | (perfil mínimo) | Perfil del cliente, `https://` o `s3://` |
| `red_cliente_cidrs` | (la VPC) | Rangos para el perfil mínimo |
| `secreto_traza_arn` | (se genera) | Secreto con la clave HMAC de la traza |
| `secreto_operadores_arn` | (un admin) | Secreto con los analistas `{"<token>": "<nombre>"}` |
| `llm_habilitado` | `false` | Crea la GPU |
| `llm_modelo_url`, `llm_modelo_sha256` | — | El `.gguf` del generador (obligatorias con GPU) |
| `embed_modelo_url`, `embed_modelo_sha256` | — | El `.gguf` de bge-m3 (obligatorias con GPU) |
| `llama_cpp_ref` | `b12445` | Etiqueta de llama.cpp |

## Secretos (recomendado para algo más que una demo)

Sin secretos, el arranque **genera** la clave de la traza y da de alta a un analista `admin`. Para una
demo vale; pero si se recrea la instancia, la clave nueva no verifica la traza anterior (el arranque lo
avisa en `/var/log/mdr-arranque.log`). Con Secrets Manager:

```sh
aws secretsmanager create-secret --name mdr/traza-clave --secret-string "$(openssl rand -hex 32)"
aws secretsmanager create-secret --name mdr/operadores --secret-string '{"<token-de-ana>":"ana"}'
tofu apply -var 'secreto_traza_arn=<ARN de mdr/traza-clave>' -var 'secreto_operadores_arn=<ARN de mdr/operadores>' …
```

Si un secreto indicado no se puede leer, el arranque **se para**: nunca genera uno nuevo por su cuenta.

## Validación offline (sin cuenta AWS, sin coste)

```sh
cd infra/aws
tofu init -backend=false && tofu fmt -check -recursive && tofu validate
cd ../.. && python3 -m unittest prototipo.tests.test_infra_aws

# Simulacro del arranque del MDR (docker, tofu y red para dnf; ~5 min):
sh deploy/empaquetar.sh                      # o usa el mdr-<versión>.tar.gz del release
sh infra/aws/simulacro/simulacro.sh dist/mdr-1.9.1.tar.gz
```

El simulacro renderiza la plantilla con OpenTofu y la ejecuta en `amazonlinux:2023` (la distribución de
la AMI) con un disco de bucle y dobles de `systemctl` y `aws`. Cuatro casos: el normal (instalado, traza
firmada, consola con token, disco montado, servicio habilitado), sin disco (se para), paquete con otra
huella (se para sin instalar) y secreto ilegible (se para). No ejerce la GPU.

## Aplicar de verdad (con la cuenta de la empresa)

```sh
export AWS_PROFILE=<perfil-de-la-empresa>
tofu plan  -var 'region=<region>' -var 'egreso_bootstrap=true'
tofu apply -var 'region=<region>' -var 'egreso_bootstrap=true'
tofu output comando_tunel_visor     # abre la consola por SSM en http://127.0.0.1:8787
tofu output comando_token_admin     # cómo leer el token del analista admin
# Con el modelo (coste GPU): -var 'llm_habilitado=true' -var 'llm_tipo=g4dn.xlarge'
#   -var 'llm_modelo_url=…' -var 'llm_modelo_sha256=…' -var 'embed_modelo_url=…' -var 'embed_modelo_sha256=…'
tofu destroy …                      # apaga la instancia antes de soltar el disco de la traza
```

Las alertas del SIEM llegan a `/var/lib/mdr/alerts.json` (o, con `TRIAJE_ESCUCHAR` en
`/etc/mdr/triaje.env`, por el receptor de red del daemon); ver el manual de producción.

## Estado de OpenTofu

Local por defecto. Para un equipo o producción, configurar un backend `s3` con bloqueo en `main.tf`.
El `.gitignore` de esta carpeta evita commitear el estado y `.terraform/`.
