"""Orquesta el lazo de decisión: ingesta -> análisis -> política -> perfil -> traza."""
import json, os, sys, yaml
from prototipo import analisis, politica, perfil as perfilm, traza, catalogo as catm

def procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo, id_decision, timestamp):
    ctx = analisis.enriquecer(alerta, hallazgos, perfil_dict)
    clas = analisis.clasificar(alerta, ctx)
    just = analisis.justificar(alerta, ctx, clas["clase"])
    accion, params = politica.proponer(clas["clase"], alerta)
    impacto = catalogo[accion]["impacto"] if accion else "ninguno"
    filtro = perfilm.filtrar(perfil_dict, accion, params, catalogo, alerta.get("activo"),
                             alerta.get("servicio"), clas["confianza"])
    analisis_out = {**clas, "justificacion": just}
    return traza.construir(id_decision, timestamp, alerta, analisis_out, accion, impacto, perfil_nombre, filtro)

def main(argv):
    alertas_path, perfil_path, hallazgos_path, salida = argv[1:5]
    perfil_dict = perfilm.cargar(perfil_path)
    perfil_nombre = perfil_path.split("/")[-1].replace(".yml", "")
    with open(hallazgos_path, encoding="utf-8") as f:
        hallazgos = json.load(f)
    catalogo = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
    n = 0
    with open(alertas_path, encoding="utf-8") as fin, open(salida, "w", encoding="utf-8") as fout:
        for i, linea in enumerate(fin):
            linea = linea.strip()
            if not linea:
                continue
            try:
                alerta = json.loads(linea)
            except json.JSONDecodeError:
                continue
            ts = alerta.get("timestamp", "")
            r = procesar(alerta, hallazgos, perfil_dict, perfil_nombre, catalogo,
                         id_decision=f"d{i}", timestamp=ts)
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} decisiones -> {salida}")

if __name__ == "__main__":
    main(sys.argv)
