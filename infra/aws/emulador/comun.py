"""Lo común de las comprobaciones del emulador (las de cada variante están en infra/aws/<variante>/emulador/
comprobar.py). Se leen del estado que deja OpenTofu (`tofu show -json`); el script de arranque, de la
fuente de datos `data.aws_instance.comprobar` que probar.sh añade a la copia (la API lo devuelve entero;
el estado solo guarda su huella)."""
import base64
import json
import subprocess
import sys


def recursos(estado):
    """{dirección: recurso} de la raíz y de sus módulos; las del módulo común sin el prefijo `module.base.`."""
    out = {}

    def recorrer(modulo):
        for r in modulo.get("resources", []):
            out[r["address"].replace("module.base.", "", 1)] = r
        for hijo in modulo.get("child_modules", []):
            recorrer(hijo)
    recorrer(estado.get("values", {}).get("root_module", {}))
    return out


def bash_n(texto):
    return subprocess.run(["bash", "-n"], input=texto, text=True, capture_output=True).returncode == 0


def user_data(rs):
    """El script de arranque como lo devuelve la API, o None si la fuente de datos no lo devolvió."""
    leido = rs.get("data.aws_instance.comprobar", {}).get("values", {}).get("user_data_base64")
    return base64.b64decode(leido).decode() if leido else None


def comprobaciones_base(rs, instancia, nombre, mira):
    """Lo que vale para cualquier variante: la instancia, su arranque, el disco y los endpoints."""
    inst = rs.get(instancia)
    mira(f"instancia {nombre} creada", inst)
    if inst:
        v = inst["values"]
        mira(f"{nombre}: sin IP pública e IMDSv2 obligatorio",
             v.get("associate_public_ip_address") is False and v["metadata_options"][0]["http_tokens"] == "required")
        mira("disco raíz cifrado", v["root_block_device"][0]["encrypted"] is True)
        ud = user_data(rs)
        if ud is None:
            # sin el script no se comprueba nada del arranque: nunca un verde a ciegas
            mira("script de arranque leído de la API", False)
        else:
            vol = rs.get("aws_ebs_volume.traza", {}).get("values", {}).get("id", "").replace("-", "")
            mira("script de arranque guardado y sin errores de sintaxis (bash -n)", bash_n(ud))
            mira("el arranque busca el EBS de la traza por su id", vol and f"nvme-Amazon_Elastic_Block_Store_{vol}" in ud)
    mira("EBS de la traza cifrado", rs.get("aws_ebs_volume.traza", {}).get("values", {}).get("encrypted") is True)
    mira("destroy apagará la instancia antes de soltar el disco",
         rs.get("aws_volume_attachment.traza", {}).get("values", {}).get("stop_instance_before_detaching") is True)
    endpoints = [r["values"]["service_name"].rsplit(".", 1)[-1] for r in rs.values() if r["type"] == "aws_vpc_endpoint"]
    mira("endpoints de SSM (ssm, ssmmessages, ec2messages) y de S3",
         {"ssm", "ssmmessages", "ec2messages", "s3"} <= set(endpoints))
    return endpoints


def main(argv, comprobaciones):
    """python3 comprobar.py <ESCENARIO> estado.json → una línea por comprobación; código 1 si falla alguna."""
    escenario, ruta = argv[1], argv[2]
    with open(ruta, encoding="utf-8") as f:
        estado = json.load(f)
    res = comprobaciones(escenario, estado)
    print(f"== {escenario}: {sum(1 for _, ok in res if ok)} de {len(res)} comprobaciones")
    for nombre, ok in res:
        print(f"   {'ok   ' if ok else 'FALLO'}  {nombre}")
    return 0 if all(ok for _, ok in res) else 1


if __name__ == "__main__":
    sys.exit("comun.py no se ejecuta solo: usa infra/aws/<variante>/emulador/comprobar.py")
