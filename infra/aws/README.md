# infra/aws — el MDR en AWS (OpenTofu)

Dos variantes, cada una en su carpeta y autosuficiente (se despliega, prueba y documenta por su cuenta;
quitar una es borrar su carpeta). **Para instalar, empieza por [INSTALAR.md](INSTALAR.md).**

| Variante | Para qué | Carpeta |
|---|---|---|
| **MDR** (producción) | El MDR (y, opcional, el modelo en GPU) conectado al SIEM y a la red de un cliente | [mdr/](mdr/README.md) |
| **Laboratorio** (pruebas) | El banco de pruebas, su Wazuh y el MDR en una máquina, para probar el MDR antes de un cliente; no se conecta a ninguno | [laboratorio/](laboratorio/README.md) |

Lo común a las dos (red, permisos de la instancia, disco de la traza) está en el módulo
[modulos/base/](modulos/base/). Diseño:
[despliegue-aws-opentofu.md](../../documentacion/04-fase4-diseno-de-arquitectura/despliegue-aws-opentofu.md),
[diseno-aws-laboratorio.md](../../documentacion/05-fase5-implementacion-del-prototipo/diseno-aws-laboratorio.md) y
[diseno-aws-dos-carpetas.md](../../documentacion/05-fase5-implementacion-del-prototipo/diseno-aws-dos-carpetas.md).

> **Estado (17/11/2026):** las dos probadas sin cuenta; el laboratorio, además, en vivo en local. **Sin
> `apply` real todavía.** El MDR que instalan es la v1.9.2 publicada.

## Cómo probar las dos

```sh
python3 -m unittest prototipo.tests.test_infra_aws   # pruebas estáticas de las dos variantes
sh infra/aws/emulador/probar.sh --listar             # las variantes y sus escenarios
sh infra/aws/emulador/probar.sh                      # todos los escenarios contra AWS Emulator (~12 min)
sh infra/aws/emulador/probar.sh mdr                  # o los de una variante
```

`ok` y «rechazado como se esperaba» son los resultados buenos: algunos escenarios comprueban que
OpenTofu **se niega** a crear una configuración que fallaría (por ejemplo, con el paquete 1.9.1).
[AWS Emulator](https://docs.aws.amazon.com/emulator/) emula en local la API de AWS (en memoria, sin
telemetría); `probar.sh` aplica los `.tf` reales en una copia temporal con un *override* que apunta el
proveedor al emulador, y suple dos huecos suyos (v1.0.492): `RunInstances` no hereda la zona de la
subred, y no trae la Deep Learning AMI de la GPU.

## Consultar el emulador a mano (AWS CLI)

`aws-emulator` solo arranca el emulador; para preguntarle (o crear algo) se usa la AWS CLI normal apuntada
a él. Sin instalarla: `uvx` (de [uv](https://docs.astral.sh/uv/)) la descarga al vuelo.

```sh
# Terminal 1: el emulador (déjala abierta)
aws-emulator --telemetry off

# Terminal 2: la AWS CLI apuntando al emulador
export PATH="$HOME/.local/bin:$PATH"          # donde instala uv (si no lo añadió a tu perfil)
EMU=~/.aws/emulator/9297
export AWS_ENDPOINT_URL=https://127.0.0.1:9297 AWS_CA_BUNDLE=$EMU/ca.pem \
       AWS_SHARED_CREDENTIALS_FILE=$EMU/emulator_credentials \
       AWS_CONFIG_FILE=/dev/null AWS_DEFAULT_REGION=us-east-1
alias aws='uvx --quiet --from awscli aws'

aws ec2 describe-vpcs --output table          # la VPC por defecto del emulador (172.31.0.0/16)
aws ec2 create-vpc --cidr-block 10.99.0.0/16  # crear algo…
aws ec2 describe-vpcs --output table          # …y verlo aparecer
```

- **No toca AWS de verdad:** todo va al emulador, con sus credenciales, que en AWS no valen.
- **Todo es de un solo arranque:** el emulador crea sus credenciales y su certificado al arrancar y los
  borra al apagarse, y lo creado vive en memoria. Al cerrarlo, se pierde; si una orden dice «Unable to
  locate credentials», el emulador no está en marcha.
- **Para ver lo que comprueban las pruebas:** con `probar.sh` en marcha, `aws ec2 describe-instances` en
  otra terminal muestra la misma instancia que luego enseñan las comprobaciones y las líneas `ok MCP …`.

## Consultar el despliegue por MCP (como un asistente de IA)

El servidor MCP de API de AWS (`awslabs.aws-api-mcp-server`, en local) permite que un asistente de IA
consulte la cuenta con órdenes de la AWS CLI. Aquí se prueba **contra el emulador**: después de crear y
comprobar cada escenario, se le pregunta por MCP por las instancias, los endpoints, el NAT, los perfiles
IAM y los discos, y se intenta **parar** la instancia, que tiene que negarse.

```sh
# Una vez: uv (https://docs.astral.sh/uv/), el gestor con el que se lanza el servidor
curl -LsSf https://astral.sh/uv/install.sh | sh

MDR_MCP=1 sh infra/aws/emulador/probar.sh E      # el laboratorio, consultado por MCP (~4 min)
MDR_MCP=1 sh infra/aws/emulador/probar.sh mdr    # o los escenarios de producción
```

Cada consulta sale como una línea `ok MCP …` con lo que respondió el emulador, y al final
`ok MCP no deja parar … (solo lectura)`. El cliente está en [emulador/mcp_cliente.py](emulador/mcp_cliente.py):
construye el entorno del servidor entero (sin heredar credenciales reales), con el endpoint, el
certificado y las credenciales falsas del emulador, `READ_OPERATIONS_ONLY=true` y
`AWS_API_MCP_TELEMETRY=false` (viene activada por defecto). El servidor alojado por AWS en la nube no
puede ver el emulador: solo vale el local.

**Qué demuestra y qué no:** que un asistente puede inspeccionar el despliegue por MCP, en solo lectura,
con las mismas preguntas que el día del primer `apply` real. **No** demuestra que la máquina funcione:
el emulador no ejecuta nada dentro de la instancia.

**El día del despliegue real**, el mismo servidor sirve para diagnosticar con permisos de **solo lectura**
(un perfil de AWS con la política `ReadOnlyAccess`). Configuración para un cliente MCP (Claude Code,
Claude Desktop…):

```json
{
  "mcpServers": {
    "aws-api": {
      "command": "uvx",
      "args": ["awslabs.aws-api-mcp-server@latest"],
      "env": {
        "AWS_REGION": "<región del despliegue>",
        "AWS_API_MCP_PROFILE_NAME": "<perfil de solo lectura>",
        "READ_OPERATIONS_ONLY": "true",
        "AWS_API_MCP_TELEMETRY": "false"
      }
    }
  }
}
```

Crear, cambiar y destruir lo sigue haciendo OpenTofu. La documentación del paquete lo marca como
sustituido por el servidor MCP que aloja AWS; para el emulador, este es el que funciona.

## Qué prueba cada capa

| Capa | Qué comprueba | Qué no |
|---|---|---|
| `tofu validate` + pruebas estáticas | Sintaxis, tipos, que las plantillas y los `.tf` dicen lo que deben | Nada se ejecuta |
| Simulacro (`simulacro/`) | El arranque del MDR de verdad en `amazonlinux:2023`: instala, firma la traza, monta el disco, y se para cuando falta algo | AWS: ni red, ni IAM, ni la GPU |
| Simulacro del laboratorio (`laboratorio/simulacro/`) | El arranque de la variante laboratorio en una «máquina» Amazon Linux 2023 vacía con `systemd`: se monta sola, levanta banco, Wazuh y MDR, contiene un ataque y lo vuelve a contener tras reiniciar | AWS: ni IAM, ni red, ni túnel SSM |
| AWS Emulator (`emulador/`) | El grafo de recursos entero, en orden, las precondiciones y lo que llega a cada instancia | No arranca máquinas ni evalúa IAM |

**Qué no prueba ninguna** (solo un despliegue real):

- que la búsqueda de la AMI encuentre Amazon Linux 2023 y la Deep Learning AMI en la región;
- la evaluación real de IAM y su retraso de propagación;
- el arranque en una instancia Nitro de verdad (nombres NVMe, cloud-init, systemd);
- la red real: `dnf` sin egreso, el DNS privado de los endpoints, el túnel SSM;
- la GPU: drivers, CUDA, la compilación de llama.cpp y la memoria;
- las cuotas y los costes de la cuenta.

## Herramientas comunes

- [emulador/](emulador/): `probar.sh` (descubre los escenarios de cada variante), `comun.py` (lo común de
  las comprobaciones) e `inventario.py` (genera el `inventario/` de una variante a partir de los planes).
- [simulacro/](simulacro/): el arranque del MDR en `amazonlinux:2023` con Docker.
