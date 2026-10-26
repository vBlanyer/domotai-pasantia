"""Retención de ficheros de traza (#6): poda los antiguos de un directorio con política por número
o por antigüedad, para que `run/` no crezca sin límite. Es una tarea de MANTENIMIENTO offline (cron
o a mano), nunca el daemon en vivo.

Salvaguardas: el fichero más reciente (se asume el que el daemon está escribiendo) NUNCA se poda, y
una traza con la cadena de hashes ROTA tampoco se borra —podría ser evidencia de manipulación (RF-09)
y se conserva con un aviso—. Sin `--aplicar` es una simulación (no borra nada).

    python3 -m prototipo.servicio.retener_trazas run --max 30 --aplicar
    python3 -m prototipo.servicio.retener_trazas run --max-dias 90 --aplicar
"""
import glob
import os
import sys

from prototipo.servicio import traza


def plan_retencion(ficheros, max_n=None, max_dias=None, ahora=None):
    """`ficheros`: lista de (ruta, mtime_epoch). Devuelve (conservar, podar). El más reciente nunca se
    poda. Se poda lo que exceda `max_n` (los N más recientes se conservan) o sea más viejo que
    `max_dias`. Sin política, no poda nada."""
    orden = sorted(ficheros, key=lambda f: f[1], reverse=True)   # más reciente primero
    conservar, podar = [], []
    for i, (ruta, mtime) in enumerate(orden):
        viejo_por_n = max_n is not None and i >= max_n
        viejo_por_dias = (max_dias is not None and ahora is not None and (ahora - mtime) > max_dias * 86400)
        if i != 0 and (viejo_por_n or viejo_por_dias):
            podar.append(ruta)
        else:
            conservar.append(ruta)                               # i==0 (activo) o dentro de la política
    return conservar, podar


def cadena_valida(ruta):
    """True si la cadena de hashes del fichero verifica (saltando los registros anteriores a la
    cadena, como la CLI de traza). Un fichero ilegible o roto devuelve False."""
    try:
        regs = traza.leer_registros(ruta)
    except (OSError, ValueError):
        return False
    k = next((i for i, r in enumerate(regs) if "hash" in r), len(regs))
    return traza.verificar(regs[k:])["valida"]


def _main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("uso: python3 -m prototipo.servicio.retener_trazas <dir> [--max N] [--max-dias D] "
              "[--excepto RUTA] [--aplicar]\n  (corre con el mismo TRIAJE_TRAZA_CLAVE que el daemon "
              "si la traza va firmada con HMAC)")
        return 2
    d = argv[0]
    max_n = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    max_dias = int(argv[argv.index("--max-dias") + 1]) if "--max-dias" in argv else None
    aplicar = "--aplicar" in argv
    # --excepto protege por NOMBRE el fichero activo del daemon (más fiable que inferirlo por mtime).
    exentos = {os.path.realpath(argv[i + 1]) for i, a in enumerate(argv) if a == "--excepto"}
    ficheros = [(r, os.path.getmtime(r)) for r in glob.glob(os.path.join(d, "trazas-*.jsonl"))]
    if not ficheros:
        print(f"no hay ficheros de traza (trazas-*.jsonl) en {d}")
        return 0
    import time
    _, podar = plan_retencion(ficheros, max_n=max_n, max_dias=max_dias, ahora=time.time())
    podar = [p for p in podar if os.path.realpath(p) not in exentos]   # nunca el activo nombrado
    borrados = conservados_rotos = 0
    for ruta in podar:
        if not cadena_valida(ruta):
            print(f"[aviso] {os.path.basename(ruta)}: no verifica la cadena -> se CONSERVA")
            conservados_rotos += 1
            continue
        if aplicar:
            os.remove(ruta); borrados += 1
            print(f"podado {os.path.basename(ruta)}")
        else:
            print(f"[seco] podaría {os.path.basename(ruta)}")
    if podar and conservados_rotos == len(podar):
        # Todo lo que tocaba podar «no verifica»: casi seguro falta TRIAJE_TRAZA_CLAVE en el entorno,
        # no que N ficheros estén manipulados. Se avisa para no dejar la retención inútil en silencio.
        print("[aviso] ningún candidato verificó la cadena; ¿falta TRIAJE_TRAZA_CLAVE en el entorno "
              "del cron (la misma del daemon)? no se podó nada.")
    a_podar = len(podar) - conservados_rotos
    print(f"{'borrados' if aplicar else 'a podar'}: {borrados if aplicar else a_podar}"
          f" · se conservan: {len(ficheros) - (borrados if aplicar else a_podar)}"
          + (f" ({conservados_rotos} no verifican)" if conservados_rotos else "")
          + ("" if aplicar else "  (simulación; usa --aplicar para borrar)"))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
