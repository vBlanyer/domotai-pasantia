"""Comprobaciones de un escenario de infra/aws/emulador/probar.sh sobre el estado que dejó OpenTofu
(`tofu show -json`). Sin AWS CLI: lo que se mira es lo que OpenTofu creó en el emulador.

    python3 comprobar.py <A|B|D> estado.json      → imprime una línea por comprobación; código 1 si falla alguna
"""
import base64
import json
import subprocess
import sys


def _recursos(estado):
    return {r["address"]: r for r in estado.get("values", {}).get("root_module", {}).get("resources", [])}


def _bash_n(texto):
    return subprocess.run(["bash", "-n"], input=texto, text=True, capture_output=True).returncode == 0


_RECURSOS = {}


def _user_data(instancia):
    """El script de arranque como lo devuelve la API (fuente de datos del override); si no, el del estado."""
    leido = _RECURSOS.get("data.aws_instance.comprobar_mdr", {}).get("values", {}).get("user_data_base64")
    if leido:
        return base64.b64decode(leido).decode()
    v = instancia["values"]
    if v.get("user_data_base64"):
        return base64.b64decode(v["user_data_base64"]).decode()
    return v.get("user_data") or ""


def comprobaciones(escenario, estado):
    rs = _recursos(estado)
    _RECURSOS.clear()
    _RECURSOS.update(rs)
    tipos = {r["type"] for r in rs.values()}
    out = []

    def mira(nombre, cond):
        out.append((nombre, bool(cond)))

    mdr = rs.get("aws_instance.mdr")
    mira("instancia del MDR creada", mdr)
    if mdr:
        v = mdr["values"]
        mira("MDR sin IP pública e IMDSv2 obligatorio",
             v.get("associate_public_ip_address") is False and v["metadata_options"][0]["http_tokens"] == "required")
        mira("disco raíz cifrado", v["root_block_device"][0]["encrypted"] is True)
        ud = _user_data(mdr)
        vol = rs.get("aws_ebs_volume.traza", {}).get("values", {}).get("id", "").replace("-", "")
        api = rs.get("data.aws_instance.comprobar_mdr")
        if api is not None and not api.get("values", {}).get("user_data_base64"):
            # la fuente de datos existe pero no devolvió el script: sin él no se comprueba nada del arranque
            mira("script de arranque leído de la API (comprobar_mdr no lo devolvió)", False)
        elif len(ud) == 40 and all(c in "0123456789abcdef" for c in ud):
            mira("script de arranque: el estado solo guarda su huella (se comprueba en el simulacro)", True)
        else:
            mira("script de arranque guardado y sin errores de sintaxis (bash -n)", ud and _bash_n(ud))
            mira("el arranque busca el EBS de la traza por su id", vol and f"nvme-Amazon_Elastic_Block_Store_{vol}" in ud)
    mira("EBS de la traza cifrado", rs.get("aws_ebs_volume.traza", {}).get("values", {}).get("encrypted") is True)
    mira("destroy apagará la instancia antes de soltar el disco",
         rs.get("aws_volume_attachment.traza", {}).get("values", {}).get("stop_instance_before_detaching") is True)
    endpoints = [r["values"]["service_name"].rsplit(".", 1)[-1] for r in rs.values() if r["type"] == "aws_vpc_endpoint"]
    mira("endpoints de SSM (ssm, ssmmessages, ec2messages) y de S3",
         {"ssm", "ssmmessages", "ec2messages", "s3"} <= set(endpoints))
    politicas = [r for r in rs.values() if r["type"] == "aws_iam_role_policy"]

    if escenario == "A":
        mira("con egreso: NAT, IP elástica e internet gateway",
             {"aws_nat_gateway", "aws_eip", "aws_internet_gateway"} <= tipos)
        mira("sin secretos: ni endpoint de Secrets Manager ni política de secretos",
             "secretsmanager" not in endpoints and not any(p["values"]["name"] == "leer-secretos" for p in politicas))
        mira("sin GPU", "aws_instance.llm[0]" not in rs)
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
        perfil_gpu = rs.get("aws_iam_instance_profile.gpu", {}).get("values", {}).get("name")
        rol_gpu = rs.get("aws_iam_role.gpu", {}).get("values", {}).get("name")
        mira("la GPU usa su propio perfil IAM", llm and perfil_gpu and llm["values"]["iam_instance_profile"] == perfil_gpu)
        de_gpu = [p for p in politicas if p["values"]["role"] in (rol_gpu, rs.get("aws_iam_role.gpu", {}).get("values", {}).get("id"))]
        mira("el rol de la GPU no puede leer secretos", rol_gpu and not any("secretsmanager" in p["values"]["policy"] for p in de_gpu))
        mira("el rol de la GPU lee los dos modelos de S3",
             any("generador.gguf" in p["values"]["policy"] and "bge-m3.gguf" in p["values"]["policy"] for p in de_gpu))
        sg = rs.get("aws_security_group.llm", {}).get("values", {})
        puertos = {i["from_port"] for i in sg.get("ingress", [])}
        mira("la GPU solo abre 8080 y 8082", puertos == {8080, 8082})
        if mdr and llm:
            ip = llm["values"]["private_ip"]
            ud = _user_data(mdr)
            if not (len(ud) == 40 and all(c in "0123456789abcdef" for c in ud)):
                mira("el arranque del MDR apunta al modelo y al embedder de la GPU",
                     f"http://{ip}:8080" in ud and f"http://{ip}:8082" in ud)
    if escenario == "E":
        v = (mdr or {}).get("values", {})
        mira("laboratorio: t3.xlarge", v.get("instance_type") == "t3.xlarge")
        raiz = (v.get("root_block_device") or [{}])[0]
        mira("laboratorio: raíz de 40 GB gp3 cifrada",
             raiz.get("volume_size") == 40 and raiz.get("volume_type") == "gp3" and raiz.get("encrypted") is True)
        mira("laboratorio: el nombre lo dice", str(v.get("tags", {}).get("Name", "")).endswith("-laboratorio"))
        mira("laboratorio: sin GPU", "aws_instance.llm[0]" not in rs)
        mira("laboratorio: con egreso (NAT)", "aws_nat_gateway" in tipos)
        ud = _user_data(mdr) if mdr else ""
        mira("el arranque clona v1.9.2 y comprueba el commit", "--branch v1.9.2" in ud and "0" * 40 in ud)
        mira("el arranque instala la unidad mdr-laboratorio", "systemctl enable --now mdr-laboratorio" in ud)
        # AWS rechaza al crear la instancia un user_data de más de 16 KB.
        mira("el script de arranque cabe en 16 KB", 0 < len(ud.encode()) < 16384)
    return out


def main(argv):
    escenario, ruta = argv[1], argv[2]
    with open(ruta, encoding="utf-8") as f:
        estado = json.load(f)
    res = comprobaciones(escenario, estado)
    print(f"== {escenario}: {sum(1 for _, ok in res if ok)} de {len(res)} comprobaciones")
    for nombre, ok in res:
        print(f"   {'ok   ' if ok else 'FALLO'}  {nombre}")
    return 0 if all(ok for _, ok in res) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
