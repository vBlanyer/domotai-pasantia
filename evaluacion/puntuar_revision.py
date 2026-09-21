"""Puntúa las hojas de la revisión independiente una vez rellenadas.

    python3 -m evaluacion.puntuar_revision [--justificaciones evaluacion/resultados/revision-manual.csv]
                                           [--escalados evaluacion/resultados/revision-escalados.csv]
                                           [--salida evaluacion/resultados/revision-independiente.md]

Justificaciones: tasa de «s» por criterio (CORRECTA, ANCLADA, COHERENTE), en total y por clase.
Escalados: cruza la decisión del revisor con la etiqueta verdadera del dataset (la hoja era ciega),
y resume si el sistema hizo bien en preguntar y si lo mostrado bastaba para decidir.
Las filas en blanco no cuentan: las tasas son sobre lo respondido.
"""
import argparse
import csv
import json
import sys

from evaluacion import cargar

CRITERIOS = ("CORRECTA", "ANCLADA", "COHERENTE")
_DECISIONES = {"aprobar": "aprobar", "a": "aprobar", "1": "aprobar",
               "rechazar": "rechazar", "r": "rechazar", "2": "rechazar",
               "reclasificar": "reclasificar", "c": "reclasificar", "3": "reclasificar"}


def si_no(v):
    v = (v or "").strip().lower()
    if v in ("s", "si", "sí", "y", "yes"):
        return True
    if v in ("n", "no"):
        return False
    return None


def decision(v):
    return _DECISIONES.get((v or "").strip().lower())


def _tasa(valores):
    vs = [v for v in valores if v is not None]
    si = sum(1 for v in vs if v)
    return {"si": si, "n": len(vs), "tasa": (si / len(vs)) if vs else None}


def leer_hoja(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        lineas = list(csv.reader(f, delimiter=";"))
    cabecera, datos = lineas[1], lineas[2:]
    return [dict(zip(cabecera, l)) for l in datos if any(c.strip() for c in l)]


def puntuar_justificaciones(filas):
    resp = [{c: si_no(f.get(f"{c} (s/n)")) for c in CRITERIOS} | {"clase": f.get("clase_motor")} for f in filas]
    resp_ok = [r for r in resp if any(r[c] is not None for c in CRITERIOS)]
    por_clase = {}
    for r in resp_ok:
        por_clase.setdefault(r["clase"], []).append(r)
    return {"total": len(filas), "respondidas": len(resp_ok),
            "criterios": {c: _tasa(r[c] for r in resp_ok) for c in CRITERIOS},
            "por_clase": {k: {c: _tasa(r[c] for r in v) for c in CRITERIOS} for k, v in sorted(por_clase.items())}}


def puntuar_escalados(filas, verdad_por_id):
    cruce = {e: {"aprobar": 0, "rechazar": 0, "reclasificar": 0} for e in ("VP", "FP")}
    aciertos, acuerdos, n = [], [], 0
    for f in filas:
        d, v = decision(f.get("DECISION")), verdad_por_id.get(f.get("id_alerta"))
        if d is None or v not in cruce:
            continue
        n += 1
        cruce[v][d] += 1
        aciertos.append((d == "aprobar") == (v == "VP"))
        acuerdos.append(d == "aprobar")   # el sistema proponía contener en todas las escaladas
    return {"total": len(filas), "respondidas": n, "cruce": cruce,
            "acierto_humano": _tasa(aciertos)["tasa"],
            "acuerdo_con_el_sistema": _tasa(acuerdos)["tasa"],
            "fp_aprobados": cruce["FP"]["aprobar"],
            "preguntar_bien": _tasa(si_no(f.get("PREGUNTAR_BIEN (s/n)")) for f in filas),
            "info_suficiente": _tasa(si_no(f.get("INFO_SUFICIENTE (s/n)")) for f in filas)}


def _pct(t):
    return "—" if t is None else f"{t:.0%}"


def informe(just, esc):
    out = ["# Revisión independiente — resultados", ""]
    if just:
        out += [f"## Justificaciones ({just['respondidas']}/{just['total']} revisadas)", "",
                "| Criterio | Sí | Tasa |", "|---|---|---|"]
        out += [f"| {c} | {v['si']}/{v['n']} | {_pct(v['tasa'])} |" for c, v in just["criterios"].items()]
        out += ["", "| Clase | " + " | ".join(CRITERIOS) + " |", "|---" * (len(CRITERIOS) + 1) + "|"]
        out += [f"| {k} | " + " | ".join(_pct(v[c]["tasa"]) for c in CRITERIOS) + " |"
                for k, v in just["por_clase"].items()]
        out.append("")
    if esc:
        c = esc["cruce"]
        out += [f"## Decisiones escaladas ({esc['respondidas']}/{esc['total']} decididas)", "",
                "| Verdad \\ revisor | aprobar | rechazar | reclasificar |", "|---|---|---|---|"]
        out += [f"| {e} | {c[e]['aprobar']} | {c[e]['rechazar']} | {c[e]['reclasificar']} |" for e in ("VP", "FP")]
        out += ["",
                f"- Acierto del revisor (aprobar un VP, no ejecutar un FP): {_pct(esc['acierto_humano'])}",
                f"- Acuerdo con la acción que proponía el sistema: {_pct(esc['acuerdo_con_el_sistema'])}",
                f"- FP que el revisor habría aprobado: {esc['fp_aprobados']}",
                f"- «Hizo bien en preguntarme»: {esc['preguntar_bien']['si']}/{esc['preguntar_bien']['n']} "
                f"({_pct(esc['preguntar_bien']['tasa'])})",
                f"- «Con lo mostrado pude decidir»: {esc['info_suficiente']['si']}/{esc['info_suficiente']['n']} "
                f"({_pct(esc['info_suficiente']['tasa'])})", ""]
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description="Puntúa las hojas rellenadas de la revisión independiente")
    ap.add_argument("--justificaciones", default="evaluacion/resultados/revision-manual.csv")
    ap.add_argument("--escalados", default="evaluacion/resultados/revision-escalados.csv")
    ap.add_argument("--salida", default="evaluacion/resultados/revision-independiente.md")
    a = ap.parse_args(argv)
    verdad = {f["id_alerta"]: f["etiqueta"] for f in cargar.cargar(particion=None)}
    just = puntuar_justificaciones(leer_hoja(a.justificaciones))
    esc = puntuar_escalados(leer_hoja(a.escalados), verdad)
    texto = informe(just, esc)
    with open(a.salida, "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    print(texto + f"\n-> {a.salida}")
    if not just["respondidas"] and not esc["respondidas"]:
        print("(las hojas siguen en blanco: nada que puntuar todavía)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
