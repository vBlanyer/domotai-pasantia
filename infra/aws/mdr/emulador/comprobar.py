"""Comprobaciones de los escenarios de la variante MDR contra AWS Emulator (los lanza
infra/aws/emulador/probar.sh mdr). Lo común está en infra/aws/emulador/comun.py.

    python3 comprobar.py <A|B|D> estado.json
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "emulador"))
import comun  # noqa: E402

# Escenarios que crean algo (C se rechaza en el plan); los usa también inventario.py.
ESCENARIOS = {
    "A": "Con egreso para el primer arranque (NAT), paquete del release de GitHub, sin secretos ni GPU.",
    "B": "Sin egreso: paquete en S3, los dos secretos en Secrets Manager; sin NAT ni GPU. El de producción recomendado.",
    "D": "Como A, más la GPU con el modelo y el embedder (MDR >= 1.9.2).",
}


def comprobaciones(escenario, estado):
    rs = comun.recursos(estado)
    tipos = {r["type"] for r in rs.values()}
    out = []

    def mira(nombre, cond):
        out.append((nombre, bool(cond)))

    endpoints = comun.comprobaciones_base(rs, "aws_instance.mdr", "del MDR", mira)
    politicas = [r for r in rs.values() if r["type"] == "aws_iam_role_policy"]
    gpu = ("aws_instance.llm[0]", "aws_iam_role.gpu[0]", "aws_iam_instance_profile.gpu[0]", "aws_security_group.llm[0]")

    if escenario == "A":
        mira("con egreso: NAT, IP elástica e internet gateway",
             {"aws_nat_gateway", "aws_eip", "aws_internet_gateway"} <= tipos)
        mira("sin secretos: ni endpoint de Secrets Manager ni política de secretos",
             "secretsmanager" not in endpoints and not any(p["values"]["name"] == "leer-secretos" for p in politicas))
        mira("sin GPU: ni instancia, ni rol, ni perfil, ni grupo de seguridad", not any(g in rs for g in gpu))
    if escenario == "B":
        mira("sin egreso: ni NAT ni internet gateway", not ({"aws_nat_gateway", "aws_internet_gateway"} & tipos))
        mira("endpoint de Secrets Manager", "secretsmanager" in endpoints)
        sec = [p for p in politicas if p["values"]["name"] == "leer-secretos"]
        mira("política de lectura de los dos secretos",
             sec and all(s in sec[0]["values"]["policy"] for s in ("mdr/traza-clave", "mdr/operadores")))
        s3 = [p for p in politicas if p["values"]["name"] == "leer-paquete-y-perfil"]
        mira("política de lectura del paquete en S3",
             s3 and "arn:aws:s3:::mdr-prueba/mdr-1.9.1.tar.gz" in s3[0]["values"]["policy"])
    if escenario == "D":
        llm = rs.get("aws_instance.llm[0]")
        mira("instancia GPU creada", llm)
        perfil_gpu = rs.get("aws_iam_instance_profile.gpu[0]", {}).get("values", {}).get("name")
        rol = rs.get("aws_iam_role.gpu[0]", {}).get("values", {})
        mira("la GPU usa su propio perfil IAM", llm and perfil_gpu and llm["values"]["iam_instance_profile"] == perfil_gpu)
        de_gpu = [p for p in politicas if p["values"]["role"] in (rol.get("name"), rol.get("id"))]
        mira("el rol de la GPU no puede leer secretos",
             rol.get("name") and not any("secretsmanager" in p["values"]["policy"] for p in de_gpu))
        mira("el rol de la GPU lee los dos modelos de S3",
             any("generador.gguf" in p["values"]["policy"] and "bge-m3.gguf" in p["values"]["policy"] for p in de_gpu))
        sg = rs.get("aws_security_group.llm[0]", {}).get("values", {})
        mira("la GPU solo abre 8080 y 8082", {i["from_port"] for i in sg.get("ingress", [])} == {8080, 8082})
        ud = comun.user_data(rs)
        if llm and ud is not None:
            ip = llm["values"]["private_ip"]
            mira("el arranque del MDR apunta al modelo y al embedder de la GPU",
                 f"http://{ip}:8080" in ud and f"http://{ip}:8082" in ud)
    return out


if __name__ == "__main__":
    sys.exit(comun.main(sys.argv, comprobaciones))
