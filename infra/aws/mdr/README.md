# infra/aws/mdr — el MDR en producción (AWS, OpenTofu)

La variante de **producción**: el **MDR (daemon + consola)** y, opcional, el **modelo de lenguaje en GPU**,
conectados al SIEM y a la red del cliente. La otra variante, el laboratorio de pruebas, y el índice están
en [infra/aws/](../README.md); la guía corta de instalación, en [../INSTALAR.md](../INSTALAR.md).

> **Estado (17/11/2026):** probado sin cuenta (validación, pruebas estáticas, simulacro del arranque en
> `amazonlinux:2023` y `plan`/`apply`/`destroy` contra AWS Emulator). **Sin `apply` real** ni arranque de
> la GPU. No aplicar en una cuenta real sin acordar alcance y coste ([COSTES.md](COSTES.md)).

Para el despliegue oficial: [DESPLIEGUE.md](DESPLIEGUE.md) (cuotas y pasos), [COSTES.md](COSTES.md),
[inventario/](inventario/) (lo que crea cada escenario) y
[produccion.tfvars.ejemplo](produccion.tfvars.ejemplo) / [backend.tf.ejemplo](backend.tf.ejemplo).

**Esta carpeta usa el módulo común [`../modulos/base`](../modulos/base/)** (red, permisos de la instancia y
disco de la traza). Si la copias fuera del repositorio, lleva también `modulos/base/` en la misma posición
relativa (`../modulos/base`).

## Qué crea

- VPC con **subred privada** (sin IP pública), grupos de seguridad mínimos y **endpoints VPC** (SSM y S3):
  nada expuesto a Internet. El analista entra por **SSM** (túnel), no por un puerto abierto.
- EC2 **MDR**. Su arranque instala el MDR **como en un cliente**:
  1. monta el **EBS cifrado** de la traza, buscado por su identificador (nunca un disco efímero), en
     `/var/lib/mdr`. Si no aparece, el arranque se para, y la unidad del servicio exige ese montaje. En
     `fstab` va con `nofail`, así que si un día falta el disco la instancia sigue accesible por SSM;
  2. descarga el **paquete del release** (`mdr-<versión>.tar.gz`, con la consola compilada), comprueba su
     **SHA-256** y ejecuta `instalar.sh`: el código queda de root y en solo lectura;
  3. escribe el perfil (el indicado o un perfil mínimo para empezar con el asistente de red), la clave
     que **firma la traza** y el acceso a la **consola con token**, y arranca el servicio.
- EC2 **GPU** (solo si `llm_habilitado = true`): AMI de AWS con el driver NVIDIA y CUDA, llama.cpp en
  una etiqueta fija compilado con CUDA, y dos servicios en la red privada: el **generador** (8080, con
  contexto de 8192) y **bge-m3**, el embedder del RAG (8082). Los dos modelos se comprueban por su
  huella. Necesita `egreso_bootstrap = true` (clona llama.cpp) y una versión del MDR **≥ 1.9.2**: el
  paquete 1.9.1 no activa el modelo, y `tofu plan` lo rechaza. La GPU tarda en estar lista (compila y
  descarga): el MDR arranca antes, con la justificación de plantilla, y un vigilante
  (`mdr-espera-modelo`) lo reinicia en cuanto responden el modelo y el embedder (hasta 90 min).
- Dos roles IAM mínimos: el del MDR (SSM, los secretos indicados y el paquete y el perfil de S3) y el de
  la GPU (SSM y los modelos de S3), que **no** puede leer los secretos del MDR.

> **Primer arranque y egreso.** El *runtime* del daemon no llama a Internet (RNF-01). El primer arranque
> sí descarga (dnf, el paquete, los modelos): con `egreso_bootstrap = true` se crea un NAT para ese
> arranque; con `false` (por defecto), sube el paquete y el perfil a S3 y pásalos como `s3://…`
> (`tofu plan` lo exige). dnf tiene que llegar a los repositorios de Amazon Linux 2023, que AWS sirve
> desde S3 en cada región, a través del endpoint de S3 de la VPC; **sin comprobar aquí** (no hay cuenta).
> Las descargas se reintentan cinco veces antes de parar.

> **Para recibir alertas y contener**, la VPC tiene que llegar a la red del cliente (VPN o enlace
> privado): esta configuración no lo crea. Las alertas del SIEM llegan a `/var/lib/mdr/alerts.json` (o,
> con `TRIAJE_ESCUCHAR` en `/etc/mdr/triaje.env`, por el receptor de red del daemon); ver el manual de
> producción.

## Variables principales (`variables.tf`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `region` | `eu-west-1` | Región |
| `egreso_bootstrap` | `false` | NAT para el primer arranque |
| `mdr_version` | `1.9.2` | Versión del release a instalar |
| `mdr_paquete_url` | (release de GitHub) | `https://` o `s3://` del `mdr-<versión>.tar.gz` |
| `mdr_paquete_sha256` | huella de `mdr-1.9.2.tar.gz` | Si no coincide, el arranque se para. Cámbiala junto con la versión |
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

Si un secreto indicado no se puede leer (tras cinco intentos), el arranque **se para**: nunca genera uno
nuevo por su cuenta. Con secretos y sin egreso se crea un endpoint de Secrets Manager en la VPC. Usa el
ARN completo del secreto; si está cifrado con una clave KMS propia, el rol necesita además `kms:Decrypt`.

## Recrear la instancia (cambiar de versión)

Cambiar `mdr_version`, el perfil o los secretos **recrea la instancia del MDR**. Activar o recrear la GPU
también la recrea, porque cambia la IP privada del modelo. El arranque solo se ejecuta una vez en cada
instancia. Al recrearla:

- **se conserva** todo lo del disco de la traza (`/var/lib/mdr`): la traza, la clave del conector, lo
  editado en la consola y la postura. El arranque reasigna a `triaje` los ficheros del disco aunque la
  instancia nueva le dé otro UID;
- **se rehace** lo que vive en `/etc/mdr`:
  - el perfil vuelve a ser `perfil_url` o el perfil mínimo; lo adoptado con el asistente de red se pierde
    si no está en `perfil_url`;
  - la clave de la traza: si no está en Secrets Manager, se genera otra y la cadena anterior deja de
    verificarse (el arranque lo avisa);
  - el analista `admin` recibe un token nuevo;
  - se pierden los cambios hechos a mano con `mdr configurar`, por ejemplo el receptor de red o TLS.

Por eso, para algo más que una demo: el perfil en `perfil_url` (S3) y los dos secretos.

## Cómo probarla

Todo sin cuenta ni coste, desde la raíz del repositorio:

```sh
(cd infra/aws/mdr && tofu init -backend=false && tofu validate)    # sintaxis y tipos
python3 -m unittest prototipo.tests.test_infra_aws                  # pruebas estáticas (las de las dos variantes)
sh infra/aws/simulacro/simulacro.sh dist/mdr-1.9.2.tar.gz           # el arranque en amazonlinux:2023 (Docker, ~5 min)
sh infra/aws/emulador/probar.sh mdr                                 # A, B, C y D contra AWS Emulator (~8 min)
```

| Escenario | Qué es | Qué se espera |
|---|---|---|
| A | Con egreso (NAT), paquete de GitHub, sin secretos ni GPU | se crea; 11 comprobaciones |
| B | Sin egreso, paquete en S3, los dos secretos (el recomendado) | se crea; 12 comprobaciones |
| C | GPU con el paquete 1.9.1 | **rechazado** por la precondición (es lo correcto) |
| D | Con la GPU (MDR ≥ 1.9.2) | se crea; 14 comprobaciones |

Las comprobaciones de cada escenario están en [emulador/comprobar.py](emulador/comprobar.py) y sus
variables en [emulador/escenarios.sh](emulador/escenarios.sh). Qué prueba cada capa y qué no prueba
ninguna: [el índice](../README.md).

## Aplicar de verdad (con la cuenta de la empresa)

Paso a paso, con cuotas, secretos y estado remoto: [DESPLIEGUE.md](DESPLIEGUE.md). En resumen:

```sh
cd infra/aws/mdr
tofu init
tofu plan  -var-file=produccion.tfvars -out despliegue.plan
tofu apply despliegue.plan
eval "$(tofu output -raw comando_tunel_visor)"   # la consola por SSM en http://127.0.0.1:8787
tofu output -raw comando_token_admin              # cómo leer el token del analista admin
tofu destroy -var-file=produccion.tfvars          # apaga la instancia antes de soltar el disco de la traza
```

## Estado de OpenTofu

Local por defecto. Para un equipo o producción, copia [backend.tf.ejemplo](backend.tf.ejemplo) a
`backend.tf` (estado en S3, cifrado y con bloqueo). El `.gitignore` de `infra/aws/` evita commitear el
estado y `.terraform/`.
