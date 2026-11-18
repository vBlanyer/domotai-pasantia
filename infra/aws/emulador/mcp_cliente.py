"""Consulta por MCP el despliegue creado en AWS Emulator, como lo haría un asistente de IA.

Lanza el servidor MCP de API de AWS (awslabs.aws-api-mcp-server, en local) apuntando al emulador, en
SOLO LECTURA y sin telemetría, y le hace las preguntas del día de un despliegue: instancias, endpoints,
NAT, perfiles IAM y discos. Por último intenta PARAR la instancia, y eso tiene que negarse.

Lo lanza probar.sh con MDR_MCP=1 (después de crear y comprobar cada escenario, antes de destruirlo):

    MDR_MCP=1 sh infra/aws/emulador/probar.sh E

A mano, con el emulador en marcha y algo creado en él (necesita uv: https://docs.astral.sh/uv/):

    uv run --python 3.12 --with mcp python infra/aws/emulador/mcp_cliente.py

Código de salida 0 si todas las consultas responden y la parada se niega; 1 si no.

Nunca habla con AWS de verdad: el entorno del servidor se construye entero aquí (no hereda credenciales
reales) con las credenciales falsas y el certificado del emulador. Si el servidor ignorara el endpoint,
fallaría al autenticarse en AWS sin crear nada.
"""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EMU = os.path.expanduser("~/.aws/emulator/9297")
ENTORNO = {
    "PATH": os.environ.get("PATH", ""),
    "HOME": os.environ.get("HOME", ""),
    "AWS_REGION": "us-east-1",
    "AWS_ENDPOINT_URL": "https://127.0.0.1:9297",
    "AWS_CA_BUNDLE": f"{EMU}/ca.pem",
    "AWS_SHARED_CREDENTIALS_FILE": f"{EMU}/emulator_credentials",
    "AWS_CONFIG_FILE": "/dev/null",
    "AWS_EC2_METADATA_DISABLED": "true",
    "READ_OPERATIONS_ONLY": "true",
    "AWS_API_MCP_TELEMETRY": "false",
    "AWS_API_MCP_SUPPRESS_DEPRECATION_WARNING": "true",
}

CONSULTAS = [
    ("instancias", "aws ec2 describe-instances --query \"Reservations[].Instances[].{id:InstanceId,tipo:InstanceType,"
                   "estado:State.Name,ip_publica:PublicIpAddress,nombre:Tags[?Key=='Name']|[0].Value}\""),
    ("endpoints de la VPC", "aws ec2 describe-vpc-endpoints --query \"VpcEndpoints[].ServiceName\""),
    ("NAT", "aws ec2 describe-nat-gateways --query \"NatGateways[].{id:NatGatewayId,estado:State}\""),
    ("perfiles IAM", "aws iam list-instance-profiles --query \"InstanceProfiles[].InstanceProfileName\""),
    ("discos", "aws ec2 describe-volumes --query \"Volumes[].{id:VolumeId,gb:Size,cifrado:Encrypted}\""),
]


def _respuesta(resultado):
    """(resultado, error) de una llamada a call_aws."""
    texto = "\n".join(getattr(c, "text", "") for c in resultado.content)
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        return None, texto.strip()[:300]
    datos = datos[0] if isinstance(datos, list) and datos else datos
    if datos.get("error"):
        return None, datos["error"]
    r = datos.get("response") or {}
    if r.get("error"):
        return None, r["error"]
    return json.loads(r.get("as_json") or "{}").get("Result"), None


async def main():
    trabajo = os.path.join(os.environ.get("TMPDIR", "/tmp"), "mdr-mcp-trabajo")
    os.makedirs(trabajo, exist_ok=True)
    servidor = StdioServerParameters(command="uvx", args=["awslabs.aws-api-mcp-server@latest"],
                                     env={**ENTORNO, "AWS_API_MCP_WORKING_DIR": trabajo})
    fallos = 0
    async with stdio_client(servidor) as (leer, escribir):
        async with ClientSession(leer, escribir) as sesion:
            await sesion.initialize()
            herramientas = [t.name for t in (await sesion.list_tools()).tools]
            print(f"   MCP    servidor de API de AWS ({', '.join(herramientas)}), solo lectura, contra el emulador")
            instancia = None
            for titulo, orden in CONSULTAS:
                resultado, error = _respuesta(await sesion.call_tool("call_aws", {"cli_command": orden}))
                if error:
                    fallos += 1
                    print(f"   FALLO  MCP {titulo}: {error}")
                    continue
                if titulo == "instancias" and resultado:
                    instancia = resultado[0].get("id")
                print(f"   ok     MCP {titulo}: {json.dumps(resultado, ensure_ascii=False)}")
            if instancia:
                _, error = _respuesta(await sesion.call_tool(
                    "call_aws", {"cli_command": f"aws ec2 stop-instances --instance-ids {instancia}"}))
                if error and "denied" in error:
                    print(f"   ok     MCP no deja parar {instancia} (solo lectura): {error}")
                else:
                    fallos += 1
                    print(f"   FALLO  MCP dejó intentar parar {instancia}: {error or 'sin error'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
