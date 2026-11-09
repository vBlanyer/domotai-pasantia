"""Analistas de la consola: un token por persona en TRIAJE_CONSOLA_OPERADORES y, si se pide, su
cuenta SSH en el equipo MDR limitada al túnel de la consola (sin shell).

    mdr analista alta <nombre> [--clave-ssh <fichero.pub>]
    mdr analista baja <nombre>
    mdr analista lista

El token se muestra una sola vez. Tras un alta o una baja, el servicio se reinicia si está en marcha:
los tokens se leen al arrancar.
"""
import json
import os
import pwd
import re
import secrets
import subprocess
import sys

from prototipo.herramientas import entorno

GRUPO = "mdr-analistas"
MARCA = "analista MDR"                      # GECOS de las cuentas que crea esta herramienta
_NOMBRE = re.compile(r"^[a-z][a-z0-9._-]{1,31}$")
SSHD_CONF = "/etc/ssh/sshd_config.d/mdr-analistas.conf"


def _token():
    return secrets.token_hex(24)


def _guardar(ruta_env, ops):
    entorno.escribir(ruta_env, {"TRIAJE_CONSOLA_OPERADORES":
                                json.dumps(ops, separators=(",", ":"), ensure_ascii=True) if ops else None})


def lista(ruta_env):
    return sorted(set(entorno.operadores(entorno.leer(ruta_env)).values()))


def alta(ruta_env, nombre, generar=_token):
    """Da de alta a `nombre` y devuelve su token. ValueError si el nombre no vale o ya existe."""
    if not _NOMBRE.match(nombre or ""):
        raise ValueError("nombre: minúsculas, números, «.», «_» o «-», de 2 a 32, empezando por letra")
    ops = entorno.operadores(entorno.leer(ruta_env))
    if nombre in ops.values():
        raise ValueError(f"{nombre} ya tiene token: dalo de baja antes de darle uno nuevo")
    token = generar()
    ops[token] = nombre
    _guardar(ruta_env, ops)
    return token


def baja(ruta_env, nombre):
    ops = entorno.operadores(entorno.leer(ruta_env))
    quedan = {t: n for t, n in ops.items() if n != nombre}
    if len(quedan) == len(ops):
        raise ValueError(f"{nombre} no tiene token")
    _guardar(ruta_env, quedan)


def preparar_tunel(conf=SSHD_CONF, ejecutar=subprocess.run, puerto=8787):
    """Grupo `mdr-analistas` y un bloque de sshd que limita sus cuentas al túnel de la consola. Si
    sshd no acepta la configuración, se retira (nunca se deja un sshd que no arranque)."""
    if ejecutar(["getent", "group", GRUPO], capture_output=True, text=True).returncode != 0:
        ejecutar(["groupadd", "--system", GRUPO], check=False)
    with open(conf, "w", encoding="utf-8") as f:
        f.write(f"# Cuentas de analistas del MDR: solo el túnel a la consola (mdr analista).\n"
                f"Match Group {GRUPO}\n"
                f"    PermitOpen 127.0.0.1:{puerto}\n"
                f"    AllowTcpForwarding local\n"
                f"    PermitTTY no\n"
                f"    X11Forwarding no\n"
                f"    ForceCommand /usr/sbin/nologin\n")
    os.chmod(conf, 0o644)
    r = ejecutar(["sshd", "-t"], capture_output=True, text=True)
    if r.returncode != 0:
        os.unlink(conf)
        raise SystemExit(f"mdr analista: sshd rechaza la configuración y se ha retirado: {r.stderr.strip()}")
    for servicio in ("ssh", "sshd"):                          # Debian/Ubuntu y Red Hat
        if ejecutar(["systemctl", "reload", servicio], capture_output=True, text=True).returncode == 0:
            break


def crear_cuenta(nombre, clave_pub, ejecutar=subprocess.run, casa=None):
    """Cuenta del sistema para el túnel, en el grupo `mdr-analistas`, con su clave pública."""
    with open(clave_pub, encoding="utf-8") as f:
        clave = f.read().strip()
    if not re.match(r"^(ssh-(ed25519|rsa)|ecdsa-sha2-nistp\d+) [A-Za-z0-9+/=]+( .*)?$", clave) or "\n" in clave:
        raise ValueError(f"{clave_pub} no es una clave pública SSH (una línea «ssh-ed25519 AAAA…»)")
    casa = casa or f"/home/{nombre}"
    if ejecutar(["id", nombre], capture_output=True, text=True).returncode == 0:
        raise SystemExit(f"mdr analista: ya existe una cuenta {nombre} en este equipo; usa otro nombre")
    ejecutar(["useradd", "--create-home", "--home-dir", casa, "--comment", MARCA, "--groups", GRUPO,
              "--shell", "/usr/sbin/nologin", nombre], check=True)
    ssh = os.path.join(casa, ".ssh")
    os.makedirs(ssh, mode=0o700, exist_ok=True)
    with open(os.path.join(ssh, "authorized_keys"), "w", encoding="utf-8") as f:
        f.write(clave + "\n")
    os.chmod(os.path.join(ssh, "authorized_keys"), 0o600)
    ejecutar(["chown", "-R", f"{nombre}:{nombre}", ssh], check=False)


def borrar_cuenta(nombre, ejecutar=subprocess.run):
    """Borra la cuenta solo si la creó esta herramienta (su GECOS lo dice). True si la borró."""
    try:
        if pwd.getpwnam(nombre).pw_gecos != MARCA:
            return False
    except KeyError:
        return False
    ejecutar(["userdel", "--remove", nombre], check=False)
    return True


def _reiniciar_si_activo(ejecutar=subprocess.run):
    r = ejecutar(["systemctl", "try-restart", "mdr-triaje"], capture_output=True, text=True)
    return r.returncode == 0


def _main(argv):
    ruta = os.environ.get("MDR_ENV", "/etc/mdr/triaje.env")
    if not argv or argv[0] not in ("alta", "baja", "lista"):
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    orden, resto = argv[0], argv[1:]
    if orden == "lista":
        nombres = lista(ruta)
        print("\n".join(nombres) if nombres else "ningún analista dado de alta")
        return 0
    if os.geteuid() != 0:
        print("mdr analista: ejecútalo con sudo", file=sys.stderr)
        return 1
    if not resto:
        print(f"mdr analista {orden}: indica el nombre", file=sys.stderr)
        return 2
    nombre = resto[0]
    try:
        if orden == "alta":
            clave = resto[resto.index("--clave-ssh") + 1] if "--clave-ssh" in resto else None
            if clave:                                         # primero lo que puede fallar
                preparar_tunel(puerto=int(entorno.leer(ruta).get("TRIAJE_WEB_PUERTO") or 8787))
                crear_cuenta(nombre, clave)
            token = alta(ruta, nombre)
            print(f"Token de {nombre} (se muestra solo ahora; entrégaselo por un canal seguro):\n\n  {token}\n")
            if clave:
                print(f"Cuenta SSH {nombre} creada, limitada al túnel: ssh -N -L 8787:127.0.0.1:8787 {nombre}@<equipo-mdr>")
        else:
            baja(ruta, nombre)
            print(f"{nombre}: token retirado" + (" y cuenta SSH borrada" if borrar_cuenta(nombre) else ""))
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print(f"mdr analista: {e}", file=sys.stderr)
        return 1
    if _reiniciar_si_activo():
        print("Servicio reiniciado para aplicar el cambio (si la automatización estaba en pausa, ya no lo está).")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
