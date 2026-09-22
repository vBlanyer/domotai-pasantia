"""El conector: traduce la orden a un comando del catálogo y lo ejecuta por el ejecutor inyectado."""
import json, os, re, sys

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
    r = ejecutar_orden(orden, cat, ejecutor_por_defecto(), argv[1] if len(argv) > 1 else "")
    print(json.dumps(r, ensure_ascii=False))

# ------------------------------------------------------------------ ejecutores SSH --
# Los dos ejecutan desde el auditor (el nodo de gestion) hacia el nodo objetivo. El primero es el
# del laboratorio tal como nacio: usuario y contrasena por defecto de Metasploitable, contrasena
# en el codigo y por la tuberia de sudo, y sin verificar la clave del host. Sirve para el
# laboratorio y para nada mas. El segundo es el diseno de produccion: usuario dedicado, clave en
# vez de contrasena, host conocido, y sudo restringido al sudoers que genera el catalogo
# (catalogo.sudoers), de modo que la frontera de privilegio en el nodo es exactamente el catalogo
# cerrado de acciones. Se aprovisiona con lab/scripts/aprovisionar-minimo-privilegio.sh.

_AUDITOR = "clab-red-cliente-auditor"   # valor por defecto: la red pequena

def nodo_gestion():
    """Contenedor desde el que el conector lanza el SSH (el nodo de gestion del cliente). Por defecto
    el auditor de la red pequena; el banco usa TRIAJE_NODO_GESTION=clab-banco-mdr-siem (H3)."""
    return os.environ.get("TRIAJE_NODO_GESTION", _AUDITOR)

def _ssh_en_auditor(linea):
    import subprocess
    cp = subprocess.run(["docker", "exec", nodo_gestion(), "sh", "-c", linea], capture_output=True, text=True)
    return (cp.returncode, cp.stdout + cp.stderr)

def ejecutor_ssh_lab(nodo_ip, comando):  # el ejecutor del laboratorio (se valida en vivo, no en unittest)
    ssh = ("ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "
           "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAuthentication=no "
           "-o PreferredAuthentications=password")
    remoto = f"echo msfadmin | sudo -S {comando}"
    return _ssh_en_auditor(f"sshpass -p msfadmin {ssh} msfadmin@{nodo_ip} \"{remoto}\"")

SSH_USUARIO = os.environ.get("TRIAJE_SSH_USUARIO", "triaje")
SSH_CLAVE = os.environ.get("TRIAJE_SSH_CLAVE", "/root/.ssh/triaje")
SSH_KNOWN_HOSTS = os.environ.get("TRIAJE_SSH_KNOWN_HOSTS", "/root/.ssh/known_hosts_triaje")

def comando_ssh_clave(nodo_ip, comando, usuario=SSH_USUARIO, clave=SSH_CLAVE, known_hosts=SSH_KNOWN_HOSTS):
    """La linea que ejecuta el auditor. Separada del ejecutor para poder probar lo que importa sin
    laboratorio: que no viaje ninguna contrasena, que la clave del host se verifique contra un
    fichero conocido, que ssh no pueda quedarse preguntando (BatchMode) y que sudo falle en vez
    de esperar una contrasena (ssh -n cierra la entrada; el sudo 1.6 del objetivo no tiene -n)."""
    # ssh -n cierra la entrada de TODA la sesion: asi sudo -S encuentra EOF y falla en vez de
    # esperar, sin pegar un '</dev/null' al comando, que en una verificacion con tuberia
    # ('iptables -L -n | grep ip') se lo llevaria el grep y dejaria la verificacion siempre falsa.
    ssh = (f"ssh -n -i {clave} -o IdentitiesOnly=yes -o BatchMode=yes -o PasswordAuthentication=no "
           f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known_hosts} -o ConnectTimeout=5 "
           "-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa")
    remoto = f"sudo -S {comando}"
    return f"{ssh} {usuario}@{nodo_ip} \"{remoto}\""

def ejecutor_ssh_clave(nodo_ip, comando):
    return _ssh_en_auditor(comando_ssh_clave(nodo_ip, comando))

def _clave_aprovisionada():
    import subprocess
    try:
        return subprocess.run(["docker", "exec", nodo_gestion(), "test", "-f", SSH_CLAVE],
                              capture_output=True).returncode == 0
    except OSError:
        return False

def ejecutor_por_defecto(escribir=print):
    """TRIAJE_SSH_MODO=clave|password decide; sin ella, la clave si esta aprovisionada en el auditor
    y, si no, el ejecutor del laboratorio con un aviso. No se cae de clave a contrasena en silencio:
    eso escondería una configuracion rota detras de una credencial que no deberia existir."""
    modo = os.environ.get("TRIAJE_SSH_MODO")
    if modo == "password":
        return ejecutor_ssh_lab
    if modo == "clave" or _clave_aprovisionada():
        return ejecutor_ssh_clave
    escribir("[aviso] conector con la contrasena del laboratorio: aprovisiona el minimo privilegio con "
             "sh lab/scripts/aprovisionar-minimo-privilegio.sh")
    return ejecutor_ssh_lab

if __name__ == "__main__":
    _main(sys.argv)
