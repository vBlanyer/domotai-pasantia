"""Inventario de lo que crea infra/aws, a partir de los planes que guarda probar.sh (MDR_INVENTARIO=<dir>).

    MDR_INVENTARIO=/tmp/inv sh infra/aws/emulador/probar.sh A B D
    python3 infra/aws/emulador/inventario.py /tmp/inv infra/aws/inventario

Escribe inventario/escenario-{a,b,d}.json (por recurso: dirección, tipo y la configuración que importa
revisar; sin identificadores ni valores del emulador) e inventario/README.md (tablas legibles).
"""
import json
import os
import sys

ESCENARIOS = {
    "A": "Con egreso para el primer arranque (NAT), paquete del release de GitHub, sin secretos ni GPU.",
    "B": "Sin egreso: paquete en S3, los dos secretos en Secrets Manager; sin NAT ni GPU. El de producción recomendado.",
    "D": "Como A, más la GPU con el modelo y el embedder (MDR >= 1.9.2).",
    "E": "Variante laboratorio: la instancia del MDR levanta el banco, Wazuh y el MDR (t3.xlarge, con egreso, MDR >= 1.9.2). No se conecta a ningún cliente.",
}

# Por qué existe cada recurso (por dirección sin índice).
POR_QUE = {
    "aws_vpc.main": "Red privada del MDR.",
    "aws_subnet.privada": "Subred sin IP pública donde viven las instancias.",
    "aws_subnet.publica": "Subred pública que solo aloja el NAT del primer arranque.",
    "aws_route_table.privada": "Rutas de la subred privada (sin salida a Internet salvo el NAT).",
    "aws_route_table_association.privada": "Asocia la subred privada a sus rutas.",
    "aws_route_table.publica": "Rutas de la subred pública hacia el internet gateway.",
    "aws_route_table_association.publica": "Asocia la subred pública a sus rutas.",
    "aws_route.privada_egreso": "Salida de la subred privada por el NAT: la usa el primer arranque, y queda mientras egreso_bootstrap = true.",
    "aws_internet_gateway.igw": "Salida a Internet de la subred pública (solo con egreso).",
    "aws_eip.nat": "IP pública del NAT (solo con egreso).",
    "aws_nat_gateway.nat": "NAT para que el primer arranque descargue paquetes (solo con egreso); se cobra mientras exista.",
    "aws_security_group.mdr": "Cortafuegos del MDR: sin entradas; salida libre.",
    "aws_security_group.llm": "Cortafuegos de la GPU: solo el MDR entra, al 8080 y al 8082. Se crea aunque no haya GPU (sin coste).",
    "aws_security_group.endpoints": "Cortafuegos de los endpoints: 443 desde la VPC.",
    "aws_vpc_endpoint.ssm": "Endpoints de SSM: el analista entra por túnel, sin puertos abiertos.",
    "aws_vpc_endpoint.s3": "Endpoint de S3: paquete, perfil y modelos sin salir a Internet.",
    "aws_vpc_endpoint.secretsmanager": "Endpoint de Secrets Manager: el arranque lee los secretos sin Internet.",
    "aws_iam_role.instancia": "Rol del MDR.",
    "aws_iam_role_policy_attachment.ssm": "El MDR se gestiona por SSM.",
    "aws_iam_role_policy.leer_secretos": "El MDR lee la clave de la traza y los analistas.",
    "aws_iam_role_policy.leer_s3": "El MDR lee el paquete y el perfil de S3.",
    "aws_iam_instance_profile.instancia": "Perfil que asocia el rol a la instancia del MDR.",
    "aws_iam_role.gpu": "Rol propio de la GPU (sin acceso a los secretos del MDR). Se crea aunque no haya GPU (sin coste).",
    "aws_iam_role_policy_attachment.gpu_ssm": "La GPU se gestiona por SSM. Se crea aunque no haya GPU (sin coste).",
    "aws_iam_role_policy.gpu_s3": "La GPU lee los dos modelos de S3.",
    "aws_iam_instance_profile.gpu": "Perfil que asocia el rol de la GPU a su instancia. Se crea aunque no haya GPU (sin coste).",
    "aws_instance.mdr": "El MDR (daemon y consola).",
    "aws_ebs_volume.traza": "Disco cifrado de la traza y del estado del MDR (/var/lib/mdr).",
    "aws_volume_attachment.traza": "Engancha el disco de la traza al MDR (destroy apaga antes de soltarlo).",
    "aws_instance.llm": "La GPU con el modelo de lenguaje y el embedder del RAG.",
}

# Qué se guarda de cada tipo (lo que importa revisar).
CAMPOS = {
    "aws_vpc": ["cidr_block", "enable_dns_support", "enable_dns_hostnames"],
    "aws_subnet": ["cidr_block", "map_public_ip_on_launch"],
    "aws_route": ["destination_cidr_block"],
    "aws_eip": ["domain"],
    "aws_security_group": ["description", "ingress", "egress"],
    "aws_vpc_endpoint": ["service_name", "vpc_endpoint_type", "private_dns_enabled"],
    "aws_iam_role_policy_attachment": ["policy_arn"],
    "aws_iam_role_policy": ["name", "policy"],
    "aws_instance": ["instance_type", "associate_public_ip_address", "metadata_options", "root_block_device",
                     "user_data_replace_on_change"],
    "aws_ebs_volume": ["size", "type", "encrypted"],
    "aws_volume_attachment": ["device_name", "stop_instance_before_detaching"],
}


def _limpiar(tipo, despues):
    c = {}
    for campo in CAMPOS.get(tipo, []):
        v = (despues or {}).get(campo)
        if v in (None, [], {}, ""):
            continue
        if campo == "policy" and isinstance(v, str):
            doc = json.loads(v)
            v = [{"acciones": s.get("Action"), "sobre": s.get("Resource")} for s in doc.get("Statement", [])]
        if campo in ("ingress", "egress"):
            v = [{"puertos": f"{r['from_port']}-{r['to_port']}", "protocolo": r["protocol"],
                  # sin rangos de IP, el origen es otro grupo de seguridad (su id se conoce al aplicar)
                  "origen": r.get("cidr_blocks") or "un grupo de seguridad (ver la descripción)",
                  "descripcion": r.get("description") or None} for r in v]
        if campo == "root_block_device":
            v = [{k: d.get(k) for k in ("volume_size", "volume_type", "encrypted")} for d in v]
        if campo == "metadata_options":
            v = [{"http_tokens": d.get("http_tokens")} for d in v]
        c[campo] = v
    if tipo == "aws_instance":
        c["user_data"] = "plantilla de arranque (templates/), comprobada en el simulacro y contra el emulador"
    return c


def inventario(plan):
    out = []
    for r in plan.get("resource_changes", []):
        if r.get("mode") != "managed" or "create" not in r["change"]["actions"]:
            continue
        base = r["address"].split("[")[0]
        out.append({"direccion": r["address"], "tipo": r["type"], "por_que": POR_QUE.get(base, ""),
                    "config": _limpiar(r["type"], r["change"]["after"])})
    return sorted(out, key=lambda x: x["direccion"])


def main(argv):
    origen, destino = argv[1], argv[2]
    os.makedirs(destino, exist_ok=True)
    md = ["# Inventario de lo que crea infra/aws", "",
          "Generado con `infra/aws/emulador/inventario.py` a partir de los planes de `probar.sh` contra AWS",
          "Emulator. Es lo que `tofu apply` crearía en cada escenario; sirve para revisar el despliegue y",
          "para la estimación de [costes](../COSTES.md). Los identificadores reales los pone AWS al aplicar.", ""]
    for e, descripcion in ESCENARIOS.items():
        ruta = os.path.join(origen, f"plan-{e}.json")
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding="utf-8") as f:
            recursos = inventario(json.load(f))
        with open(os.path.join(destino, f"escenario-{e.lower()}.json"), "w", encoding="utf-8") as f:
            json.dump({"escenario": e, "descripcion": descripcion, "recursos": recursos}, f, ensure_ascii=False, indent=1)
            f.write("\n")
        md += [f"## Escenario {e} · {len(recursos)} recursos", "", descripcion, "",
               "| Recurso | Tipo | Por qué existe |", "|---|---|---|"]
        md += [f"| `{r['direccion']}` | `{r['tipo']}` | {r['por_que']} |" for r in recursos]
        md.append("")
    with open(os.path.join(destino, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
