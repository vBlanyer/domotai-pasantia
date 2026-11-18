"""Comprobaciones del escenario de la variante laboratorio contra AWS Emulator (lo lanza
infra/aws/emulador/probar.sh laboratorio). Lo común está en infra/aws/emulador/comun.py.

    python3 comprobar.py E estado.json
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "emulador"))
import comun  # noqa: E402

# Escenarios que crean algo (F se rechaza en el plan); los usa también inventario.py.
ESCENARIOS = {
    "E": "La variante laboratorio: una máquina (t3.xlarge, con egreso) que levanta el banco, Wazuh y el MDR (>= 1.9.2). No se conecta a ningún cliente.",
}


def comprobaciones(escenario, estado):
    rs = comun.recursos(estado)
    tipos = {r["type"] for r in rs.values()}
    out = []

    def mira(nombre, cond):
        out.append((nombre, bool(cond)))

    comun.comprobaciones_base(rs, "aws_instance.laboratorio", "del laboratorio", mira)
    if escenario == "E":
        v = rs.get("aws_instance.laboratorio", {}).get("values", {})
        mira("laboratorio: t3.xlarge", v.get("instance_type") == "t3.xlarge")
        raiz = (v.get("root_block_device") or [{}])[0]
        mira("laboratorio: raíz de 40 GB gp3 cifrada",
             raiz.get("volume_size") == 40 and raiz.get("volume_type") == "gp3" and raiz.get("encrypted") is True)
        mira("laboratorio: el nombre lo dice", str(v.get("tags", {}).get("Name", "")).endswith("-laboratorio"))
        mira("laboratorio: sin GPU", not any(r["type"] == "aws_instance" and "llm" in a for a, r in rs.items()))
        mira("laboratorio: con egreso (NAT)", "aws_nat_gateway" in tipos)
        ud = comun.user_data(rs) or ""
        mira("el arranque clona v1.9.2 y comprueba el commit", "--branch v1.9.2" in ud and "0" * 40 in ud)
        mira("el arranque instala la unidad mdr-laboratorio", "systemctl enable --now mdr-laboratorio" in ud)
        # AWS rechaza al crear la instancia un user_data de más de 16 KB.
        mira("el script de arranque cabe en 16 KB", 0 < len(ud.encode()) < 16384)
    return out


if __name__ == "__main__":
    sys.exit(comun.main(sys.argv, comprobaciones))
