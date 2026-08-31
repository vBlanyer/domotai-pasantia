"""CLI: alerts.json crudo -> registros normalizados (una etapa de la tubería)."""
import json, sys
from lab.dataset import esquema

def normalizar_fichero(ruta_alerts, campaña):
    regs = []
    with open(ruta_alerts, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                cruda = json.loads(linea)
            except json.JSONDecodeError:
                continue  # línea corrupta: se salta, no rompe el fichero (formato JSONL)
            regs.append(esquema.normalizar_alerta(cruda, campaña))
    return regs

def main(argv):
    ruta, campaña, salida = argv[1], argv[2], argv[3]
    regs = normalizar_fichero(ruta, campaña)
    with open(salida, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(regs)} alertas normalizadas -> {salida}")

if __name__ == "__main__":
    main(sys.argv)
