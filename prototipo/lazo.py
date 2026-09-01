"""Orquestador del lazo en vivo: decisión (5A) -> validación -> orden -> conector -> verificación -> traza."""
import json, os, sys, yaml
from prototipo import triaje, orden as ordenm, conector, validacion, verificacion, perfil as perfilm, catalogo as catm

def procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp, leer=input):
    decision = triaje.procesar(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp)
    veredicto = None
    if decision.get("requiere_humano"):
        veredicto = validacion.pedir(decision, alerta, leer=leer)
        if veredicto in ("rechazar", "modificar"):
            # "modificar" retiene la alerta sin ejecutar la acción propuesta (salvaguarda honesta):
            # elegir una acción alternativa concreta es trabajo futuro (semilla en veredicto_humano).
            return {**decision, "veredicto_humano": veredicto, "orden": None, "ejecucion": None, "verificacion": None}
    o = ordenm.construir(decision, alerta)
    if o is None:
        return {**decision, "veredicto_humano": veredicto, "orden": None, "ejecucion": None, "verificacion": None}
    ejecucion = conector.ejecutar_orden(o, catalogo, ejecutor, timestamp)
    verif = verificacion.confirmar(o, catalogo, ejecutor)
    return {**decision, "veredicto_humano": veredicto, "orden": o, "ejecucion": ejecucion, "verificacion": verif}

class _EjecutorAuto:
    """Ejecutor falso para --auto (sin laboratorio), con estado como el EjecutorFalso de los tests:
    la primera verificación (pre-check) da "no está"; tras aplicar la acción, la re-verificación
    da "sí está". Así --auto puede mostrar un lazo con ejecucion.exito y verificacion.verificado
    en True sin necesitar el laboratorio Containerlab."""
    def __init__(self):
        self._vistos = {}      # nodo_ip -> comandos de verificación (con grep) ya vistos
        self._aplicado = set()  # (nodo_ip, comando_de_verificacion) que ya deben dar "sí está"

    def __call__(self, nodo_ip, comando):
        if "grep" in comando:   # comando de verificación
            self._vistos.setdefault(nodo_ip, set()).add(comando)
            return (0, "(simulado)") if (nodo_ip, comando) in self._aplicado else (1, "")
        # comando de aplicación: marca aplicadas las verificaciones ya vistas para este nodo
        for c in self._vistos.get(nodo_ip, set()):
            self._aplicado.add((nodo_ip, c))
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
    ejecutor = _EjecutorAuto() if auto else conector.ejecutor_ssh_lab
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
