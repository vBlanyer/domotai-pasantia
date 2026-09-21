"""Hoja de revisión de las decisiones que el sistema escala al humano (la mitad del lazo humano que
la evaluación automática no puede medir).

    python3 -m evaluacion.revision_escalados [--n 24] [--semilla 21] [--salida evaluacion/resultados/revision-escalados.csv]

Corre el mismo pipeline que `campana.evaluar` (ráfaga calculada antes de clasificar), se queda con
las decisiones que piden validación humana y saca una muestra estratificada: todos los FP (aprobar
uno bloquearía algo legítimo), y el resto a partes iguales entre los estratos de VP (el router con
confianza baja, el puesto del empleado), para que ninguno quede tapado por el más numeroso.

La hoja es CIEGA: no lleva la etiqueta verdadera. El revisor ve exactamente lo que vería el analista
en la terminal (`validacion.mostrar`) y decide como lo haría en el turno. La verdad se cruza después,
con `evaluacion.puntuar_revision`.
"""
import argparse
import csv
import json
import random
import sys

from evaluacion import cargar
from prototipo import rafaga, triaje, validacion, catalogo as catm, perfil as perfilm

RUBRICA = ("Una fila por decision que el sistema te pasaria a ti. Lee la columna lo_que_ve_el_analista como si "
           "te saliera en la terminal durante el turno. "
           "DECISION = aprobar / rechazar / reclasificar (lo que harias tu); "
           "CLASE_NUEVA = solo si reclasificas: la clase correcta; "
           "PREGUNTAR_BIEN = s si hizo bien en pedirte validacion en vez de actuar solo, n si podia haberlo hecho sin ti; "
           "INFO_SUFICIENTE = s si con lo mostrado pudiste decidir, n si te falto algo (di que en el comentario).")

CABECERA = ["n", "id_alerta", "lo_que_ve_el_analista",
            "DECISION", "CLASE_NUEVA", "PREGUNTAR_BIEN (s/n)", "INFO_SUFICIENTE (s/n)", "comentario"]


def estrato(fila, traza):
    if fila.get("etiqueta") == "FP":
        return "FP"
    actor = ((traza.get("impacto_determinado") or {}).get("actor") or {}).get("tipo") or "desconocido"
    return f"VP · {actor}"


def escalados(filas, hallazgos, perfil_dict, perfil_nombre, catalogo):
    """(fila, traza) de cada decisión que pide humano, con la ráfaga calculada como en la campaña."""
    rafaga.contar_en_lote(filas)
    res = []
    for i, fila in enumerate(filas):
        traza = triaje.procesar(fila, hallazgos, perfil_dict, perfil_nombre, catalogo,
                                id_decision=f"e{i}", timestamp=fila.get("timestamp", ""))
        if traza.get("requiere_humano"):
            res.append((fila, traza))
    return res


def muestra_estratificada(pares, n=24, semilla=21):
    rng = random.Random(semilla)
    grupos = {}
    for par in pares:
        grupos.setdefault(estrato(*par), []).append(par)
    for g in grupos.values():
        rng.shuffle(g)
    elegidos = list(grupos.pop("FP", []))[:n]
    # Reparto a partes iguales entre los estratos VP; el que no llena su cupo lo cede a los demás.
    restantes = sorted(grupos.items(), key=lambda kv: len(kv[1]))
    cupo = n - len(elegidos)
    for i, (_, g) in enumerate(restantes):
        toma = min(len(g), cupo // (len(restantes) - i))
        elegidos += g[:toma]
        cupo -= toma
    rng.shuffle(elegidos)
    return elegidos


def escribir_hoja(pares, salida):
    with open(salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([RUBRICA])
        w.writerow(CABECERA)
        for n, (fila, traza) in enumerate(pares, 1):
            w.writerow([n, fila.get("id_alerta"), validacion.mostrar(traza, fila).strip(), "", "", "", "", ""])


def main(argv):
    ap = argparse.ArgumentParser(description="Hoja ciega de revisión de las decisiones escaladas al humano")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--semilla", type=int, default=21)
    ap.add_argument("--perfil", default="empresarial")
    ap.add_argument("--hallazgos", default="lab/campañas/2026-08-31-evaluacion/hallazgos.json")
    ap.add_argument("--salida", default="evaluacion/resultados/revision-escalados.csv")
    a = ap.parse_args(argv)
    filas = cargar.cargar(particion="evaluacion")
    with open(a.hallazgos, encoding="utf-8") as f:
        hallazgos = json.load(f)
    perfil_dict = perfilm.cargar(f"prototipo/perfiles/{a.perfil}.yml")
    catalogo = catm.cargar_catalogo("prototipo/catalogo.yml")
    todos = escalados(filas, hallazgos, perfil_dict, a.perfil, catalogo)
    muestra = muestra_estratificada(todos, n=a.n, semilla=a.semilla)
    escribir_hoja(muestra, a.salida)
    conteo = {}
    for par in muestra:
        conteo[estrato(*par)] = conteo.get(estrato(*par), 0) + 1
    print(f"{len(todos)} decisiones escaladas; muestra de {len(muestra)} -> {a.salida}  "
          f"({', '.join(f'{k}: {v}' for k, v in sorted(conteo.items()))}; abrir con LibreOffice/Excel, separador ';')")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
