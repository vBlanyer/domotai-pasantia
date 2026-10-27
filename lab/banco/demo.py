"""Lanzador de ataques del laboratorio del banco, por número, para demostraciones.

    sh lab/banco/banco.sh atacar             (menú interactivo; o: python3 -m lab.banco.demo)
    sh lab/banco/banco.sh atacar auto [N] [gap]          (TANDA: lanza toda la batería una vez, o N veces)
    sh lab/banco/banco.sh atacar continuo [opciones]     (SOAK: ataques variados SIN FIN hasta Ctrl+C)

La tanda CONTINUA (`continuo`/`soak`, o la tecla `c` del menú) ejercita el MDR de forma sostenida:
baraja TODA la batería en cada vuelta y la lanza sin parar hasta Ctrl+C, con la IP de origen rotada
(para que la supresión y los bloqueos previos no la ahoguen) y restaurando el banco cada N ataques
(`--restaurar-cada`, def. 20) para que no se degrade. `--gap` separa los ataques, `--semilla` fija
el orden (reproducible) y `--vueltas` lo acota si no se quiere sin fin. Al parar, un resumen por
familia; luego `sh lab/banco/banco.sh restaurar`.

Para que el ataque NO sea una caja negra, el menú muestra por defecto —y las tandas con `--verbose`/
`-v` (o la tecla `v`)— el comando EXACTO que se inyecta en cada nodo (`↳ <nodo> $ <comando>`): la
preparación, el ataque y el deshacer. Es `ejecutor_detallado`, que envuelve el ejecutor y narra cada
`docker exec` justo antes de lanzarlo, sin cambiar qué se ejecuta.

El menú cubre LAS 10 FAMILIAS (ninguna queda sin ataque): los casos de red del catálogo
(`lab/banco/casos.py`) numerados —fuerza bruta, reconocimiento, telnet, explotación web— y, a
continuación, los **ataques de host** (`ATAQUES_HOST`) cuya respuesta no es bloquear una IP de
origen: abuso de cuenta (bloquear la CUENTA), integridad de ficheros/FIM (AISLAR el host),
denegación de servicio/DoS (ACOTAR la banda), acceso consumado (CORTAR la sesión), exfiltración/C2
(bloquear el DESTINO) y malware (AISLAR el host). Reutiliza solo DATOS del catálogo; no toca el prototipo.
Respeta los 60 s de silencio de la regla 5763 de Wazuh entre ataques de red, y ofrece deshacer/restaurar.

La opción `t` del menú (o `atacar auto`) corre la **tanda automática**: lanza TODA la batería —los de
red con IP de origen rotada y luego los tres de host—, uno tras otro y solos (sin esperas de 60 s ni
supresión, cada uno un incidente distinto). Sirve para ver/probar el camino completo en vivo —la
plantilla justifica cada decisión— sin elegir uno a uno. No deshace: al terminar, `sh lab/banco/banco.sh restaurar`.

Los ataques de host sin origen de red (cuenta/FIM/DoS/exfil/malware) escriben su evento en el auth.log
que el reenviador (canal auth) ya manda a Wazuh; reglas locales (`lab/wazuh/local_rules_banco.xml`:
5902, 100400 syscheck, 100500 dos, 100700 c2, 100800 virustotal) lo levantan con el grupo que el
adaptador mapea a la familia. La detección en vivo se valida con el banco levantado, como todo caso vivo.

Con la tecla `r` se activa la **IP de origen rotativa**: cada ataque sale desde una IP nueva de la
misma subred del atacante (alias en la interfaz de datos + `ssh -b`), para poder repetir el mismo
ataque sin chocar con la supresión del MDR ni con el bloqueo previo, como un atacante que rota IPs.
"""
import os
import random
import subprocess
import sys
import time

from lab.banco import casos, red

P = "clab-banco"
ESPERA_WAZUH = 65          # la regla 5763 de Wazuh se silencia 60 s tras dispararse
IFACE_DATOS = "eth1"       # la interfaz del plano de datos en los nodos del banco
IP_EXTERNA = "198.51.100.10"   # el atacante externo, la misma que usan los casos de internet


def casos_vivos():
    """Los casos de nivel vivo que lanzan algo (ataque real o preparación), en el orden del catálogo."""
    return [c for c in casos.CASOS if c["nivel"] == "vivo" and (c.get("ataque") or c.get("preparar"))]


def rotable(caso):
    """Un caso admite IP de origen rotativa si lanza un ataque desde un origen conocido."""
    return bool(caso.get("ataque") and caso.get("origen"))


def ip_rotada(base_ip, n):
    """Una IP nueva en la /24 de `base_ip`, hosts 11.. para no pisar el gateway (.1), el nodo base
    (.10) ni la difusión (.255). Determinista: el n-ésimo lanzamiento usa .{11+n}."""
    subred = base_ip.rsplit(".", 1)[0]
    host = 11 + (n % 240)          # 11..250, todos válidos y distintos de .1/.10/.255
    return f"{subred}.{host}"


def ataque_rotado(caso, src_ip):
    """El ataque del propio caso, pero desde `src_ip`: alias en la interfaz de datos y el cliente
    (ssh, nc o curl) atado a esa IP. Antes solo sabía rotar una fuerza bruta SSH."""
    nodo, cmd = caso["ataque"]
    alias = f"ip addr add {src_ip}/24 dev {IFACE_DATOS} 2>/dev/null; "
    return nodo, alias + casos.atar_a_ip(cmd, src_ip)


def deshacer_rotado(caso, src_ip):
    """Las reglas de deshacer del caso con la IP base sustituida por la rotada, para retirar el
    bloqueo que el MDR aplicó a `src_ip` (no a la IP base)."""
    base = caso.get("origen", "")
    return [(nodo, cmd.replace(base, src_ip) if base else cmd) for nodo, cmd in caso.get("deshacer", [])]


def _exec(nodo, cmd, ejecutar=subprocess.run):
    return ejecutar(["docker", "exec", f"{P}-{nodo}", "sh", "-c", cmd], capture_output=True, text=True)


def _describir_comando(args):
    """Una línea legible de lo que el lanzador va a ejecutar contra el banco: el nodo y el comando de
    shell EXACTO (o la acción, si no es un `docker exec`). Es lo que convierte el script de ataque en
    algo transparente en vez de una caja negra: se ve qué se inyecta y dónde."""
    if args[:2] == ["docker", "exec"]:
        cont = next((a for a in args if isinstance(a, str) and a.startswith(f"{P}-")), f"{P}-?")
        return f"    ↳ {cont[len(P) + 1:]} $ {args[-1]}"     # <nodo> $ <comando>
    if args[:1] == ["sh"] and args[-1:] == ["restaurar"]:
        return "    ↳ (banco) restaurar: quita los bloqueos que aplicó el MDR y reinicia los servicios"
    return "    ↳ " + " ".join(str(a) for a in args)


def ejecutor_detallado(ejecutar=subprocess.run, escribir=print):
    """Envuelve un ejecutor para NARRAR cada comando (el nodo y el shell exacto) justo antes de
    lanzarlo. No cambia qué se ejecuta: solo lo hace visible, para que el ataque no sea opaco."""
    def _ejecutar(args, **kw):
        escribir(_describir_comando(args))
        return ejecutar(args, **kw)
    return _ejecutar


# --- Ataque de ABUSO DE CUENTA (familia abuso_de_cuenta) ---------------------------------------
# No es un ataque de red con IP de origen, sino un evento de cuenta en el equipo comprometido. En
# Alpine useradd/sudo no dejan log, así que el ataque CREA la cuenta (para que el bloqueo pueda
# aplicarse) y escribe la línea de useradd en el auth.log que el reenviador --auth manda a Wazuh
# (mismo patrón que el señuelo telnet). Wazuh dispara 5902 (grupo adduser) y el MDR la triaja como
# abuso_de_cuenta -> FORZAR_CAMBIO_PASS sobre la cuenta, retenido para humano. Por eso vive como paso
# propio (no como caso con `origen` de red): su respuesta es sobre el usuario, no una IP.
_AUTH_LOG = "/var/log/banco/auth.log"

def _linea_useradd(usuario):
    return (f"useradd[1234]: new user: name={usuario}, UID=1001, GID=1001, "
            f"home=/home/{usuario}, shell=/bin/ash")

def ataque_abuso_cuenta(destino="web-banking", usuario="backdoor", ejecutar=subprocess.run):
    cmd = f"adduser -D {usuario} 2>/dev/null; echo '{_linea_useradd(usuario)}' >> {_AUTH_LOG}"
    return _exec(destino, cmd, ejecutar)

def deshacer_abuso_cuenta(destino="web-banking", usuario="backdoor", ejecutar=subprocess.run):
    return _exec(destino, f"passwd -u {usuario} 2>/dev/null; deluser {usuario} 2>/dev/null", ejecutar)


# --- Ataque de INTEGRIDAD DE FICHEROS (familia integridad_fichero, FIM) ------------------------
# Como el abuso de cuenta, no tiene IP de origen: es un cambio en un fichero crítico del host. El
# banco no corre el módulo syscheck de Wazuh (alimenta por syslog, no por agente), así que el ataque
# MODIFICA de verdad un fichero (reversible) y escribe la línea `ossec-fim[...]` en el auth.log que el
# reenviador --auth ya manda a Wazuh; la regla local 100400 (grupo 'syscheck') la levanta -> el MDR la
# triaja integridad_fichero -> AISLAR_NODO (cuarentena en el cortafuegos de borde), humano incondicional.
_FIM_FICHERO = "/etc/.banco-integridad"

def _linea_fim(fichero):
    return (f"ossec-fim[1200]: integridad: checksum de '{fichero}' cambiado "
            "(fichero critico modificado/manipulado)")

def ataque_integridad_fichero(destino="web-banking", fichero=_FIM_FICHERO, ejecutar=subprocess.run):
    cmd = f"echo '# manipulado {int(time.time())}' >> {fichero}; echo '{_linea_fim(fichero)}' >> {_AUTH_LOG}"
    return _exec(destino, cmd, ejecutar)

def deshacer_integridad_fichero(destino="web-banking", fichero=_FIM_FICHERO, ejecutar=subprocess.run):
    return _exec(destino, f"rm -f {fichero} 2>/dev/null", ejecutar)


# --- Ataque de DENEGACIÓN DE SERVICIO (familia denegacion_servicio, DoS/flood) -----------------
# Un flujo volumétrico: no hay una IP única que bloquear, así que el MDR responde ACOTANDO la banda
# (LIMITAR_BANDA). Se genera una ráfaga MODESTA (no tumba el banco de verdad) y se escribe la línea
# `ossec-flood[...]` en el auth.log; la regla local 100500 (grupo 'dos') la levanta -> denegacion_servicio.
def _linea_dos(destino_ip):
    return (f"ossec-flood[1300]: posible inundacion: 400 conexiones/s hacia {destino_ip} "
            "(denegacion de servicio volumetrica)")

def ataque_denegacion_servicio(destino="web-banking", destino_ip="10.10.0.10", ejecutar=subprocess.run):
    rafaga = "for i in $(seq 1 30); do (printf x | nc -w1 127.0.0.1 443 >/dev/null 2>&1 &) done; "
    cmd = rafaga + f"echo '{_linea_dos(destino_ip)}' >> {_AUTH_LOG}"
    return _exec(destino, cmd, ejecutar)

def deshacer_denegacion_servicio(destino="web-banking", ejecutar=subprocess.run):
    # Si el MDR aplicó LIMITAR_BANDA, el throttle se quita con restaurar; aquí se limpia por si acaso.
    return _exec(destino, "tc qdisc del dev eth1 root 2>/dev/null || true", ejecutar)


# --- Ataque de ACCESO CONSUMADO (familia acceso_consumado) -------------------------------------
# El atacante YA entró: un login EXITOSO desde una IP que venía haciendo fuerza bruta. Se inyectan en
# el sshd.log (que el reenviador --sshd manda a Wazuh) unas líneas de fuerza bruta (disparan 5763) y
# luego un login aceptado desde la MISMA IP; la regla compuesta local 100600 (grupo 'intrusion') lo
# levanta -> acceso_consumado -> MATAR_CONEXION sobre la IP del atacante (cortar la sesión viva). Un
# login exitoso LEGÍTIMO no trae el contexto de fuerza bruta, así que no se marca.
_SSHD_LOG = "/var/log/banco/sshd.log"

def _linea_sshd_fallo(src_ip, usuario="cliente"):
    # Fallo sobre una cuenta VÁLIDA (la misma que luego entra), no "invalid user": así Wazuh acumula la
    # fuerza bruta por la vía 5760->5763 (usuario válido), que es la que la regla compuesta 100600 espera.
    return f"sshd[2100]: Failed password for {usuario} from {src_ip} port 51000 ssh2"

def _linea_sshd_exito(src_ip, usuario="cliente"):
    return f"sshd[2101]: Accepted password for {usuario} from {src_ip} port 51000 ssh2"

def ataque_acceso_consumado(destino="web-banking", src_ip=IP_EXTERNA, ejecutar=subprocess.run):
    # 10 fallos ESPACIADOS (para que la frecuencia de fuerza bruta 5763 acumule en su ventana y Wazuh
    # dispare la regla de fábrica 40112 "fallos seguidos de éxito") y luego un login aceptado desde la
    # MISMA IP -> 40112 -> regla local 100600 (grupo 'intrusion') -> acceso_consumado -> MATAR_CONEXION.
    fallos = "".join(f"echo '{_linea_sshd_fallo(src_ip)}' >> {_SSHD_LOG}; sleep 0.4; " for _ in range(10))
    cmd = fallos + f"sleep 1.5; echo '{_linea_sshd_exito(src_ip)}' >> {_SSHD_LOG}"
    return _exec(destino, cmd, ejecutar)

def deshacer_acceso_consumado(destino="web-banking", src_ip=IP_EXTERNA, ejecutar=subprocess.run):
    # MATAR_CONEXION es transitoria; si además se bloqueó la IP, se limpia el DROP.
    return _exec(destino, f"iptables -D INPUT -s {src_ip} -j DROP 2>/dev/null || true", ejecutar)


# --- Ataque de EXFILTRACIÓN / C2 (familia exfiltracion) ----------------------------------------
# Un activo interno conecta a un DESTINO malicioso conocido (lista de amenazas del SIEM). La respuesta
# estrena una DIRECCIÓN nueva: bloquear el DESTINO (egreso) en el borde (BLOQUEAR_DESTINO), no el
# origen. El banco no enruta a Internet, así que el ataque no hace una conexión real saliente: inyecta
# el evento que un IDS/threat-intel levantaría, con src (el host que baliza) y dst (el destino). La
# regla local 100700 (grupo 'c2') + el decoder banco-ids-c2 (saca srcip/dstip) lo levantan -> el MDR
# lo triaja exfiltracion -> BLOQUEAR_DESTINO en el cortafuegos de borde, humano. VALIDAR EN VIVO.
IP_C2 = "203.0.113.66"     # destino malicioso (lista de amenazas), fuera del banco

def _linea_c2(src_ip, dst_ip):
    return (f"ossec-ids[1400]: egress to known C2: src={src_ip} dst={dst_ip} "
            "(coincidencia con lista de amenazas)")

def ataque_exfiltracion(destino="web-banking", dst_ip=IP_C2, ejecutar=subprocess.run):
    src_ip = red.NODOS.get(destino, {}).get("ip", "10.10.0.10")   # el host interno que baliza
    cmd = f"echo '{_linea_c2(src_ip, dst_ip)}' >> {_AUTH_LOG}"
    return _exec(destino, cmd, ejecutar)

def deshacer_exfiltracion(destino="web-banking", dst_ip=IP_C2, ejecutar=subprocess.run):
    # Si el MDR aplicó BLOQUEAR_DESTINO, el bloqueo de egreso vive en el cortafuegos de borde (fw-core).
    return _exec("fw-core", f"iptables -D FORWARD -d {dst_ip} -j DROP 2>/dev/null || true", ejecutar)


# --- Ataque de MALWARE / ROOTKIT (familia malware) ---------------------------------------------
# Un veredicto EXPLÍCITO de binario malicioso (VirusTotal / rootcheck de trojano). La respuesta reusa
# AISLAR_NODO (la cuarentena de FIM): no se mata un proceso (eso roza EDR) ni se toca el host, se aísla
# en el borde. No ejecuta malware real: crea un fichero señuelo (reversible) e inyecta el veredicto que
# el agente levantaría. La regla local 100800 (grupo 'virustotal') lo levanta -> el MDR lo triaja
# malware -> AISLAR_NODO, humano incondicional. Cierra el hueco donde un hit de VirusTotal caía en
# 'plataforma' (ruido) o no_soportada sin contención. VALIDAR EN VIVO.
_MALWARE_FICHERO = "/tmp/.banco-muestra.bin"

def _linea_malware(fichero):
    return (f"ossec-vt[1500]: VirusTotal: {fichero} positives=54/70 "
            "(binario malicioso detectado)")

def ataque_malware(destino="web-banking", fichero=_MALWARE_FICHERO, ejecutar=subprocess.run):
    cmd = f"touch {fichero} 2>/dev/null; echo '{_linea_malware(fichero)}' >> {_AUTH_LOG}"
    return _exec(destino, cmd, ejecutar)

def deshacer_malware(destino="web-banking", fichero=_MALWARE_FICHERO, ejecutar=subprocess.run):
    return _exec(destino, f"rm -f {fichero} 2>/dev/null || true", ejecutar)


# Ataques "de host": se inyectan como EVENTO en el host (no un cliente de red que rota IP), así que
# viven fuera del catálogo de casos de red. El menú los lista tras los de red y la tanda los lanza todos.
ATAQUES_HOST = [
    {"id": "CUENTA", "familia": "abuso_de_cuenta",
     "titulo": "abuso de cuenta (alta de 'backdoor' en web-banking) -> bloquear la CUENTA, humano",
     "lanzar": ataque_abuso_cuenta, "deshacer": deshacer_abuso_cuenta},
    {"id": "FIM", "familia": "integridad_fichero",
     "titulo": "integridad de ficheros (modifica un fichero critico en web-banking) -> AISLAR el host, humano",
     "lanzar": ataque_integridad_fichero, "deshacer": deshacer_integridad_fichero},
    {"id": "DOS", "familia": "denegacion_servicio",
     "titulo": "denegacion de servicio (inundacion contra web-banking) -> ACOTAR la banda, humano",
     "lanzar": ataque_denegacion_servicio, "deshacer": deshacer_denegacion_servicio},
    {"id": "INTRUSION", "familia": "acceso_consumado",
     "titulo": "acceso consumado (login exitoso tras fuerza bruta en web-banking) -> CORTAR la conexion, humano",
     "lanzar": ataque_acceso_consumado, "deshacer": deshacer_acceso_consumado},
    {"id": "EXFIL", "familia": "exfiltracion",
     "titulo": "exfiltracion/C2 (web-banking conecta a un destino malicioso) -> BLOQUEAR el DESTINO en el borde, humano",
     "lanzar": ataque_exfiltracion, "deshacer": deshacer_exfiltracion},
    {"id": "MALWARE", "familia": "malware",
     "titulo": "malware (binario malicioso detectado en web-banking, VirusTotal) -> AISLAR el host, humano",
     "lanzar": ataque_malware, "deshacer": deshacer_malware},
]


def menu(vivos):
    """Casos de red numerados 1..N y, a continuación, los ataques de host (cuenta/FIM/DoS) N+1..N+M,
    para que TODAS las familias sean seleccionables por número desde una sola lista."""
    lineas = [f"  {i}. {c['id']} — {c['titulo']}" for i, c in enumerate(vivos, 1)]
    base = len(vivos)
    lineas += [f"  {base + i}. {h['id']} — {h['titulo']}" for i, h in enumerate(ATAQUES_HOST, 1)]
    return "\n".join(lineas)


LINEA_A_MEDIDA = "  a. Ataque a medida (elige equipo objetivo, servicio y origen)"


def _elegir(leer, prompt, opciones, etiqueta):
    """Imprime `opciones` numeradas (etiqueta(opcion) -> texto) y devuelve la elegida, o None si se
    cancela (0/intro) o la entrada no es válida."""
    for i, o in enumerate(opciones, 1):
        print(f"    {i}. {etiqueta(o)}")
    sel = (leer(prompt) or "").strip().lower()
    if sel in ("0", "", "q"):
        return None
    try:
        return opciones[int(sel) - 1] if int(sel) >= 1 else None
    except (ValueError, IndexError):
        print("  opción no válida")
        return None


def elegir_a_medida(leer):
    """Pregunta equipo objetivo, tipo de ataque (solo los que tienen sentido para ese equipo) y
    origen (internet o un equipo interno), y devuelve un caso a medida listo para `lanzar`. None si
    se cancela en cualquier paso."""
    objetivos = sorted(red.NODOS)
    print("\n  Equipo objetivo:")
    obj = _elegir(leer, f"  objetivo [1-{len(objetivos)}, 0=cancelar]: ",
                  objetivos, lambda n: f"{n} ({red.NODOS[n]['ip']})")
    if obj is None:
        return None
    puertos = red.SERVICIOS.get(obj, {}).get("puertos", [])
    tipos = casos.tipos_para(puertos)
    print(f"\n  Tipo de ataque contra {obj}:")
    tipo = _elegir(leer, f"  ataque [1-{len(tipos)}, 0=cancelar]: ", tipos, lambda t: t["titulo"])
    if tipo is None:
        return None
    origenes = ["internet"] + [n for n in objetivos if n != obj]
    print("\n  Origen del ataque:")
    org = _elegir(leer, f"  origen [1-{len(origenes)}, 0=cancelar]: ", origenes,
                  lambda n: "internet (atacante externo)" if n == "internet" else f"{n} ({red.NODOS[n]['ip']})")
    if org is None:
        return None
    origen_nodo, origen_ip = ("internet", IP_EXTERNA) if org == "internet" else (org, red.NODOS[org]["ip"])
    puerto = next((p for p in puertos if p in casos.PUERTOS_WEB), None)
    return casos.caso_a_medida(tipo["clave"], origen_nodo, origen_ip, obj, red.NODOS[obj]["ip"], puerto)


def lanzar(caso, ejecutar=subprocess.run, src_ip=None):
    """Ejecuta la preparación (si la hay) y luego el ataque, vía docker exec. Con `src_ip`, lanza
    el ataque desde esa IP de origen nueva (rotación); sin él, comportamiento actual."""
    for nodo, cmd in caso.get("preparar", []):
        _exec(nodo, cmd, ejecutar)
    if caso.get("ataque"):
        origen, cmd = ataque_rotado(caso, src_ip) if src_ip else caso["ataque"]
        _exec(origen, cmd, ejecutar)


def deshacer(caso, ejecutar=subprocess.run, src_ip=None):
    reglas = deshacer_rotado(caso, src_ip) if src_ip else caso.get("deshacer", [])
    for nodo, cmd in reglas:
        if cmd == "REARRANCAR":
            ejecutar(["docker", "exec", "-d", f"{P}-{nodo}", "sh", "-c", red.comando_servicio(nodo)])
        else:
            _exec(nodo, cmd, ejecutar)


def _siguiente_rotada(caso, contadores):
    """La próxima IP de origen rotada para `caso`, avanzando el contador de su subred: IPs nuevas
    contiguas, nunca una que el MDR pueda tener ya bloqueada de un ataque anterior."""
    subred = caso["origen"].rsplit(".", 1)[0]
    n = contadores.get(subred, 0)
    contadores[subred] = n + 1
    return ip_rotada(caso["origen"], n)


def _ruta_banco_sh():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "banco.sh")


def restaurar_banco(ejecutar=subprocess.run):
    """Deja el banco sano a mitad de un soak reusando `banco.sh restaurar` (la MISMA rutina que la
    restauración manual: quita los bloqueos que aplicó el MDR al contener y reinicia los servicios
    caídos). Así una tanda larga no deja el banco degradado —host aislado, servicio caído— hasta el
    punto de dejar de generar incidentes nuevos."""
    return ejecutar(["sh", _ruta_banco_sh(), "restaurar"], capture_output=True, text=True)


def tanda_automatica(ejecutar=subprocess.run, dormir=time.sleep, repeticiones=1, gap=6, escribir=print):
    """Lanza TODA la batería de ataques vivos (los que atacan desde un origen), uno tras otro y solos,
    con IP de origen ROTADA: sin esperas de 60 s ni supresión, y cada uno aparece como incidente
    distinto en el tablero. La clase del origen se conserva (interno→retenido, externo→auto), así que
    la batería ejercita ambos caminos y la plantilla justifica cada decisión. NO deshace: el daemon
    decide y, al terminar, se restaura con `sh lab/banco/banco.sh restaurar`. `repeticiones` vueltas."""
    vivos = [c for c in casos_vivos() if rotable(c)]
    # +len(ATAQUES_HOST): los ataques de host (cuenta/FIM/DoS), sin origen de red, se lanzan al final.
    contadores, total, hecho = {}, repeticiones * len(vivos) + len(ATAQUES_HOST), 0
    escribir(f"== Tanda automática: {total} ataque(s), IP de origen rotada (ve el tablero) ==")
    for _ in range(repeticiones):
        for caso in vivos:
            src = _siguiente_rotada(caso, contadores)
            hecho += 1
            escribir(f"  [{hecho}/{total}] {caso['id']} — {caso['titulo']} desde {src}")
            lanzar(caso, ejecutar=ejecutar, src_ip=src)
            dormir(gap)
    # Ataques de host: no rotan (no tienen IP de origen); se lanzan una vez cada uno, al final.
    for host in ATAQUES_HOST:
        hecho += 1
        escribir(f"  [{hecho}/{total}] {host['id']} — {host['titulo']}")
        host["lanzar"](ejecutar=ejecutar)
        dormir(gap)
    escribir(f"  tanda completa ({total} ataques). Deshaz con: sh lab/banco/banco.sh restaurar")


def tanda_continua(ejecutar=subprocess.run, dormir=time.sleep, gap=6, restaurar_cada=20,
                   semilla=None, vueltas=None, escribir=print):
    """Lanza ataques VARIADOS de forma indefinida —barajando el orden en cada vuelta y rotando la IP
    de origen— hasta que algo lo pare (Ctrl+C) o se cumplan `vueltas`. Pensado para SOAK/estrés del
    MDR: ejercita el camino detección→triaje→respuesta de forma continua y en orden impredecible,
    contra el banco propio. La IP de origen nueva en cada ataque de red esquiva la supresión y los
    bloqueos previos; cada `restaurar_cada` ataques se restaura el banco para que no se degrade
    indefinidamente (0 lo desactiva). `semilla` fija el orden (reproducible, RNF-03). `vueltas=None`
    = sin fin. Devuelve {lanzados, vueltas, tally} al parar. NO deshace los ataques de host: al
    terminar, `sh lab/banco/banco.sh restaurar`."""
    rng = random.Random(semilla)
    rotables = [c for c in casos_vivos() if rotable(c)]
    contadores, tally, lanzados, vuelta = {}, {}, 0, 0
    limite = "sin fin (Ctrl+C para parar)" if vueltas is None else f"{vueltas} vuelta(s)"
    escribir(f"== Tanda CONTINUA — {limite}: ataques variados, IP de origen rotada, "
             f"restaura cada {restaurar_cada or 'nunca'} ==")
    try:
        while vueltas is None or vuelta < vueltas:
            vuelta += 1
            # El pool de la vuelta: cada caso de red con su IP nueva + los ataques de host, barajado
            # para que el orden no sea siempre el mismo (un soak realista, no un guion fijo).
            pool = [("red", c, _siguiente_rotada(c, contadores)) for c in rotables]
            pool += [("host", h, None) for h in ATAQUES_HOST]
            rng.shuffle(pool)
            for tipo, item, src in pool:
                lanzados += 1
                tally[item["id"]] = tally.get(item["id"], 0) + 1
                desde = f" desde {src}" if src else ""
                escribir(f"  [{lanzados}] vuelta {vuelta} · {item['id']} — {item['titulo']}{desde}")
                if tipo == "red":
                    lanzar(item, ejecutar=ejecutar, src_ip=src)
                else:
                    item["lanzar"](ejecutar=ejecutar)
                if restaurar_cada and lanzados % restaurar_cada == 0:
                    escribir(f"  · restaurando el banco tras {lanzados} ataque(s) (que no se degrade)")
                    restaurar_banco(ejecutar=ejecutar)
                dormir(gap)
    except (KeyboardInterrupt, EOFError):
        pass
    escribir(f"\n== parada: {lanzados} ataque(s) en {vuelta} vuelta(s) ==")
    for id_, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
        escribir(f"   {id_}: {n}")
    escribir("  restaura el banco con: sh lab/banco/banco.sh restaurar")
    return {"lanzados": lanzados, "vueltas": vuelta, "tally": tally}


def _parsear_continuo(argv):
    import argparse
    p = argparse.ArgumentParser(prog="banco.sh atacar continuo",
                                description="Soak del MDR: lanza ataques variados sin fin (Ctrl+C para parar).")
    p.add_argument("--gap", type=float, default=6, help="segundos entre ataques (def. 6)")
    p.add_argument("--restaurar-cada", type=int, default=20, dest="restaurar_cada",
                   help="restaura el banco cada N ataques; 0 lo desactiva (def. 20)")
    p.add_argument("--semilla", type=int, default=None, help="fija el orden del barajado (reproducible)")
    p.add_argument("--vueltas", type=int, default=None, help="para tras N vueltas completas (def. sin fin)")
    p.add_argument("-v", "--verbose", "--detalle", action="store_true", dest="verbose",
                   help="muestra el nodo y el comando exacto de cada ataque (no caja negra)")
    return p.parse_args(argv)


_BANDERAS_DETALLE = ("-v", "--verbose", "--detalle")


def main(argv=None, leer=input, ejecutar=subprocess.run, dormir=time.sleep):
    if argv and argv[0] == "auto":   # no interactivo: sh lab/banco/banco.sh atacar auto [repeticiones] [gap] [-v]
        pos = [x for x in argv[1:] if x not in _BANDERAS_DETALLE]
        ej = ejecutor_detallado(ejecutar) if any(x in _BANDERAS_DETALLE for x in argv[1:]) else ejecutar
        reps = int(pos[0]) if len(pos) > 0 else 1
        gap = float(pos[1]) if len(pos) > 1 else 6
        tanda_automatica(ejecutar=ej, dormir=dormir, repeticiones=reps, gap=gap)
        return 0
    if argv and argv[0] in ("continuo", "soak"):   # soak: ataques variados sin fin (Ctrl+C para parar)
        a = _parsear_continuo(argv[1:])
        ej = ejecutor_detallado(ejecutar) if a.verbose else ejecutar
        tanda_continua(ejecutar=ej, dormir=dormir, gap=a.gap, restaurar_cada=a.restaurar_cada,
                       semilla=a.semilla, vueltas=a.vueltas)
        return 0
    vivos = casos_vivos()
    ultimo = 0.0
    rotar = False
    detallar = True                 # por defecto, el menú MUESTRA el comando de cada ataque (no caja negra)
    contadores = {}                 # subred -> nº de lanzamientos rotados (para IPs nuevas contiguas)
    sin_deshacer = {}               # origen -> caso que atacó desde él y no se deshizo (puede estar bloqueado)
    try:
        while True:
            base = len(vivos)
            print("\n== Ataques del banco (para el daemon/tablero) ==")
            print(menu(vivos))
            print(LINEA_A_MEDIDA)
            print("  t. Tanda automática (lanza TODA la batería sola: red + host, IP rotada)")
            print("  c. Tanda CONTINUA / soak (ataques variados SIN FIN hasta Ctrl+C; IP rotada, auto-restaura)")
            print(f"  r. IP de origen rotativa: {'ON' if rotar else 'OFF'}  "
                  "(cada ataque de red desde una IP nueva; esquiva supresión y bloqueo previo)")
            print(f"  v. Detalle de comandos: {'ON' if detallar else 'OFF'}  "
                  "(muestra el nodo y el comando exacto de cada ataque)")
            print("  0. Salir")
            sel = leer(f"Elige [0-{base + len(ATAQUES_HOST)}, a, t, c, r, v]: ").strip().lower()
            if sel in ("0", "", "q"):
                return 0
            if sel == "r":
                rotar = not rotar
                continue
            if sel == "v":
                detallar = not detallar
                continue
            # El ejecutor que se usa para TODO lo que se lance en esta vuelta: narrado o no.
            ej = ejecutor_detallado(ejecutar) if detallar else ejecutar
            if sel == "t":
                tanda_automatica(ejecutar=ej, dormir=dormir)
                continue
            if sel == "c":
                tanda_continua(ejecutar=ej, dormir=dormir)
                continue
            if sel == "a":
                caso = elegir_a_medida(leer)
                if caso is None:
                    continue
            else:
                try:
                    idx = int(sel)
                    if idx < 1:
                        raise IndexError
                except ValueError:
                    print("  opción no válida")
                    continue
                if base < idx <= base + len(ATAQUES_HOST):
                    # Ataque de host (cuenta/FIM/DoS): sin IP de origen, no rota; lanza y ofrece deshacer.
                    host = ATAQUES_HOST[idx - base - 1]
                    print(f"  lanzando {host['id']} — {host['titulo']}...")
                    host["lanzar"](ejecutar=ej)
                    if leer("  ¿deshacer/restaurar? [s/N] ").strip().lower().startswith("s"):
                        host["deshacer"](ejecutar=ej); print("  restaurado")
                    continue
                try:
                    caso = vivos[idx - 1]
                except IndexError:
                    print("  opción no válida")
                    continue

            # IP de origen: rotada (si procede) o la base del caso.
            src = None
            if rotar and rotable(caso):
                subred = caso["origen"].rsplit(".", 1)[0]
                n = contadores.get(subred, 0)
                src = ip_rotada(caso["origen"], n)
                contadores[subred] = n + 1

            # La espera de 60 s solo hace falta al repetir desde la MISMA IP; con IP nueva no aplica.
            if caso.get("ataque") and src is None:
                espera = ESPERA_WAZUH - (time.time() - ultimo)
                if ultimo and espera > 0:
                    print(f"  (esperando {int(espera)} s: la regla 5763 se silencia 60 s tras dispararse)")
                    dormir(espera)

            origen = caso.get("origen")
            if rotar and caso.get("ataque") and not rotable(caso):
                print(f"  (el caso {caso['id']} no admite IP rotativa: sale desde {origen})")
            if caso.get("ataque") and src is None and origen in sin_deshacer:
                print(f"  ⚠ {origen} ya atacó en {sin_deshacer[origen]} sin deshacer: puede que el MDR la haya "
                      "bloqueado y este ataque no llegue. Usa r (IP rotativa) o sh lab/banco/banco.sh restaurar.")

            desde = f" desde {src}" if src else ""
            print(f"  lanzando {caso['id']} — {caso['titulo']}{desde}...")
            lanzar(caso, ejecutar=ej, src_ip=src)
            if caso.get("ataque") and src is None:
                ultimo = time.time()
                if origen:
                    sin_deshacer[origen] = caso["id"]
            if caso.get("deshacer") and leer("  ¿deshacer/restaurar el caso? [s/N] ").strip().lower().startswith("s"):
                deshacer(caso, ejecutar=ej, src_ip=src)
                if src is None:
                    sin_deshacer.pop(origen, None)
                print("  restaurado")
    except (KeyboardInterrupt, EOFError):
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
