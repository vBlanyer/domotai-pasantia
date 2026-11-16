"""El catálogo de acciones como dato: impacto, reversión y comando por acción."""
import re
import yaml

def cargar_catalogo(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def impacto_de(catalogo, accion_id):
    return catalogo[accion_id]["impacto"]

# ------------------------------------------------------------ minimo privilegio --
# El catalogo cerrado (RF-15) ya es la frontera de las ACCIONES: el motor no puede ordenar nada
# que no este en el. Aqui pasa a ser tambien la frontera de PRIVILEGIO en el nodo: el usuario
# con el que entra el conector solo puede ejecutar, via sudo, los comandos que el catalogo
# declara, con sus parametros como comodines. Derivarlo del catalogo, y no escribirlo a mano,
# es lo que impide que las dos fronteras se separen con el tiempo. Los comodines son seguros
# porque el conector rechaza cualquier parametro con espacios o metacaracteres (conector._SEGURO):
# un comodin no puede absorber argumentos que no esten en la plantilla.

_PLANTILLA = re.compile(r"\{[a-z_]+\}")
_BINARIO = re.compile(r"^[a-z][a-z0-9_-]*$")
# Valores de allowlist del sudoers: nombres de servicio/cuenta limpios. Rechaza `*` (reabriría el
# comodín), espacios y metacaracteres (sudoers roto) — misma disciplina que conector._SEGURO.
# Empieza por letra o número: un valor que empezara por «-» sería una opción del binario
# (`passwd -l -d`, `service --status-all stop`).
_VALOR_SEGURO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\Z")

def _tramos(plantilla):
    """Los comandos de una plantilla: cada tramo de ';' y solo el primer tramo de una tuberia
    (es el que ejecuta sudo). Devuelve [(binario, args_con_comodines)]."""
    salida = []
    for tramo in (plantilla or "").split(";"):
        partes = tramo.split("|", 1)[0].split()
        if partes and _BINARIO.match(partes[0]):
            salida.append((partes[0], " ".join(_PLANTILLA.sub("*", p) for p in partes[1:])))
    return salida

def comandos_privilegiados(catalogo):
    """[(binario, argumentos_con_comodines)] unicos, en orden estable, a partir de las plantillas
    del catalogo. `comando` y `reversion_cmd` son siempre comandos. `verificacion` a veces es una
    descripcion ("salida capturada", "pcap devuelto"): se toma como comando solo si usa parametros
    del catalogo, lleva tuberia, o empieza por un binario que el catalogo ya emplea como comando."""
    vistos, salida = set(), []
    def anadir(clave):
        if clave not in vistos:
            vistos.add(clave); salida.append(clave)
    binarios_de_accion = set()
    for accion in catalogo.values():
        for campo in ("comando", "reversion_cmd"):
            for clave in _tramos(accion.get(campo)):
                binarios_de_accion.add(clave[0]); anadir(clave)
    for accion in catalogo.values():
        v = accion.get("verificacion") or ""
        tramos = _tramos(v)
        if tramos and ("{" in v or "|" in v or tramos[0][0] in binarios_de_accion):
            for clave in tramos:
                anadir(clave)
    return salida

# ------------------------------------------------------------------ papel de cada equipo --
# Qué acciones del catálogo le aplican a un equipo según su papel. Es el punto de partida que propone
# la consola al dar de alta un equipo; el operador puede quitar o añadir acciones del catálogo. El
# sudoers del equipo y lo que el motor puede ordenarle salen de esa lista (no del catálogo entero).
_OBSERVAR = ["OBS_CONEXIONES", "OBS_PROCESOS", "OBS_ESCUCHA", "OBS_CONFIG", "OBS_CAPTURA"]
PAPELES = {
    "servidor": {"nombre": "Servidor",
                 "descripcion": "Observar, bloquear IP y puerto, cortar conexiones, limitar banda, parar servicios y bloquear cuentas de su lista.",
                 "acciones": _OBSERVAR + ["BLOQUEAR_IP", "BLOQUEAR_PUERTO", "MATAR_CONEXION", "LIMITAR_BANDA",
                                          "CERRAR_SERVICIO", "FORZAR_CAMBIO_PASS"]},
    "cortafuegos": {"nombre": "Cortafuegos o borde",
                    "descripcion": "Observar, bloquear en tránsito, bloquear destinos y aislar nodos.",
                    "acciones": _OBSERVAR + ["BLOQUEAR_IP", "BLOQUEAR_IP_FIREWALL", "BLOQUEAR_DESTINO", "AISLAR_NODO",
                                             "BLOQUEAR_PUERTO"]},
    "puesto": {"nombre": "Puesto",
               "descripcion": "Observar, cortar conexiones y bloquear cuentas de su lista.",
               "acciones": _OBSERVAR + ["BLOQUEAR_IP", "MATAR_CONEXION", "FORZAR_CAMBIO_PASS"]},
}
# Acciones cuyo objetivo es un nombre (servicio/cuenta): sin lista declarada, el equipo NO las admite
# (nunca «cualquier servicio» ni «cualquier cuenta», incluida root).
ACCION_CON_LISTA = {"CERRAR_SERVICIO": ("service", "servicios"), "FORZAR_CAMBIO_PASS": ("passwd", "cuentas")}


def acciones_efectivas(acciones, servicios=(), cuentas=(), cuentas_cualquiera=False):
    """Las acciones que de verdad admite el equipo: las elegidas, menos las de lista sin lista.
    `cuentas_cualquiera`: el bloqueo de cuentas admite cualquier cuenta (salvo las del sistema, que
    veta el motor), para las que crea el atacante y no se conocen de antemano."""
    listas = {"servicios": list(servicios or []), "cuentas": ["*"] if cuentas_cualquiera else list(cuentas or [])}
    return [a for a in acciones if a not in ACCION_CON_LISTA or listas[ACCION_CON_LISTA[a][1]]]


def reglas(catalogo, allowlist=None):
    """[(binario, argumentos)] que el sudoers permite: los comandos privilegiados del catálogo con el
    comodín de los binarios de `allowlist` expandido a sus valores. Es lo que `sudoers` escribe y lo
    que la prueba de conexión compara con lo que el equipo permite de verdad (deriva)."""
    allowlist = allowlist or {}
    out = []
    for binario, args in comandos_privilegiados(catalogo):
        pedidos = allowlist.get(binario) or []
        valores = [v for v in pedidos if _VALOR_SEGURO.match(str(v))
                   and not (binario == "passwd" and str(v) in _cuentas_del_sistema())]
        if pedidos and not valores and args.count("*") == 1:
            continue                  # una lista que se queda vacía al filtrar NO reabre el comodín
        if valores and args.count("*") == 1:
            out.extend((binario, args.replace("*", v)) for v in valores)
        else:
            out.append((binario, args))
    return out


def reglas_de_equipo(catalogo, acciones=None, servicios=(), cuentas=(), cuentas_cualquiera=False):
    """Reglas del sudoers de un equipo según su papel. `acciones=None` = equipo sin papel declarado:
    el catálogo entero (el comportamiento heredado del laboratorio). Con `cuentas_cualquiera` el
    sudoers de `passwd` conserva el comodín (como el aprovisionamiento clásico): la frontera «salvo las
    cuentas del sistema» la pone el filtro del motor, no sudo."""
    if acciones is None:
        return reglas(catalogo)
    sub = {k: v for k, v in catalogo.items() if k in set(acciones_efectivas(acciones, servicios, cuentas, cuentas_cualquiera))}
    return reglas(sub, {"service": list(servicios or []), "passwd": [] if cuentas_cualquiera else list(cuentas or [])})


# ------------------------------------------------------------- envoltorio mdr-accion --
# En sudoers un comodín `*` admite espacios (sudoers(5): los argumentos se comparan como una sola cadena),
# así que `iptables -A INPUT -s * -j DROP` dejaba pasar `--modprobe=<programa>`, que iptables ejecuta como
# root (#13 de la revisión del 15/11). El sudoers solo permite ahora este envoltorio, que recibe los
# argumentos ya separados y valida CADA UNO por su tipo antes de ejecutar exactamente una plantilla del
# catálogo. Es sh POSIX: sirve con cualquier sudo (también el 1.6.9 de Metasploitable).
ENVOLTORIO_RUTA = "/usr/local/sbin/mdr-accion"
PATH_SEGURO = "/usr/sbin:/usr/bin:/sbin:/bin"
_TIPO_PARAMETRO = {"ip": "ip", "ip_nodo": "ip", "puerto": "puerto", "if": "iface", "rate": "rate",
                   "servicio": "nombre", "usuario": "cuenta"}          # el resto: nombre
_VALIDADORES = r"""_una_linea() { case "$1" in *'
'*) return 1 ;; esac; return 0; }
_casa() { _una_linea "$1" && printf '%s' "$1" | grep -Eqx -- "$2"; }
_OCT='(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])'
es_ip() { _casa "$1" "($_OCT\.){3}$_OCT"; }
es_puerto() { _casa "$1" '[0-9]{1,5}' && [ "$1" -ge 1 ] && [ "$1" -le 65535 ]; }
es_iface() { _casa "$1" '[A-Za-z0-9][A-Za-z0-9._-]{0,14}'; }
es_rate() { _casa "$1" '[0-9]{1,9}(bit|kbit|mbit|gbit)'; }
es_nombre() { _casa "$1" '[A-Za-z0-9][A-Za-z0-9._-]{0,62}'; }
es_cuenta() { es_nombre "$1" || return 1; case " $SISTEMA " in *" $1 "*) return 1 ;; esac; return 0; }
"""


def _cuentas_del_sistema():
    from prototipo.motor.perfil import CUENTAS_DEL_SISTEMA
    return CUENTAS_DEL_SISTEMA


def _plantillas_tipadas(catalogo, allowlist=None):
    """[(binario, [token])] en el mismo orden que `reglas`: cada token es un literal o («tipo»,) para un
    parámetro. Con allowlist, el único parámetro de ese binario pasa a ser cada valor permitido (literal)."""
    import shlex
    crudas = {}
    for accion in catalogo.values():
        for campo in ("comando", "reversion_cmd", "verificacion"):
            for tramo in (accion.get(campo) or "").split(";"):
                partes = tramo.split("|", 1)[0].split()
                if partes and _BINARIO.match(partes[0]):
                    clave = (partes[0], " ".join(_PLANTILLA.sub("*", p) for p in partes[1:]))
                    crudas.setdefault(clave, [(_TIPO_PARAMETRO.get(p[1:-1], "nombre"),) if _PLANTILLA.fullmatch(p) else p
                                              for p in partes[1:]])
    out = []
    for binario, args in reglas(catalogo, allowlist):
        tokens = crudas.get((binario, args))
        if tokens is None:                       # una plantilla expandida con un valor de la allowlist
            tokens = shlex.split(args)
        out.append((binario, tokens))
    return out


def envoltorio(catalogo, allowlist=None, path=PATH_SEGURO, usuario=None):
    """Texto del envoltorio /usr/local/sbin/mdr-accion para un equipo (sus reglas: catálogo o papel)."""
    import shlex
    q = shlex.quote
    funciones, nombres = [], []
    for i, (binario, tokens) in enumerate(_plantillas_tipadas(catalogo, allowlist), 1):
        conds = [f"[ $# -eq {len(tokens) + 1} ]", f'[ "$1" = {q(binario)} ]']
        for j, t in enumerate(tokens, 2):
            arg = f'"${{{j}}}"'
            conds.append(f"es_{t[0]} {arg}" if isinstance(t, tuple) else f"[ {arg} = {q(t)} ]")
        funciones.append(f"r{i}() {{ " + " && ".join(conds) + "; }")
        nombres.append(f'r{i} "$@"')
    reglas_txt = "\n".join(f"{b} {a}".strip() for b, a in reglas(catalogo, allowlist))
    # el usuario real del conector tampoco se bloquea nunca: dejaría al MDR fuera del equipo
    sistema = " ".join(sorted(set(_cuentas_del_sistema()) | ({usuario} if usuario else set())))
    lineas = [
        "#!/bin/sh",
        "# mdr-accion: lo único que el conector del MDR puede ejecutar como root en este equipo.",
        "# Generado desde prototipo/catalogo.yml (python3 -m prototipo.accion.catalogo --envoltorio). No editar",
        "# a mano. Valida cada argumento por su tipo y ejecuta exactamente una plantilla del catálogo;",
        "# cualquier otra cosa sale con el código 126 sin ejecutar nada.",
        f"PATH={path}",
        "export PATH",
        f"SISTEMA={q(sistema)}",
        _VALIDADORES.rstrip("\n"),
        *funciones,
        'if [ "${1:-}" = "--reglas" ] && [ $# -eq 1 ]; then',
        "cat <<'FIN_REGLAS'",
        reglas_txt,
        "FIN_REGLAS",
        "exit 0",
        "fi",
        "if " + " || ".join(nombres) + "; then",
        '  exec "$@"',
        "fi",
        'echo "mdr-accion: orden fuera del catálogo; no se ejecuta" >&2',
        "exit 126",
    ]
    return "\n".join(lineas) + "\n"


def envoltorio_de_equipo(catalogo, acciones=None, servicios=(), cuentas=(), cuentas_cualquiera=False, path=PATH_SEGURO,
                         usuario=None):
    """El envoltorio de un equipo según su papel: las mismas reglas que `reglas_de_equipo`."""
    if acciones is None:
        return envoltorio(catalogo, path=path, usuario=usuario)
    sub = {k: v for k, v in catalogo.items() if k in set(acciones_efectivas(acciones, servicios, cuentas, cuentas_cualquiera))}
    return envoltorio(sub, {"service": list(servicios or []), "passwd": [] if cuentas_cualquiera else list(cuentas or [])},
                      path=path, usuario=usuario)


def sudoers_envoltorio(usuario, ruta=ENVOLTORIO_RUTA):
    """El sudoers del conector: solo el envoltorio (que valida cada argumento)."""
    return ("# Generado por el MDR: el conector solo puede ejecutar como root el envoltorio, que valida cada\n"
            "# argumento contra el catálogo cerrado de acciones (RF-15). No editar a mano.\n"
            f"{usuario} ALL=(root) NOPASSWD: {ruta}\n")


def sudoers(catalogo, usuario, rutas, allowlist=None):
    """Texto de sudoers para `usuario`: NOPASSWD solo sobre los comandos del catalogo, con la
    ruta absoluta de cada binario en `rutas`. Devuelve (texto, faltan).

    `allowlist` {binario: [valores]} RESTRINGE el comodin `*` de ese binario a una lista cerrada:
    en vez de `service * stop` (cualquier servicio) o `passwd -u *` (cualquier cuenta, incl. root),
    emite una linea por valor declarado (`service nginx stop`, ...). Sin allowlist para un binario,
    se mantiene el `*` (comportamiento por defecto). Solo acota comandos con UN comodin (los
    objetivos tipo servicio/cuenta); `{ip}`/`{puerto}` son arbitrarios por naturaleza y siguen `*`."""
    lineas, faltan = [], []
    for binario, args in reglas(catalogo, allowlist):
        ruta = rutas.get(binario)
        if not ruta:
            if binario not in faltan:
                faltan.append(binario)
            continue
        lineas.append(f"{usuario} ALL=(root) NOPASSWD: {ruta} {args}".rstrip())
    cabecera = ("# Generado desde prototipo/catalogo.yml: la frontera de privilegio del conector es\n"
                "# exactamente el catalogo cerrado de acciones (RF-15). No editar a mano; regenerar con\n"
                f"#   python3 -m prototipo.accion.catalogo --sudoers {usuario} --rutas bin=/ruta,...\n")
    return cabecera + "\n".join(lineas) + "\n", faltan

def _allowlist_de(argv):
    allowlist = {}
    if "--allowlist" in argv:   # p. ej. --allowlist service=nginx:apache2,passwd=appuser
        for par in argv[argv.index("--allowlist") + 1].split(","):
            if "=" in par:
                b, vals = par.split("=", 1)
                allowlist[b.strip()] = [v for v in vals.split(":") if v]
    return allowlist


def _main(argv):
    import os, sys
    if "--envoltorio" in argv:
        cat = cargar_catalogo(os.path.join(os.path.dirname(os.path.dirname(__file__)), "catalogo.yml"))
        usuario = argv[argv.index("--usuario") + 1] if "--usuario" in argv else None
        sys.stdout.write(envoltorio(cat, allowlist=_allowlist_de(argv) or None, usuario=usuario))
        return 0
    if "--sudoers" in argv:
        usuario = argv[argv.index("--sudoers") + 1]
        rutas = {}
        if "--rutas" in argv:
            for par in argv[argv.index("--rutas") + 1].split(","):
                if "=" in par:
                    b, p = par.split("=", 1)
                    if p:
                        rutas[b.strip()] = p.strip()
        allowlist = {}
        if "--allowlist" in argv:   # p. ej. --allowlist service=nginx:apache2,passwd=appuser
            for par in argv[argv.index("--allowlist") + 1].split(","):
                if "=" in par:
                    b, vals = par.split("=", 1)
                    allowlist[b.strip()] = [v for v in vals.split(":") if v]
        cat = cargar_catalogo(os.path.join(os.path.dirname(os.path.dirname(__file__)), "catalogo.yml"))
        texto, faltan = sudoers(cat, usuario, rutas, allowlist=allowlist or None)
        sys.stdout.write(texto)
        if faltan:
            print(f"# AVISO: sin ruta en el nodo, fuera del sudoers: {', '.join(faltan)}", file=sys.stderr)
        return 0
    print("uso: python3 -m prototipo.accion.catalogo --sudoers <usuario> --rutas iptables=/sbin/iptables,... "
          "[--allowlist service=nginx:apache2,passwd=appuser]")
    return 2

if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
