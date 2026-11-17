# infra/aws — despliegue en AWS (OpenTofu)

Infraestructura para correr el **MDR (daemon + consola)** y, opcional, el **modelo de lenguaje en GPU**
en AWS. Implementa el plano de
[despliegue-aws-opentofu.md](../../documentacion/04-fase4-diseno-de-arquitectura/despliegue-aws-opentofu.md).
Briefing para la reunión con el tutor industrial:
[briefing-reunion-despliegue-aws.md](../../documentacion/04-fase4-diseno-de-arquitectura/briefing-reunion-despliegue-aws.md).

> **Estado (17/11/2026):** corregido según los puntos #6–#12, #18 y #19 de
> [OBSERVACIONES-REVISION.md](../../OBSERVACIONES-REVISION.md) y el plan
> [plan-despliegue-aws.md](../../documentacion/05-fase5-implementacion-del-prototipo/plan-despliegue-aws.md).
> Comprobado en tres capas (ver «Qué prueba cada capa»): `tofu validate` y pruebas estáticas, el
> **simulacro** del arranque del MDR en `amazonlinux:2023`, y `plan`/`apply`/`destroy` contra **AWS
> Emulator**. **No probado:** un `apply` en una cuenta real y el arranque de la GPU. **No hacer `apply` en
> una cuenta real** sin acordar alcance y coste ([COSTES.md](COSTES.md); la GPU es el grueso, por eso
> `llm_habilitado = false` por defecto).

Para el despliegue oficial: [DESPLIEGUE.md](DESPLIEGUE.md) (cuotas y pasos), [COSTES.md](COSTES.md),
[inventario/](inventario/) (lo que crea cada escenario) y
[produccion.tfvars.ejemplo](produccion.tfvars.ejemplo) / [backend.tf.ejemplo](backend.tf.ejemplo).

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

## Dos variantes

- **`variante = "mdr"`** (por defecto): la de producción. El MDR se conecta al SIEM y a la red reales del
  cliente (hace falta un enlace privado con su red: VPN o similar).
- **`variante = "laboratorio"`**: el entorno de pruebas de la empresa. La misma instancia (`t3.xlarge`)
  levanta el **laboratorio del banco**, su **Wazuh** y el **MDR**, como en local, y en cada encendido lo
  rehace solo (unidad `mdr-laboratorio`, `lab/banco/servicio-mdr.sh`). **No se conecta a ningún
  cliente.** Necesita un MDR ≥ 1.9.2, `egreso_bootstrap = true` y `laboratorio_commit`; sin GPU. Guía:
  [DESPLIEGUE.md](DESPLIEGUE.md), «Variante laboratorio».

## Variables principales (`variables.tf`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `region` | `eu-west-1` | Región |
| `variante` | `mdr` | `mdr` (producción) o `laboratorio` (banco, Wazuh y MDR en una máquina; ver abajo) |
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

## Prueba contra AWS Emulator (sin cuenta, sin coste)

[AWS Emulator](https://docs.aws.amazon.com/emulator/) emula en local la API de AWS (en memoria, sin
telemetría). `probar.sh` aplica los `.tf` de esta carpeta **sin tocarlos**: en una copia temporal añade
un *override* que apunta el proveedor al emulador, y hace `plan`, `apply` y `destroy`.

```sh
sh infra/aws/emulador/probar.sh            # los cuatro escenarios
sh infra/aws/emulador/probar.sh B          # solo uno
```

| Escenario | Qué es | Resultado (17/11) |
|---|---|---|
| A | MDR con egreso (NAT), paquete de GitHub | 27 recursos; 11/11 comprobaciones |
| B | MDR sin egreso, paquete en S3, dos secretos | 23 recursos; 12/12 |
| C | GPU con el paquete 1.9.1 | rechazado por la precondición, como debe |
| D | MDR + GPU (MDR ≥ 1.9.2) | 29 recursos; 14/14 |
| E | Variante laboratorio (MDR ≥ 1.9.2, con egreso) | 27 recursos; 16/16 |
| F | Laboratorio sin egreso | rechazado por la precondición |
| G | Laboratorio con el paquete 1.9.1 | rechazado por la precondición |

Las comprobaciones (`emulador/comprobar.py`) leen el estado y el script de arranque tal como lo
devuelve la API: rutas y NAT, endpoints, permisos de cada rol, puertos de la GPU y que el arranque del
MDR apunte a la IP de la GPU. Con `MDR_INVENTARIO=<dir>` se guardan los planes, y
`emulador/inventario.py` genera [inventario/](inventario/).

El emulador (v1.0.492) tiene dos huecos que el *override* suple solo en la copia: `RunInstances` no
hereda la zona de la subred, y no trae la Deep Learning AMI (en D se usa la de Amazon Linux 2023).

## Qué prueba cada capa

| Capa | Qué comprueba | Qué no |
|---|---|---|
| `tofu validate` + pruebas estáticas | Sintaxis, tipos, que las plantillas y los `.tf` dicen lo que deben | Nada se ejecuta |
| Simulacro (`simulacro/`) | El arranque del MDR de verdad en `amazonlinux:2023`: instala, firma la traza, monta el disco, y se para cuando falta algo | AWS: ni red, ni IAM, ni la GPU |
| AWS Emulator (`emulador/`) | El grafo de recursos entero, en orden, las precondiciones y lo que llega a cada instancia | No arranca máquinas ni evalúa IAM |

**Qué no prueba ninguna** (solo un despliegue real):

- que la búsqueda de la AMI encuentre Amazon Linux 2023 y la Deep Learning AMI en la región;
- la evaluación real de IAM y su retraso de propagación;
- el arranque en una instancia Nitro de verdad (nombres NVMe, cloud-init, systemd);
- la red real: `dnf` sin egreso, el DNS privado de los endpoints, el túnel SSM;
- la GPU: drivers, CUDA, la compilación de llama.cpp y la memoria;
- las cuotas y los costes de la cuenta.

## Aplicar de verdad (con la cuenta de la empresa)

Paso a paso, con cuotas, secretos y estado remoto: [DESPLIEGUE.md](DESPLIEGUE.md). En resumen:

```sh
export AWS_PROFILE=<perfil-de-la-empresa>
tofu plan  -var 'region=<region>' -var 'egreso_bootstrap=true'
tofu apply -var 'region=<region>' -var 'egreso_bootstrap=true'
tofu output -raw comando_tunel_visor # abre la consola por SSM en http://127.0.0.1:8787
tofu output -raw comando_token_admin # cómo leer el token del analista admin
# Con el modelo (coste GPU): -var 'llm_habilitado=true' -var 'llm_tipo=g4dn.xlarge'
#   -var 'llm_modelo_url=…' -var 'llm_modelo_sha256=…' -var 'embed_modelo_url=…' -var 'embed_modelo_sha256=…'
tofu destroy …                      # apaga la instancia antes de soltar el disco de la traza
```

Las alertas del SIEM llegan a `/var/lib/mdr/alerts.json` (o, con `TRIAJE_ESCUCHAR` en
`/etc/mdr/triaje.env`, por el receptor de red del daemon); ver el manual de producción.

## Estado de OpenTofu

Local por defecto. Para un equipo o producción, copia [backend.tf.ejemplo](backend.tf.ejemplo) a
`backend.tf` (estado en S3, cifrado y con bloqueo).
El `.gitignore` de esta carpeta evita commitear el estado y `.terraform/`.
