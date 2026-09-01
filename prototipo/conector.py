"""El conector: traduce la orden a un comando del catálogo y lo ejecuta por el ejecutor inyectado."""
import json, sys, re

_SEGURO = re.compile(r'^[A-Za-z0-9._:-]+\Z')   # IPs, puertos, nombres de servicio: sin metacaracteres de shell
# \Z (no $) para que un \n final no cuele -> separador de comandos en el shell remoto.

def render_comando(catalogo, accion_id, params):
    return catalogo[accion_id]["comando"].format(**params)

def _params_seguros(params):
    # además del charset: nada que empiece por "-" (evita que un valor se interprete como flag, p.ej. de iptables).
    return all(_SEGURO.match(str(v)) and not str(v).startswith("-") for v in params.values())

def _resultado(orden, comando, rc, salida, exito, idempotente, timestamp):
    return {
        "decision_id": orden.get("decision_id"), "accion_id": orden.get("accion_id"),
        "nodo": orden.get("nodo_objetivo"), "comando_ejecutado": comando,
        "codigo_salida": rc, "salida": salida, "exito": exito,
        "idempotente": idempotente, "timestamp": timestamp,
    }

def ejecutar_orden(orden, catalogo, ejecutor, timestamp):
    acc = catalogo[orden["accion_id"]]
    if not _params_seguros(orden.get("params", {})):
        return _resultado(orden, None, -1, "params rechazados: caracteres no permitidos", False, False, timestamp)
    cmd_verif = acc["verificacion"].format(**orden["params"])
    # 1. Verificar-antes-de-actuar: si ya está en el estado deseado, no reejecutar (idempotencia).
    #    Solo aplica cuando la verificación representa un estado final persistente (p.ej. una regla
    #    de iptables). Para acciones con reversion:transitoria (MATAR_CONEXION), rc0 en la
    #    verificación significa "el estado indeseado aún existe" (la conexión sigue viva), no
    #    "ya se aplicó la acción" -> nunca se salta la ejecución por idempotencia.
    transitoria = acc.get("reversion") == "transitoria"
    if not transitoria:
        rc_v, out_v = ejecutor(orden["nodo_ip"], cmd_verif)
        if rc_v == 0:
            return _resultado(orden, None, rc_v, out_v, True, True, timestamp)
    # 2. Ejecutar y volver a verificar para confirmar el efecto.
    cmd = render_comando(catalogo, orden["accion_id"], orden["params"])
    rc, out = ejecutor(orden["nodo_ip"], cmd)
    rc_v2, out_v2 = ejecutor(orden["nodo_ip"], cmd_verif)
    return _resultado(orden, cmd, rc, out, rc == 0 and rc_v2 == 0, False, timestamp)

def _main(argv):  # lee una orden de stdin y la ejecuta (frontera de proceso; futuro conector en Go)
    import os
    from prototipo import catalogo as catm
    orden = json.loads(sys.stdin.read())
    cat = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
    r = ejecutar_orden(orden, cat, ejecutor_ssh_lab, argv[1] if len(argv) > 1 else "")
    print(json.dumps(r, ensure_ascii=False))

def ejecutor_ssh_lab(nodo_ip, comando):  # el ejecutor del laboratorio (se valida en vivo, no en unittest)
    import subprocess
    ssh = ("ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "
           "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no "
           "-o PreferredAuthentications=password")
    remoto = f"echo msfadmin | sudo -S {comando}"
    cp = subprocess.run(
        ["docker", "exec", "clab-red-cliente-auditor", "sh", "-c",
         f"sshpass -p msfadmin {ssh} msfadmin@{nodo_ip} \"{remoto}\""],
        capture_output=True, text=True)
    return (cp.returncode, cp.stdout + cp.stderr)

if __name__ == "__main__":
    _main(sys.argv)
