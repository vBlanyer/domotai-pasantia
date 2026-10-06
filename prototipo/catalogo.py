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

def sudoers(catalogo, usuario, rutas):
    """Texto de sudoers para `usuario`: NOPASSWD solo sobre los comandos del catalogo, con la
    ruta absoluta de cada binario en `rutas` (resuelta en el nodo objetivo, porque sudoers
    exige rutas absolutas). Devuelve (texto, faltan): los binarios sin ruta quedan fuera y se
    devuelven para que el aprovisionamiento los declare."""
    lineas, faltan = [], []
    for binario, args in comandos_privilegiados(catalogo):
        ruta = rutas.get(binario)
        if not ruta:
            if binario not in faltan:
                faltan.append(binario)
            continue
        lineas.append(f"{usuario} ALL=(root) NOPASSWD: {ruta} {args}".rstrip())
    cabecera = ("# Generado desde prototipo/catalogo.yml: la frontera de privilegio del conector es\n"
                "# exactamente el catalogo cerrado de acciones (RF-15). No editar a mano; regenerar con\n"
                f"#   python3 -m prototipo.catalogo --sudoers {usuario} --rutas bin=/ruta,...\n")
    return cabecera + "\n".join(lineas) + "\n", faltan

def _main(argv):
    import os, sys
    if "--sudoers" in argv:
        usuario = argv[argv.index("--sudoers") + 1]
        rutas = {}
        if "--rutas" in argv:
            for par in argv[argv.index("--rutas") + 1].split(","):
                if "=" in par:
                    b, p = par.split("=", 1)
                    if p:
                        rutas[b.strip()] = p.strip()
        cat = cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
        texto, faltan = sudoers(cat, usuario, rutas)
        sys.stdout.write(texto)
        if faltan:
            print(f"# AVISO: sin ruta en el nodo, fuera del sudoers: {', '.join(faltan)}", file=sys.stderr)
        return 0
    print("uso: python3 -m prototipo.catalogo --sudoers <usuario> --rutas iptables=/sbin/iptables,...")
    return 2

if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
