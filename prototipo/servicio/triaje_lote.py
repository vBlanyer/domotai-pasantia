"""Triaje por LOTES, sin ejecutor: decide y escribe los registros, no contiene. Es el paralelo
«decide-solo» de `servicio/lazo` (que además ejecuta). Vive en `servicio/` porque es orquestación
con E/S; el pipeline de decisión que recorre es `motor/triaje.procesar` (puro).

Uso: python3 -m prototipo.servicio.triaje_lote <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl>
(las alertas van NORMALIZADAS: prototipo.entrada.ingesta primero, como en lazo)."""
import json
import os
import sys

from prototipo.entrada import ingesta
from prototipo.motor import perfil as perfilm, triaje
from prototipo.accion import catalogo as catm


def main(argv):
    alertas_path, perfil_path, hallazgos_path, salida = argv[1:5]
    perfil_dict = perfilm.cargar(perfil_path)
    perfil_nombre = perfil_path.split("/")[-1].replace(".yml", "")
    with open(hallazgos_path, encoding="utf-8") as f:
        hallazgos = json.load(f)
    catalogo = catm.cargar_catalogo(os.path.join(os.path.dirname(os.path.dirname(__file__)), "catalogo.yml"))
    n = 0
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)  # crea run/ (u otro dir de la salida)
    with open(alertas_path, encoding="utf-8") as fin, open(salida, "w", encoding="utf-8") as fout:
        for i, linea in enumerate(fin):
            alerta = ingesta.parsear_linea(linea)
            if alerta is None:
                continue
            ts = alerta.get("timestamp", "")
            r = triaje.procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo,
                                id_decision=f"d{i}", timestamp=ts)
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} decisiones -> {salida}")


if __name__ == "__main__":
    main(sys.argv)
