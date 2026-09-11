"""Orquestador del lazo en vivo: decisión (5A) -> validación -> orden -> conector -> verificación -> traza."""
import json, os, sys, yaml
from prototipo import traza, triaje, orden as ordenm, conector, validacion, verificacion, perfil as perfilm, catalogo as catm, analisis

def procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp,
                  leer=input, justificar_fn=analisis.justificar, mitigar_fn=None):
    decision = triaje.procesar(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp,
                               justificar_fn=justificar_fn)
    # Modo agente: si hay contención que aplicar, delega la mitigación al agente ReAct, que decide la
    # estrategia, ESCALA de dispositivo y aprueba POR PASO (RF-08). El daemon no hace su prompt único.
    if mitigar_fn is not None and decision.get("accion_final"):
        plan = mitigar_fn(decision, alerta, leer)
        return {**decision, "veredicto_humano": None, "clase_reclasificada": None,
                "mitigacion_agente": plan, "orden": None, "ejecucion": None, "verificacion": None}
    veredicto, clase_reclasificada = None, None
    if decision.get("requiere_humano"):
        v = validacion.pedir(decision, alerta, leer=leer)
        veredicto, clase_reclasificada = v["veredicto"], v.get("clase_nueva")
        if veredicto in ("rechazar", "reclasificar"):
            # "reclasificar" retiene la alerta sin ejecutar la acción propuesta y registra la clase
            # corregida por el analista como feedback (RF-08/RF-12): si el triaje se equivocó de clase,
            # no se ejecuta su acción.
            return {**decision, "veredicto_humano": veredicto, "clase_reclasificada": clase_reclasificada,
                    "orden": None, "ejecucion": None, "verificacion": None}
    o = ordenm.construir(decision, alerta)
    if o is None:
        return {**decision, "veredicto_humano": veredicto, "clase_reclasificada": clase_reclasificada,
                "orden": None, "ejecucion": None, "verificacion": None}
    ejecucion = conector.ejecutar_orden(o, catalogo, ejecutor, timestamp)
    verif = verificacion.confirmar(o, catalogo, ejecutor)
    # Escalada por defecto (requisito del tutor industrial): si el paso en el activo no se pudo
    # ejecutar o no se verifica y el perfil describe una topologia, se sigue la cadena de
    # contencion hacia el perimetro, con el filtro del perfil en cada salto. Sin topologia no hay
    # a donde escalar y la traza lo deja como esta: exito=False, verificado=False.
    escalada = None
    if not (ejecucion.get("exito") and verif.get("verificado")) and perfil.get("topologia"):
        from prototipo import agente_mitigacion as ag
        escalada = ag.escalar_determinista(alerta, decision.get("clase"), perfil, catalogo, ejecutor,
                                           leer=leer, timestamp=timestamp, desde=o.get("nodo_objetivo"),
                                           confianza=decision.get("confianza", 1.0), siempre_humano=False,
                                           decision_id=id_decision)
    return {**decision, "veredicto_humano": veredicto, "clase_reclasificada": clase_reclasificada,
            "orden": o, "ejecucion": ejecucion, "verificacion": verif, "escalada": escalada}

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
    ejecutor = _EjecutorAuto() if auto else conector.ejecutor_por_defecto()
    n = 0
    with open(alertas_path, encoding="utf-8") as fin, open(salida, "w", encoding="utf-8") as fout:
        cadena = traza.Cadena(fout)               # fichero nuevo: la cadena empieza en GENESIS
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
            cadena.escribir(r)
            n += 1
    print(f"{n} pasos del lazo -> {salida}")

if __name__ == "__main__":
    main(sys.argv)
