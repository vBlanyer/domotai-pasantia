"""Hoja de revisión manual de las justificaciones (la segunda mirada que el informe recomienda).

    python3 -m evaluacion.revision_manual [evaluacion/resultados/8b-con-rag/campana-<fecha>.json] [salida.csv]

Exporta una fila por justificación generada con lo que el revisor necesita para juzgarla sin abrir
nada más: la alerta (regla, familia, origen, activo, servicio, ráfaga), la verdad del dataset, la
clase que decidió el motor, los pasajes que recuperó y el texto. Y tres columnas vacías para el
revisor. El criterio no es «suena bien»: es si el texto explica LA decisión del motor citando
solo hechos de la alerta, sin contradecirla y sin inventar.
"""
import csv
import glob
import json
import sys

RUBRICA = ("Criterios (una letra por columna): "
           "CORRECTA = explica la decision del motor (la clase), no otra cosa; "
           "ANCLADA = solo cita hechos de la alerta (origen, activo, servicio, regla, rafaga): nada inventado ni de otro caso; "
           "COHERENTE = no contradice la clase ni el motivo real (origen declarado, exposicion, rafaga). "
           "Respuesta: s / n. Comentario libre en la ultima columna.")


def main(argv):
    ruta = argv[0] if argv else sorted(glob.glob("evaluacion/resultados/8b-con-rag/campana-*.json"))[-1]
    salida = argv[1] if len(argv) > 1 else "evaluacion/resultados/revision-manual.csv"
    d = json.load(open(ruta, encoding="utf-8"))
    filas = {f["id_alerta"]: f for f in (json.loads(l) for l in open("lab/dataset/etiquetado.jsonl", encoding="utf-8") if l.strip())}
    with open(salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([RUBRICA])
        w.writerow(["n", "id_alerta", "regla", "familia", "origen", "activo", "servicio", "verdad", "clase_motor",
                    "justificador", "pasajes", "justificacion", "CORRECTA (s/n)", "ANCLADA (s/n)", "COHERENTE (s/n)", "comentario"])
        n = 0
        for r in d["anclaje"]["detalle"]:
            a = filas.get(r["id_alerta"], {})
            n += 1
            w.writerow([n, r["id_alerta"], a.get("regla_id"), a.get("familia"), a.get("origen_ip"), a.get("activo"),
                        a.get("servicio"), a.get("etiqueta"), r.get("clase"), r.get("justificador"),
                        " ".join(r.get("pasajes_usados") or []), (r.get("texto") or "").replace("\n", " "), "", "", "", ""])
    print(f"{n} justificaciones -> {salida}  (abrir con LibreOffice/Excel; separador ';')")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
