"""Escaneo de postura: qué puertos tiene abiertos cada equipo del perfil, con Nmap, en el formato que
consume el motor (`hallazgos`: {version_herramienta, timestamp, nodos: {equipo: [{puerto, servicio,
estado}]}}). Con postura, el MDR distingue un ataque a un servicio expuesto (confianza alta, se puede
automatizar) de uno a un servicio cerrado (falso positivo); sin ella, todo es caso gris.

Un equipo cuyo escaneo falla se OMITE, nunca se escribe como lista vacía: vacía significa «escaneado,
sin puertos abiertos» y voltearía un ataque real a falso positivo (`postura_de` trata la ausencia como
caso gris). Escanear la red del cliente exige su autorización por escrito.

    python3 -m prototipo.herramientas.escanear_postura <perfil.yml> <salida.json> [--puertos 22,443] [--equipos a,b]
"""
import datetime
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile

PLAZO_EQUIPO = "120s"


def parsear_puertos(stdout):
    """{puerto, servicio, estado} de cada línea «22/tcp open ssh» de la salida de Nmap."""
    return [{"puerto": int(m.group(1)), "servicio": m.group(3), "estado": m.group(2)}
            for m in re.finditer(r"^(\d+)/tcp\s+(\S+)\s+(\S+)", stdout, re.M)]


def argumentos(ip, puertos=None):
    alcance = ["-p", puertos] if puertos else ["--top-ports", "1000"]
    return ["nmap", "-Pn", "--host-timeout", PLAZO_EQUIPO, *alcance, ip]


def _ip_valida(ip):
    try:
        ipaddress.ip_address(str(ip))
        return True
    except ValueError:
        return False


def escanear(perfil, ejecutar=subprocess.run, puertos=None, equipos=None, ahora=None):
    """(hallazgos, omitidos). Sale con error si Nmap no está: sin versión registrada, los resultados
    no serían comparables entre escaneos."""
    try:
        r = ejecutar(["nmap", "--version"], capture_output=True, text=True)
    except OSError:
        raise SystemExit("escanear: no se encuentra nmap en este equipo (instálalo: apt install nmap)")
    if r.returncode != 0 or not r.stdout:
        raise SystemExit("escanear: nmap no responde a --version; no se escribe nada")
    version = r.stdout.splitlines()[0].split(" (")[0]
    if puertos and not re.fullmatch(r"[0-9,\-]+", puertos):
        raise SystemExit("escanear: --puertos admite números, comas y rangos (22,80,8000-8100)")

    nodos, omitidos = {}, []
    for nombre, a in (perfil.get("activos") or {}).items():
        if equipos and nombre not in equipos:
            continue
        ip = (a or {}).get("ip")
        if not ip:
            continue
        if not _ip_valida(ip):
            omitidos.append(nombre)
            continue
        try:
            res = ejecutar(argumentos(str(ip), puertos), capture_output=True, text=True)
        except OSError:
            omitidos.append(nombre)
            continue
        if res.returncode != 0:
            omitidos.append(nombre)
            continue
        nodos[nombre] = parsear_puertos(res.stdout)
    sello = ahora or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"version_herramienta": version, "timestamp": sello, "nodos": nodos}, omitidos


def fusionar(anterior, nuevo, intentados):
    """La postura tras escanear SOLO `intentados`: el resto se conserva de `anterior`; de los
    intentados manda el escaneo nuevo, y uno que falló queda como caso gris (sin su entrada vieja)."""
    nodos = {k: v for k, v in ((anterior or {}).get("nodos") or {}).items() if k not in set(intentados)}
    nodos.update(nuevo["nodos"])
    return {**nuevo, "nodos": nodos}


def escribir(hallazgos, ruta):
    """Escribe de una vez (fichero temporal y renombrado): el servicio nunca lee uno a medias."""
    d = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".postura-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(hallazgos, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o644)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _opcion(argv, nombre):
    if nombre in argv:
        i = argv.index(nombre)
        return argv[i + 1] if i + 1 < len(argv) else None
    return None


def _main(argv):
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
    if len(pos) != 2:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    from prototipo.motor import perfil as perfilm
    perfil = perfilm.cargar(pos[0])
    equipos = _opcion(argv, "--equipos")
    hallazgos, omitidos = escanear(perfil, puertos=_opcion(argv, "--puertos"),
                                   equipos=equipos.split(",") if equipos else None)
    if equipos:                                     # solo unos equipos: el resto de la postura se conserva
        try:
            with open(pos[1], encoding="utf-8") as f:
                anterior = json.load(f)
        except (OSError, ValueError):
            anterior = {}
        hallazgos = fusionar(anterior, hallazgos, equipos.split(","))
    escribir(hallazgos, pos[1])
    total = sum(len(v) for v in hallazgos["nodos"].values())
    print(f"postura -> {pos[1]}: {len(hallazgos['nodos'])} equipos, {total} puertos ({hallazgos['version_herramienta']})")
    if omitidos:
        print(f"sin escanear (quedan como caso gris): {', '.join(omitidos)}")
    print("El MDR lee la postura al arrancar: reinicia el servicio para usarla.")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
