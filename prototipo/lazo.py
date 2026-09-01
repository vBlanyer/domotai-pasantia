"""Orquestador del lazo en vivo: decisión (5A) -> validación -> orden -> conector -> verificación -> traza."""
import json, os, sys, yaml
from prototipo import triaje, orden as ordenm, conector, validacion, verificacion, perfil as perfilm, catalogo as catm

def procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp, leer=input):
    decision = triaje.procesar(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp)
    veredicto = None
    if decision.get("requiere_humano"):
        veredicto = validacion.pedir(decision, alerta, leer=leer)
        if veredicto == "rechazar":
            return {**decision, "veredicto_humano": veredicto, "orden": None, "ejecucion": None, "verificacion": None}
    o = ordenm.construir(decision, alerta)
    if o is None:
        return {**decision, "veredicto_humano": veredicto, "orden": None, "ejecucion": None, "verificacion": None}
    ejecucion = conector.ejecutar_orden(o, catalogo, ejecutor, timestamp)
    verif = verificacion.confirmar(o, catalogo, ejecutor)
    return {**decision, "veredicto_humano": veredicto, "orden": o, "ejecucion": ejecucion, "verificacion": verif}

def _ejecutor_auto(nodo_ip, comando):   # ejecutor falso para --auto (sin laboratorio)
    if "grep" in comando:
        return (1, "")
    return (0, "(simulado)")

def main(argv):
    args = [a for a in argv[1:] if a != "--auto"]
    auto = "--auto" in argv
    alertas_path, perfil_path, hallazgos_path, salida = args[0:4]
    perfil = perfilm.cargar(perfil_path)
    perfil_nombre = os.path.basename(perfil_path).replace(".yml", "")
    with open(hallazgos_path, encoding="utf-8") as f:
        hallazgos = json.load(f)
    catalogo = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
    ejecutor = _ejecutor_auto if auto else conector.ejecutor_ssh_lab
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
            r = procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                              f"d{i}", alerta.get("timestamp", ""))
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} pasos del lazo -> {salida}")

if __name__ == "__main__":
    main(sys.argv)
