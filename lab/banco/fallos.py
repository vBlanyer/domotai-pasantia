"""Banco de fallos del conector (fase 0 de PLAN-MANEJO-FALLOS-CONTENCION.md).

Dos modos:

    python3 -m lab.banco.fallos capturar [EQUIPO]
        NO toca ningún equipo. Desde el nodo de gestión provoca cada clase de fallo cambiando solo lo
        que usa el conector (un known_hosts o una clave temporales en /tmp del nodo, un puerto cerrado,
        una IP sin equipo, una orden que sudo permite pero falla) y guarda la salida REAL de ssh y sudo
        en prototipo/tests/fixtures/fallos_conector.json. Las pruebas del clasificador usan esas salidas:
        los patrones no se inventan. Por defecto usa api-movil, que debe estar aprovisionado.

    python3 -m lab.banco.fallos provocar|deshacer CASO EQUIPO
        Fallos que SÍ modifican un equipo, para una pasada completa del laboratorio (con el daemon):
          e1           el equipo descarta el SSH del nodo de gestión (caso E1 del banco)
          sshd         para sshd
          sin-clave    vacía el authorized_keys del conector (con copia)
          clave-host   regenera las claves del host (con copia; deshacer las restaura)
          contramedida un bucle que borra en el acto las reglas de bloqueo de 192.0.2.0/24
        Cada `provocar` tiene su `deshacer`, que deja el equipo como estaba.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

NODO = os.environ.get("TRIAJE_NODO_GESTION", "clab-banco-mdr-siem")
CLAVE, KNOWN = "/root/.ssh/triaje", "/root/.ssh/known_hosts_triaje"
SALIDA = os.path.join(os.path.dirname(__file__), "..", "..", "prototipo", "tests", "fixtures", "fallos_conector.json")
IPS = {"api-movil": "10.20.0.10", "web-banking": "10.10.0.10", "middleware": "10.40.0.10", "core-db": "10.50.0.10",
       "hsm": "10.60.0.10", "swift-alliance": "10.30.0.10", "atm": "10.210.0.10", "taquilla": "10.200.0.10",
       "fw-core": "10.0.0.1", "fw-edge": "10.0.0.254", "pagos-qr": "10.70.0.10", "auditor": "10.100.0.20"}
TMP = "/tmp/mdr-fallos"


def _nodo(linea, timeout=40):
    try:
        cp = subprocess.run(["docker", "exec", NODO, "sh", "-c", linea], capture_output=True, text=True, timeout=timeout)
        return cp.returncode, cp.stdout + cp.stderr
    except subprocess.TimeoutExpired:
        return 124, "timeout del arnés"


def _ssh(ip, remoto, clave=CLAVE, known=KNOWN, puerto=None):
    """La misma línea que usa el conector (conector.comando_ssh_clave), con piezas cambiables."""
    p = f" -p {puerto}" if puerto else ""
    return (f"ssh -n -i {clave} -o IdentitiesOnly=yes -o BatchMode=yes -o PasswordAuthentication=no "
            f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known} -o ConnectTimeout=5 "
            f"-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa{p} triaje@{ip} \"{remoto}\"")


def capturar(equipo="api-movil"):
    ip = IPS[equipo]
    rc, _ = _nodo(_ssh(ip, "sudo -S iptables -L -n"))
    if rc != 0:
        sys.exit(f"{equipo} no responde con el conector (rc={rc}): aprovisiónalo antes de capturar")
    # temporales SOLO en el nodo de gestión: una clave que el equipo no conoce y un known_hosts con otra huella
    _nodo(f"rm -rf {TMP} && mkdir -m 700 {TMP} && ssh-keygen -q -t ed25519 -N '' -f {TMP}/ajena "
          f"&& ssh-keygen -q -t ed25519 -N '' -f {TMP}/host_falso && echo \"{ip} $(cut -d' ' -f1,2 {TMP}/host_falso.pub)\" > {TMP}/known_cambiada "
          f"&& : > {TMP}/known_vacio")
    casos = [
        ("ok", "ok", _ssh(ip, "sudo -S iptables -L -n"), "comando del catálogo con todo en orden"),
        ("ok_LC", "ok", _ssh(ip, "LC_ALL=C sudo -S iptables -L -n"), "lo mismo con LC_ALL=C"),
        ("verificacion_no_esta", "no_esta", _ssh(ip, "sudo -S iptables -L -n | grep 192.0.2.99"),
         "verificación: la regla no está (grep sin coincidencias, rc 1): NO es un fallo"),
        ("F2_sin_aprovisionar", "F2", _ssh(ip, "sudo -S iptables -L -n", known=f"{TMP}/known_vacio"),
         "el known_hosts no tiene la clave de este equipo"),
        ("F2_equipo_nuevo", "F2", _ssh(IPS["pagos-qr"], "sudo -S iptables -L -n"), "pagos-qr sin dar de alta"),
        ("F3_clave_host_cambiada", "F3", _ssh(ip, "sudo -S iptables -L -n", known=f"{TMP}/known_cambiada"),
         "el known_hosts tiene OTRA clave para este equipo"),
        ("F4_clave_rechazada", "F4", _ssh(ip, "sudo -S iptables -L -n", clave=f"{TMP}/ajena"),
         "el equipo no acepta la clave del conector"),
        ("F5_conexion_rechazada", "F5", _ssh(ip, "sudo -S iptables -L -n", puerto=2222), "puerto sin sshd"),
        ("F5_sin_equipo", "F5", _ssh("10.70.0.99", "sudo -S iptables -L -n"), "IP del laboratorio sin equipo"),
        ("F5_sin_ruta", "F5", _ssh("10.99.0.10", "sudo -S iptables -L -n"), "red sin segmento en fw-core"),
        ("F6_binario_ausente", "F6", _ssh(ip, "sudo -S ss -tunap"), "acción del catálogo cuyo binario no está"),
        ("F6_fuera_del_sudoers", "F6", _ssh(ip, "sudo -S cat /etc/hostname"), "comando fuera del sudoers"),
        ("F6_fuera_del_sudoers_LC", "F6", _ssh(ip, "LC_ALL=C sudo -S cat /etc/hostname"), "lo mismo con LC_ALL=C"),
        ("F7_comando_falla", "F7", _ssh(ip, "sudo -S iptables -D INPUT -s 192.0.2.99 -j DROP"),
         "sudo lo permite (es la reversión) pero el comando falla: la regla no existe"),
    ]
    out = []
    for nombre, clase, linea, nota in casos:
        rc, salida = _nodo(linea)
        out.append({"caso": nombre, "clase": clase, "rc": rc, "salida": salida, "nota": nota})
        print(f"{nombre:28} rc={rc:<4} {salida.strip().splitlines()[-1][:90] if salida.strip() else '(sin salida)'}")
    out.append({"caso": "F9_sin_configurar", "clase": "F9", "rc": 126,
                "salida": "conector sin configurar: aprovisiona el minimo privilegio (sh lab/scripts/aprovisionar-minimo-privilegio.sh) o fija TRIAJE_SSH_MODO",
                "nota": "salida del ejecutor que rechaza (conector._ejecutor_sin_configurar)"})
    _nodo(f"rm -rf {TMP}")
    _, ver = _nodo("ssh -V 2>&1")
    datos = {"capturado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "equipo": equipo,
             "openssh_nodo": ver.strip(), "casos": out}
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print(f"guardado en {os.path.relpath(SALIDA)}")


_DESHACER = "/root/mdr-fallos-copia"
_CASOS = {
    "e1": ("iptables -C INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP 2>/dev/null || iptables -I INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP",
           "iptables -D INPUT -s 10.100.0.10 -p tcp --dport 22 -j DROP 2>/dev/null || true"),
    "sshd": ("pkill -x sshd || true", "pgrep -x sshd >/dev/null || /usr/sbin/sshd -E /var/log/banco/sshd.log"),
    "sin-clave": (f"mkdir -p {_DESHACER} && cp -p /home/triaje/.ssh/authorized_keys {_DESHACER}/authorized_keys && : > /home/triaje/.ssh/authorized_keys",
                  f"cp -p {_DESHACER}/authorized_keys /home/triaje/.ssh/authorized_keys"),
    "clave-host": (f"mkdir -p {_DESHACER}/ssh && cp -p /etc/ssh/ssh_host_* {_DESHACER}/ssh/ && rm -f /etc/ssh/ssh_host_* && ssh-keygen -A && pkill -HUP -x sshd || true",
                   f"cp -p {_DESHACER}/ssh/ssh_host_* /etc/ssh/ && pkill -HUP -x sshd || true"),
    "contramedida": ("nohup sh -c 'while true; do for r in $(iptables -S INPUT | grep -o \"192\\.0\\.2\\.[0-9]*\"); do "
                     "iptables -D INPUT -s $r -j DROP 2>/dev/null; done; sleep 0.1; done' >/dev/null 2>&1 & echo $! > /tmp/mdr-contramedida.pid",
                     "kill $(cat /tmp/mdr-contramedida.pid) 2>/dev/null; rm -f /tmp/mdr-contramedida.pid"),
}


def provocar(caso, equipo, deshacer=False):
    if caso not in _CASOS:
        sys.exit(f"caso desconocido: {caso} (casos: {', '.join(_CASOS)})")
    cmd = _CASOS[caso][1 if deshacer else 0]
    cp = subprocess.run(["docker", "exec", f"clab-banco-{equipo}", "sh", "-c", cmd], capture_output=True, text=True)
    print(f"{'deshecho' if deshacer else 'provocado'}: {caso} en {equipo} (rc={cp.returncode}) {cp.stderr.strip()[:120]}")


def _main(argv):
    if len(argv) >= 2 and argv[1] == "capturar":
        return capturar(argv[2] if len(argv) > 2 else "api-movil")
    if len(argv) == 4 and argv[1] in ("provocar", "deshacer"):
        return provocar(argv[2], argv[3], deshacer=argv[1] == "deshacer")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
