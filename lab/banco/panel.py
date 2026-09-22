"""Panel de salud del laboratorio del banco en la terminal: una fila por servicio en verde (OK) o rojo
(CAIDO), de quien depende, cuanto lleva en ese estado y los ultimos cambios. Se refresca solo.

    sh lab/banco/banco.sh vigilar        (o: python3 -m lab.banco.panel [--una-vez] [--sin-color])

Lee la ultima muestra del monitor que corre en mdr-siem (/var/log/banco/salud.jsonl, ver monitor.py):
no sondea nada por su cuenta, asi que muestra exactamente lo que el monitor mide. Corre en la
maquina anfitriona (usa docker exec), no dentro de la imagen.
"""
import argparse
import datetime
import json
import subprocess
import sys
import time

from lab.banco import red

VERDE, ROJO, GRIS, NEGRITA, FIN = "\033[32m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"
ORDEN = ["core-db", "hsm", "middleware", "web-banking", "api-movil", "swift-alliance", "atm"]
_MAX_EVENTOS = 8


def leer_ultima(ejecutar=subprocess.run):
    """Ultima muestra del monitor ({"t", "estados"}), o None si no hay datos o no se pueden leer."""
    try:
        r = ejecutar(["docker", "exec", "clab-banco-mdr-siem", "tail", "-n1", "/var/log/banco/salud.jsonl"],
                     capture_output=True, text=True)
    except OSError:
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return None


def historial_vacio():
    return {"ultimo": {}, "desde": {}, "eventos": []}


def actualizar(historial, muestra):
    """Anota los cambios de estado respecto a la muestra anterior. La primera muestra no es un cambio."""
    t = muestra["t"]
    for nombre, estado in sorted(muestra["estados"].items()):
        previo = historial["ultimo"].get(nombre)
        if previo is None:
            historial["desde"][nombre] = t
        elif previo != estado:
            historial["desde"][nombre] = t
            historial["eventos"].append((t, nombre, estado))
        historial["ultimo"][nombre] = estado
    historial["eventos"] = historial["eventos"][-_MAX_EVENTOS:]
    return historial


def _instante(t):
    return datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")


def _hora(t):
    return t[11:19]


def _duracion(desde, hasta):
    s = int((_instante(hasta) - _instante(desde)).total_seconds())
    return f"{s} s" if s < 120 else f"{s // 60} min"


def _dependencias(nombre):
    deps = red.SERVICIOS.get(nombre, {}).get("depende", [])
    return ", ".join(f"{d} (no declarada)" if (nombre, d) in red.NO_DECLARADAS else d for d in deps) or "—"


def renderizar(muestra, historial, color=True):
    c = (lambda codigo, texto: f"{codigo}{texto}{FIN}") if color else (lambda codigo, texto: texto)
    lineas = [c(NEGRITA, "Laboratorio del banco — salud de los servicios"), ""]
    if muestra is None:
        lineas.append("  sin datos del monitor (¿está levantado el banco? sh lab/lab.sh up banco)")
        return "\n".join(lineas)
    t, estados = muestra["t"], muestra["estados"]
    lineas.append(c(GRIS, f"  muestra de las {_hora(t)} UTC · se refresca cada 2 s · Ctrl+C para salir"))
    lineas.append("")
    lineas.append(f"  {'SERVICIO':<16}{'ESTADO':<12}{'DESDE HACE':<12}DEPENDE DE")
    for nombre in ORDEN + sorted(set(estados) - set(ORDEN)):
        if nombre not in estados:
            continue
        ok = estados[nombre] == "ok"
        estado = c(VERDE, f"{'● OK':<12}") if ok else c(ROJO, f"{'✖ CAÍDO':<12}")
        desde = _duracion(historial["desde"].get(nombre, t), t)
        lineas.append(f"  {nombre:<16}{estado}{desde:<12}{_dependencias(nombre)}")
    caidos = sum(1 for e in estados.values() if e != "ok")
    lineas.append("")
    resumen = f"  {caidos} de {len(estados)} servicios caídos"
    lineas.append(c(ROJO if caidos else VERDE, resumen))
    lineas.append("")
    lineas.append(c(NEGRITA, "  Últimos cambios"))
    if not historial["eventos"]:
        lineas.append(c(GRIS, "  (ninguno desde que se abrió el panel)"))
    for te, nombre, estado in reversed(historial["eventos"]):
        paso = c(ROJO, "OK → CAÍDO") if estado != "ok" else c(VERDE, "CAÍDO → OK")
        lineas.append(f"  {_hora(te)}  {nombre:<16}{paso}")
    return "\n".join(lineas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Panel de salud del laboratorio del banco")
    ap.add_argument("--una-vez", action="store_true", help="muestra una vez y sale")
    ap.add_argument("--sin-color", action="store_true")
    ap.add_argument("--intervalo", type=float, default=2.0)
    a = ap.parse_args(argv)
    color = not a.sin_color and sys.stdout.isatty()
    historial = historial_vacio()
    try:
        while True:
            muestra = leer_ultima()
            if muestra is not None:
                actualizar(historial, muestra)
            texto = renderizar(muestra, historial, color=color)
            if a.una_vez:
                print(texto)
                return 0
            print("\033[H\033[2J" + texto, flush=True)
            time.sleep(a.intervalo)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
