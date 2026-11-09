"""Conectividad del conector con cada equipo, editable desde la consola sin tocar código.

Tres piezas, todas sin efectos salvo a través de un `correr(args, entrada=None) -> (rc, salida)`
inyectable (el real ejecuta en el nodo de gestión o en el host, según el modo del conector):

- AJUSTES operativos: usuario por defecto y, por equipo (clave = su IP), puerto y usuario. Viven en
  un YAML aparte (como el overlay de Políticas) que el conector lee por encima de las variables de
  entorno. Todo valor se valida al leer y al escribir: lo que no valida se ignora (fail-closed: un
  fichero roto no inventa usuarios ni puertos).
- PRUEBA de conexión: entrar y ejecutar un comando del catálogo (sudo permitido) y otro fuera de él
  (sudo debe denegarlo). La salida de ssh se clasifica (clave del host cambiada, sin aprovisionar, sin
  acceso…). La salida del comando prohibido NUNCA se devuelve.
- CLAVE DEL HOST fijada (known_hosts): huellas fijadas, huella que presenta el equipo y aceptación de
  una clave nueva SOLO si es la misma huella que el analista vio y confirmó.

La clave PRIVADA no se lee ni se devuelve nunca: solo su huella y la clave pública.
"""
import ipaddress
import os
import re
import tempfile

import yaml

_USUARIO = re.compile(r"^[a-z_][a-z0-9_-]{0,31}\Z")
_VACIO = {"usuario_defecto": None, "equipos": {}}


def validar_puerto(v):
    """Puerto TCP 1..65535 (int o texto de dígitos); None = sin ajuste. ValueError si no vale."""
    if v is None:
        return None
    if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, str) and v.isdigit())):
        raise ValueError("puerto inválido")
    n = int(v)
    if not 1 <= n <= 65535:
        raise ValueError("puerto fuera de rango")
    return n


def validar_usuario(v):
    """Nombre de usuario POSIX conservador (va en la línea de ssh): None = sin ajuste."""
    if v is None:
        return None
    if not isinstance(v, str) or not _USUARIO.match(v):
        raise ValueError("usuario inválido")
    return v


def _ip_ok(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except (ValueError, TypeError):
        return False


def cargar(ruta):
    """Ajustes saneados: {"usuario_defecto": str|None, "equipos": {ip: {"nombre"?, "puerto"?, "usuario"?}}}."""
    try:
        with open(ruta, encoding="utf-8") as f:
            bruto = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {"usuario_defecto": None, "equipos": {}}
    if not isinstance(bruto, dict):
        return {"usuario_defecto": None, "equipos": {}}
    try:
        defecto = validar_usuario(bruto.get("usuario_defecto"))
    except ValueError:
        defecto = None
    equipos = {}
    for ip, v in (bruto.get("equipos") or {}).items() if isinstance(bruto.get("equipos"), dict) else []:
        if not _ip_ok(str(ip)) or not isinstance(v, dict):
            continue
        e = {}
        if isinstance(v.get("nombre"), str):
            e["nombre"] = v["nombre"]
        for campo, validar in (("puerto", validar_puerto), ("usuario", validar_usuario)):
            try:
                val = validar(v.get(campo))
            except ValueError:
                val = None
            if val is not None:
                e[campo] = val
        if "puerto" in e or "usuario" in e:
            equipos[str(ip)] = e
    return {"usuario_defecto": defecto, "equipos": equipos}


def con_cambio(ajustes, ip, nombre, puerto, usuario):
    """Ajustes nuevos con el puerto/usuario de `ip` (None = quitar ese ajuste). Valida."""
    if not _ip_ok(ip):
        raise ValueError("ip inválida")
    puerto, usuario = validar_puerto(puerto), validar_usuario(usuario)
    equipos = {k: dict(v) for k, v in (ajustes.get("equipos") or {}).items()}
    e = {"nombre": nombre} if nombre else {}
    if puerto is not None:
        e["puerto"] = puerto
    if usuario is not None:
        e["usuario"] = usuario
    if "puerto" in e or "usuario" in e:
        equipos[ip] = e
    else:
        equipos.pop(ip, None)
    return {"usuario_defecto": ajustes.get("usuario_defecto"), "equipos": equipos}


def guardar(ruta, ajustes):
    """Escritura atómica (temporal en el mismo directorio + os.replace), permisos 0600."""
    directorio = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=directorio, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump({"usuario_defecto": ajustes.get("usuario_defecto"), "equipos": ajustes.get("equipos") or {}},
                           f, allow_unicode=True, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    _cache.clear()


_cache = {}


def ajustes_de(ip, ruta=None):
    """(usuario, puerto) para conectar con `ip`; None = lo que diga el conector por defecto. La ruta
    es TRIAJE_CONECTIVIDAD (la fija el daemon); se relee solo si el fichero cambió."""
    ruta = ruta or os.environ.get("TRIAJE_CONECTIVIDAD")
    if not ruta:
        return None, None
    try:
        mtime = os.stat(ruta).st_mtime_ns
    except OSError:
        return None, None
    if _cache.get("clave") != (ruta, mtime):
        _cache.update(clave=(ruta, mtime), datos=cargar(ruta))
    a = _cache["datos"]
    e = a["equipos"].get(ip) or {}
    return e.get("usuario") or a.get("usuario_defecto"), e.get("puerto")


# ---------------------------------------------------------------------------- prueba de conexión --
# Un comando del catálogo (el listado que usan las verificaciones) y uno claramente fuera de él: el
# mismo par que comprueba lab/scripts/aprovisionar-minimo-privilegio.sh al terminar.
COMANDO_PERMITIDO = "iptables -L -n"
# Testigo de «sudo deniega lo que está fuera del catálogo»: un comando que NO está en ningún sudoers
# generado y que no lee ni cambia nada. Si sudo lo permite, el privilegio no es el mínimo; si se
# ejecutara, no pasaría ningún dato del equipo por la memoria del daemon (antes era `cat /etc/shadow`).
COMANDO_PROHIBIDO = "true"


def diagnosticar(rc, salida):
    s = (salida or "").lower()
    if rc == 0:
        return "ok"
    if "remote host identification has changed" in s:
        return "host_cambiada"
    if "host key verification failed" in s or "no " in s and "host key is known" in s:
        return "sin_fijar"
    if "permission denied (publickey" in s:
        return "sin_clave"
    if rc in (124, 127) or any(t in s for t in ("connection refused", "timed out", "no route to host",
                                                  "could not resolve", "connection closed", "network is unreachable")):
        return "sin_acceso"
    return "fallo"


_ESTADO = {"host_cambiada": "host_cambiada", "sin_fijar": "sin_aprovisionar", "sin_clave": "sin_aprovisionar",
           "sin_acceso": "sin_acceso", "fallo": "fallo"}
_TEXTO = {"host_cambiada": "la clave del host no coincide con la fijada",
          "sin_fijar": "no hay clave del host fijada para este equipo",
          "sin_clave": "el equipo no acepta la clave del conector",
          "sin_acceso": "no se pudo conectar (puerto cerrado, sin ruta o sin respuesta)",
          "fallo": "el comando del catálogo falló"}


def probar(ejecutor, ip, permitido=None, listar=None, esperadas=None):
    """Prueba de conexión con el `ejecutor` del conector. Devuelve {ok, estado, pasos[, reglas]}.

    Con `listar` (un ejecutor SIN sudo) y `esperadas` (las reglas del papel del equipo), añade la
    comprobación de deriva: lo que sudo permite de verdad frente a lo esperado. Sobrar algo es
    privilegio de más; faltar algo solo avisa (binario no instalado o regla quitada a mano)."""
    pasos = []
    rc, out = ejecutor(ip, permitido or COMANDO_PERMITIDO)
    d = diagnosticar(rc, out)
    if d != "ok":
        pasos.append({"paso": "entra y ejecuta un comando del catálogo", "ok": False, "detalle": _TEXTO[d]})
        return {"ok": False, "estado": _ESTADO[d], "pasos": pasos}
    pasos.append({"paso": "entra y ejecuta un comando del catálogo", "ok": True,
                  "detalle": "clave del host, entrada con la clave del conector y sudo del catálogo: correctos"})
    rc2, out2 = ejecutor(ip, COMANDO_PROHIBIDO)
    if rc2 == 0:
        pasos.append({"paso": "sudo deniega lo que está fuera del catálogo", "ok": False,
                      "detalle": "sudo permitió un comando fuera del catálogo: el privilegio no es el mínimo"})
        return {"ok": False, "estado": "privilegio_de_mas", "pasos": pasos}
    d2 = diagnosticar(rc2, out2)
    if d2 in ("host_cambiada", "sin_fijar", "sin_clave", "sin_acceso"):
        pasos.append({"paso": "sudo deniega lo que está fuera del catálogo", "ok": False, "detalle": _TEXTO[d2]})
        return {"ok": False, "estado": _ESTADO[d2], "pasos": pasos}
    pasos.append({"paso": "sudo deniega lo que está fuera del catálogo", "ok": True, "detalle": "denegado, como debe"})
    if listar is None or esperadas is None:
        return {"ok": True, "estado": "verificada", "pasos": pasos}
    rc3, out3 = listar(ip, "sudo -S -l")
    if rc3 != 0:
        pasos.append({"paso": "lo que sudo permite coincide con su papel", "ok": True,
                      "detalle": "no se pudo listar (sudo pide contraseña para listar): sin comprobar"})
        return {"ok": True, "estado": "verificada", "pasos": pasos, "reglas": {"estado": "sin_comprobar", "sobran": [], "faltan": []}}
    cmp = comparar_reglas(esperadas, reglas_de_sudo_l(out3))
    if cmp["sobran"]:
        pasos.append({"paso": "lo que sudo permite coincide con su papel", "ok": False,
                      "detalle": f"sudo permite {len(cmp['sobran'])} regla(s) que su papel no incluye"})
        return {"ok": False, "estado": "privilegio_de_mas", "pasos": pasos, "reglas": cmp}
    pasos.append({"paso": "lo que sudo permite coincide con su papel", "ok": True,
                  "detalle": (f"{len(esperadas) - len(cmp['faltan'])} de {len(esperadas)} reglas presentes; "
                              f"faltan {len(cmp['faltan'])} (binario no instalado o regla quitada)") if cmp["faltan"]
                  else f"{len(esperadas)} reglas esperadas, {len(esperadas)} encontradas"})
    return {"ok": True, "estado": "verificada", "pasos": pasos, "reglas": cmp}


# --------------------------------------------------------------------- deriva del sudoers --
def _norm(binario, args):
    return (os.path.basename(binario), " ".join((args or "").split()))


def reglas_de_sudo_l(texto):
    """[(binario, args)] de la salida de `sudo -l` del usuario del conector (solo reglas NOPASSWD como
    root; el binario por su nombre, sin ruta, para comparar con el catálogo)."""
    out = []
    for linea in (texto or "").splitlines():
        if "NOPASSWD:" not in linea:
            continue
        for cmd in linea.split("NOPASSWD:", 1)[1].split(","):
            partes = cmd.strip().split(None, 1)
            if partes:
                out.append(_norm(partes[0], partes[1] if len(partes) > 1 else ""))
    return out


def comparar_reglas(esperadas, encontradas):
    """{"estado": coinciden|sobran|faltan, "sobran": [...], "faltan": [...]} con las reglas como texto."""
    esp = {_norm(b, a) for b, a in esperadas}
    enc = set(encontradas)
    texto = lambda r: f"{r[0]} {r[1]}".strip()
    sobran = sorted(texto(r) for r in enc - esp)
    faltan = sorted(texto(r) for r in esp - enc)
    return {"estado": "sobran" if sobran else "faltan" if faltan else "coinciden", "sobran": sobran, "faltan": faltan}


# ------------------------------------------------------------ última prueba, en disco --
def _escribir_json(ruta, datos):
    import json
    directorio = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=directorio, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _leer_json(ruta):
    import json
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def cargar_pruebas(ruta):
    """{ip: última prueba} guardadas (sobreviven al reinicio del daemon)."""
    return {k: v for k, v in _leer_json(ruta).items() if _ip_ok(k) and isinstance(v, dict)} if ruta else {}


def guardar_pruebas(ruta, pruebas):
    if ruta:
        _escribir_json(ruta, pruebas)


# ------------------------------------------------------- rotación de la clave del conector --
# Tres fases sin credenciales de administrador: el usuario del conector es dueño de su propio
# authorized_keys en cada equipo. Mientras dura, el conector ofrece las DOS claves (la actual y la
# nueva), así ningún equipo pierde el acceso a medias.
_CLAVE_PUBLICA = re.compile(r"^(ssh-ed25519|ssh-rsa) [A-Za-z0-9+/]+={0,3}( [A-Za-z0-9._@-]{1,64})?\Z")


def clave_publica_valida(linea):
    """La línea de clave pública, limpia, si es segura para escribirla en un comando remoto; si no, None."""
    linea = (linea or "").strip()
    return linea if _CLAVE_PUBLICA.match(linea) else None


def cuerpo_clave(linea):
    campos = (linea or "").split()
    return campos[1] if len(campos) > 1 else None


def cmd_anadir_clave(publica):
    """Comando remoto (como el usuario del conector, sin sudo) que añade `publica` a su authorized_keys
    si no está. Sin `$`: va dentro de comillas dobles en la línea del nodo de gestión."""
    k = clave_publica_valida(publica)
    if not k:
        raise ValueError("clave pública inválida")
    return (f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
            f"(grep -qF '{cuerpo_clave(k)}' ~/.ssh/authorized_keys || echo '{k}' >> ~/.ssh/authorized_keys) && "
            f"chmod 600 ~/.ssh/authorized_keys")


def cmd_quitar_clave(cuerpo_viejo, cuerpo_nuevo):
    """Quita la clave vieja SOLO si la nueva ya está (nunca deja el equipo sin ninguna)."""
    for c in (cuerpo_viejo, cuerpo_nuevo):
        if not c or not re.match(r"^[A-Za-z0-9+/]+={0,3}\Z", c):
            raise ValueError("clave inválida")
    return (f"grep -qF '{cuerpo_nuevo}' ~/.ssh/authorized_keys && "
            f"grep -vF '{cuerpo_viejo}' ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.mdr && "
            f"mv ~/.ssh/authorized_keys.mdr ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys")


def ruta_rotacion(ruta_ajustes=None):
    ruta_ajustes = ruta_ajustes or os.environ.get("TRIAJE_CONECTIVIDAD")
    return os.path.join(os.path.dirname(os.path.abspath(ruta_ajustes)), "conectividad-rotacion.json") if ruta_ajustes else None


def cargar_rotacion(ruta=None):
    """Estado de la rotación en curso, o None."""
    ruta = ruta or ruta_rotacion()
    d = _leer_json(ruta) if ruta else {}
    return d if d.get("estado") == "en_curso" else None


def guardar_rotacion(ruta, estado):
    if estado is None:
        try:
            os.unlink(ruta)
        except OSError:
            pass
    else:
        _escribir_json(ruta, estado)


# ------------------------------------------------------------------ paquete de alta --
RUTAS_TIPICAS = {"iptables": "/usr/sbin/iptables", "ss": "/usr/bin/ss", "ps": "/usr/bin/ps", "ip": "/usr/sbin/ip",
                 "timeout": "/usr/bin/timeout", "tc": "/usr/sbin/tc", "service": "/usr/sbin/service",
                 "passwd": "/usr/bin/passwd", "reboot": "/usr/sbin/reboot", "ping": "/usr/bin/ping",
                 "restaurar": "/usr/local/sbin/restaurar"}


def _sq(texto):
    """Comillas simples de shell (los valores ya vienen validados; esto es el cinturón)."""
    return "'" + str(texto).replace("'", "'\\''") + "'"


def paquete(formato, equipo, usuario, publica, reglas, generado):
    """Paquete de alta de un equipo: «script» (sh idempotente que resuelve las rutas en el propio
    equipo), «ansible» o «sudoers» (rutas típicas de Debian/Ubuntu). Solo lleva la clave PÚBLICA.
    Devuelve (nombre_fichero, contenido)."""
    if not _USUARIO.match(usuario or ""):
        raise ValueError("usuario inválido")
    k = clave_publica_valida(publica)
    if not k:
        raise ValueError("clave pública del conector no disponible")
    nombre = equipo["nombre"]
    papel = equipo.get("papel") or "sin papel (catálogo completo)"
    listas = " · ".join(x for x in (f"servicios: {', '.join(equipo.get('servicios') or [])}" if equipo.get("servicios") else "",
                                    "cuentas: cualquiera salvo las del sistema" if equipo.get("cuentas_cualquiera")
                                    else f"cuentas: {', '.join(equipo.get('cuentas') or [])}" if equipo.get("cuentas") else "") if x)
    cab = f"Alta de {nombre} en el MDR · generado el {generado}"
    if formato == "sudoers":
        lineas = [f"# {cab}", f"# Papel: {papel}{' · ' + listas if listas else ''}",
                  "# Rutas típicas de Debian/Ubuntu: compruébalas en el equipo (command -v) antes de instalarlo.",
                  *[f"{usuario} ALL=(root) NOPASSWD: {RUTAS_TIPICAS.get(b, '/usr/bin/' + b)} {a}".rstrip() for b, a in reglas]]
        return f"mdr-{usuario}.sudoers", "\n".join(lineas) + "\n"
    if formato == "ansible":
        sud = "\n".join(f"          {usuario} ALL=(root) NOPASSWD: {RUTAS_TIPICAS.get(b, '/usr/bin/' + b)} {a}".rstrip() for b, a in reglas)
        return f"alta-{nombre}.yml", (
            f"# {cab}\n# Papel: {papel}{' · ' + listas if listas else ''}. Rutas típicas de Debian/Ubuntu: revísalas.\n"
            f"- name: Alta de {nombre} en el MDR\n  hosts: {nombre}\n  become: true\n  tasks:\n"
            f"    - name: Usuario del conector, sin contraseña (solo clave)\n"
            f"      ansible.builtin.user: {{ name: {usuario}, shell: /bin/sh, password: '*' }}\n"
            f"    - name: Clave pública del conector\n"
            f"      ansible.posix.authorized_key: {{ user: {usuario}, key: \"{k}\" }}\n"
            f"    - name: Sudo limitado a su papel\n"
            f"      ansible.builtin.copy:\n        dest: /etc/sudoers.d/mdr-{usuario}\n        mode: \"0440\"\n"
            f"        validate: visudo -cf %s\n        content: |\n          # Generado por el MDR. No editar a mano.\n{sud}\n"
            f"    - name: Huella de la clave del host (dictala en la plataforma)\n"
            f"      ansible.builtin.command: ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub\n      changed_when: false\n")
    if formato != "script":
        raise ValueError("formato desconocido")
    reglas_sh = "\n".join(f"regla {_sq(b)} {_sq(a)}" for b, a in reglas)
    return f"alta-{nombre}.sh", f"""#!/bin/sh
# {cab}
# Papel: {papel}{' · ' + listas if listas else ''}
# Ejecútalo UNA vez como root en {nombre} ({equipo.get('ip')}). Es idempotente y no contiene ningún secreto:
# solo la clave PÚBLICA del conector. Al final imprime la huella de la clave del host para la plataforma.
set -eu
U={usuario}
# Portable (Debian/Ubuntu, RHEL y equipos mínimos con BusyBox): useradd o adduser, usermod o la línea
# del shadow, y el directorio del usuario leído de /etc/passwd.
if ! id "$U" >/dev/null 2>&1; then
  if command -v useradd >/dev/null 2>&1; then useradd -m -s /bin/sh "$U"; else adduser -D -s /bin/sh "$U"; fi
fi
# sin contraseña válida ('*'), no bloqueada ('!'): OpenSSH sin PAM rechaza una cuenta bloqueada aunque la clave valga
if command -v usermod >/dev/null 2>&1; then usermod -p '*' "$U"; else sed -i "s/^$U:[^:]*:/$U:*:/" /etc/shadow; fi
H=$(awk -F: -v u="$U" '$1 == u {{ print $6 }}' /etc/passwd)
install -d -m 700 -o "$U" -g "$U" "$H/.ssh"
K={_sq(k)}
touch "$H/.ssh/authorized_keys"
grep -qxF "$K" "$H/.ssh/authorized_keys" || echo "$K" >> "$H/.ssh/authorized_keys"
chown "$U:$U" "$H/.ssh/authorized_keys"; chmod 600 "$H/.ssh/authorized_keys"
T=$(mktemp)
regla() {{
  b=$(command -v "$1" 2>/dev/null || true)
  if [ -n "$b" ]; then echo "$U ALL=(root) NOPASSWD: $b $2" >> "$T"
  else echo "  aviso: $1 no está instalado; se omite la regla «$1 $2»" >&2; fi
}}
echo "# Generado por el MDR para {nombre}. No editar a mano: se regenera desde la plataforma." > "$T"
{reglas_sh}
visudo -cf "$T" >/dev/null
# Sustituye cualquier sudoers anterior que da permisos SOLO al usuario del conector (el de este paquete,
# el del aprovisionamiento del laboratorio o uno añadido a mano): sudo suma todos los ficheros, y uno
# viejo dejaría permitido lo que el papel ya quitó. Se aparta con copia en /root, no se borra. Un fichero
# que mezcla reglas de otros usuarios no se toca: solo se avisa.
for f in /etc/sudoers.d/*; do
  [ -f "$f" ] && [ "$f" != "/etc/sudoers.d/mdr-$U" ] || continue
  tiene=$(grep -c "^$U[[:space:]]" "$f" || true)
  otras=$(grep -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' "$f" | grep -vc "^$U[[:space:]]" || true)
  if [ "$tiene" -gt 0 ] && [ "$otras" -eq 0 ]; then
    mv "$f" "/root/mdr-sudoers-anterior.$(basename "$f")"; echo "  sudoers anterior apartado (copia en /root): $f"
  elif [ "$tiene" -gt 0 ]; then
    echo "  aviso: $f da permisos a $U junto a reglas de otros usuarios; revísalo a mano" >&2
  fi
done
# Equipos antiguos (sudo sin sudoers.d): el aprovisionamiento clásico deja un bloque entre marcas en /etc/sudoers.
if grep -q '^# >>> conector-triaje' /etc/sudoers 2>/dev/null; then
  cp -p /etc/sudoers /root/mdr-sudoers-anterior.sudoers
  sed -i '/^# >>> conector-triaje/,/^# <<< conector-triaje/d' /etc/sudoers && visudo -c >/dev/null
  echo "  bloque anterior del conector quitado de /etc/sudoers (copia en /root)"
fi
install -m 440 -o root -g root "$T" /etc/sudoers.d/mdr-$U
rm -f "$T"
echo "Alta lista. Huella de la clave del host (compárala en la plataforma):"
for f in /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_rsa_key.pub; do [ -f "$f" ] && ssh-keygen -lf "$f" || true; done
"""


# ------------------------------------------------------------------------------ clave del host --
# Las huellas se calculan aquí (SHA256 del blob de la clave, en base64 sin relleno: lo mismo que
# `ssh-keygen -l`), leyendo los ficheros con `cat`: el nodo de gestión no tiene por qué traer
# ssh-keygen ni ssh-keyscan (el del banco solo tiene el cliente ssh).
import base64
import hashlib

_TIPOS = {"ssh-ed25519": "ED25519", "ssh-rsa": "RSA", "ecdsa-sha2-nistp256": "ECDSA",
          "ecdsa-sha2-nistp384": "ECDSA", "ecdsa-sha2-nistp521": "ECDSA", "ssh-dss": "DSA"}


class HuellaDistinta(Exception):
    """El equipo presenta otra huella que la que el analista confirmó: no se escribe nada."""


def _huella_blob(b64):
    try:
        crudo = base64.b64decode(b64, validate=True)
    except (ValueError, TypeError):
        return None
    return "SHA256:" + base64.b64encode(hashlib.sha256(crudo).digest()).decode().rstrip("=")


def huella_de(linea):
    """(huella, tipo) de una línea de clave pública («tipo base64 comentario») o de known_hosts
    («hosts tipo base64»); (None, None) si no es una clave."""
    campos = (linea or "").split()
    for i, c in enumerate(campos):
        if c in _TIPOS and i + 1 < len(campos):
            h = _huella_blob(campos[i + 1])
            return (h, _TIPOS[c]) if h else (None, None)
    return None, None


def _host_de(campo):
    m = re.match(r"^\[([^\]]+)\]:\d+$", campo)
    return m.group(1) if m else campo


def claves_de_known_hosts(texto):
    """{ip: [(tipo, huella)]} en el orden del fichero (sin hosts con hash ni marcadores)."""
    r = {}
    for linea in (texto or "").splitlines():
        if not linea.strip() or linea.startswith(("#", "|", "@")):
            continue
        huella, tipo = huella_de(linea)
        if not huella:
            continue
        for h in linea.split()[0].split(","):
            r.setdefault(_host_de(h), []).append((tipo, huella))
    return r


def _preferida(claves):
    """La huella a enseñar: la ed25519 si la hay; si no, la primera."""
    return next((h for t, h in claves if t == "ED25519"), claves[0][1] if claves else None)


def huellas_fijadas(texto):
    """{ip: huella a enseñar} de un known_hosts."""
    return {ip: _preferida(cs) for ip, cs in claves_de_known_hosts(texto).items()}


def reemplazar_host(texto, ip, nuevas):
    """known_hosts sin ninguna entrada de `ip` (con o sin puerto) y con las `nuevas` al final."""
    quedan = []
    for linea in (texto or "").splitlines():
        hosts = linea.split(" ", 1)[0].split(",") if linea.strip() and not linea.startswith("#") else []
        if any(_host_de(h) == ip for h in hosts):
            continue
        quedan.append(linea)
    return "\n".join(quedan + list(nuevas)) + "\n"


def _no_existe(rc, out):
    return rc in (126, 127) or "not found" in (out or "").lower()


def escanear(ip, puerto, correr):
    """Líneas de known_hosts con la clave que presenta ahora el equipo. Con ssh-keyscan si existe; si
    no, con el propio ssh aceptando la clave en un fichero temporal (no toca el known_hosts real)."""
    if not _ip_ok(ip):
        raise ValueError("ip inválida")
    puerto = int(puerto or 22)
    rc, out = correr(["ssh-keyscan", "-T", "5", "-p", str(puerto), "-t", "ed25519,rsa", ip])
    if not _no_existe(rc, out):
        return [l for l in (out or "").splitlines() if l.strip() and not l.startswith("#") and huella_de(l)[0]] if rc == 0 else []
    # Directorio temporal de nombre aleatorio y solo del conector (mktemp -d, 0700): un nombre fijo en
    # un /tmp compartido admitiría que otro proceso del nodo lo anticipara con un enlace simbólico.
    rc_d, d = correr(["mktemp", "-d", "/tmp/mdr-escaneo.XXXXXXXX"])
    directorio = (d or "").strip().splitlines()[-1] if rc_d == 0 and (d or "").strip() else ""
    if not re.match(r"^/tmp/mdr-escaneo\.[A-Za-z0-9]{6,}\Z", directorio):
        return []
    tmp = f"{directorio}/known_hosts"
    correr(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={tmp}",
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ConnectTimeout=5", "-o", "PreferredAuthentications=none",
            "-p", str(puerto), "-l", "mdr-escaneo", ip, "true"])
    rc, out = correr(["cat", tmp])
    correr(["rm", "-rf", directorio])
    return [l for l in (out or "").splitlines() if l.strip() and huella_de(l)[0]] if rc == 0 else []


def huella_presentada(ip, puerto, correr):
    """Huella (preferida) de la clave que presenta ahora el equipo, o None si no responde."""
    lineas = escanear(ip, puerto, correr)
    return _preferida([huella_de(l)[::-1] for l in lineas]) if lineas else None


def aceptar_clave_host(ip, puerto, huella_confirmada, known_hosts, correr):
    """Sustituye las claves fijadas de `ip` por las que presenta, SOLO si la huella que el analista vio
    y confirmó está entre ellas (si cambió entre medias, HuellaDistinta y no se toca nada)."""
    lineas = escanear(ip, puerto, correr)
    if not lineas:
        raise HuellaDistinta("el equipo no presentó ninguna clave")
    if huella_confirmada not in {huella_de(l)[0] for l in lineas}:
        raise HuellaDistinta("la huella que presenta el equipo no es la confirmada")
    rc0, actual = correr(["cat", known_hosts])
    actual = actual if rc0 == 0 else ""   # primera clave fijada: aún no hay fichero (y la salida es el error de cat)
    # Escritura atómica: temporal + copia del anterior + rename. Un corte a mitad no deja el known_hosts
    # truncado (con él, el conector no entraría a ningún equipo).
    rc, _ = correr(["tee", known_hosts + ".mdr"], reemplazar_host(actual, ip, lineas))
    if rc != 0:
        raise HuellaDistinta("no se pudo escribir el known_hosts del conector")
    correr(["cp", "-p", known_hosts, known_hosts + ".anterior"])
    rc, _ = correr(["mv", known_hosts + ".mdr", known_hosts])
    if rc != 0:
        raise HuellaDistinta("no se pudo sustituir el known_hosts del conector")
    return huella_confirmada
