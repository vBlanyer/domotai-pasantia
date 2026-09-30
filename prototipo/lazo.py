"""Orquestador del lazo en vivo: decisión (5A) -> validación -> orden -> conector -> verificación -> traza."""
import json, os, sys, yaml
from prototipo import traza, triaje, orden as ordenm, conector, validacion, verificacion, perfil as perfilm, catalogo as catm, analisis

def decidir_incidente(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp,
                      justificar_fn=analisis.justificar):
    """1ª fase: clasifica y decide (rápido, sin ejecutar ni pedir humano). Devuelve la decisión."""
    return triaje.procesar(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp,
                           justificar_fn=justificar_fn)


class _PreguntaPendiente(Exception):
    """La escalada necesita a un humano y el lazo no puede esperarle (modo web no bloqueante)."""


def _escalar(alerta, decision, perfil, catalogo, ejecutor, leer, timestamp, desde, id_decision,
             escribir=print):
    from prototipo import agente_mitigacion as ag
    return ag.escalar_determinista(alerta, decision.get("clase"), perfil, catalogo, ejecutor,
                                   leer=leer, escribir=escribir, timestamp=timestamp, desde=desde,
                                   confianza=decision.get("confianza", 1.0), siempre_humano=False,
                                   decision_id=id_decision)


def _lineas_de_la_pregunta(lineas):
    """Las líneas de la última pregunta (desde su «── Validación humana ──»), sin las de saltos ya
    respondidos: son las que ve el analista en la tarjeta."""
    inicios = [i for i, l in enumerate(lineas) if l.startswith("── Validación humana")]
    return lineas[inicios[-1]:] if inicios else lineas


def _acumular(parcial, excepcion=None, respuesta=None):
    """Lleva en `escalada_previa` lo que ya hizo la escalada antes de diferirse (pasos, reglas
    aplicadas, respuestas del analista): una escalada diferida varias veces se traza entera."""
    previa = parcial.get("escalada_previa") or {"pasos": [], "reversiones": [], "veredictos": []}
    return {"pasos": previa["pasos"] + list(getattr(excepcion, "pasos", [])),
            "reversiones": previa["reversiones"] + list(getattr(excepcion, "reversiones", [])),
            "veredictos": previa["veredictos"] + ([] if respuesta is None else
                                                  ["aprobar" if respuesta.lower().startswith("s") else "rechazar"])}


def _fusionar(escalada, previa):
    if not previa or escalada is None:
        return escalada
    return {**escalada, "pasos": previa["pasos"] + escalada.get("pasos", []),
            "reversiones": previa["reversiones"] + escalada.get("reversiones", []),
            "escalado": True}


def reanudar_escalada(parcial, alerta, perfil, catalogo, ejecutor, respuesta, desde, timestamp,
                      diferir_escalada=None):
    """Retoma una escalada diferida con la respuesta del analista ("s" aprueba). La pregunta se
    hace antes de ejecutar en cada dispositivo, así que retomar desde `desde` no repite nada que
    haya tenido efecto. Devuelve el registro final para la traza.

    La respuesta vale solo para el salto que el analista vio: si el siguiente también pide humano,
    se difiere otra vez con `diferir_escalada` (nueva tarjeta, devuelve `en_cola`); sin él, ese
    salto no se aprueba."""
    base = {k: v for k, v in parcial.items() if k not in ("en_cola", "escalada_previa")}
    respondidas, lineas = [], []
    def _una_respuesta(prompt=""):
        if not respondidas:
            respondidas.append(prompt)
            return respuesta
        if diferir_escalada is None:
            return ""
        raise _PreguntaPendiente(prompt)
    try:
        escalada = _escalar(alerta, parcial, perfil, catalogo, ejecutor, _una_respuesta, timestamp,
                            desde, parcial.get("id_decision", ""), escribir=lineas.append)
    except _PreguntaPendiente as e:
        diferir_escalada({**base, "escalada_previa": _acumular(parcial, e, respuesta)}, alerta,
                         getattr(e, "reanudar_desde", desde), _lineas_de_la_pregunta(lineas))
        return {**base, "escalada": None, "en_cola": True}
    previa = _acumular(parcial, respuesta=respuesta)
    return {**base, "escalada": _fusionar(escalada, previa), "veredictos_escalada": previa["veredictos"]}


def aplicar_veredicto(decision, alerta, perfil, catalogo, ejecutor, id_decision, timestamp,
                      veredicto=None, clase_reclasificada=None, leer=input, diferir_escalada=None):
    """2ª fase: dado el veredicto (None=automático, 'aprobar', 'rechazar', 'reclasificar'), ejecuta la
    contención + verifica + escala, o retiene. Es lo que corre DESPUÉS de que el humano responde (o
    inline en el camino automático). Devuelve el registro finalizado para la traza.

    Con `diferir_escalada(parcial, alerta, desde, lineas)` (modo web), si la escalada necesita
    preguntar no se bloquea: se entrega el contexto para reanudarla y se devuelve `en_cola`."""
    if veredicto in ("rechazar", "reclasificar"):
        # "reclasificar" retiene la alerta sin ejecutar la acción propuesta y registra la clase
        # corregida por el analista como feedback (RF-08/RF-12): si el triaje se equivocó de clase,
        # no se ejecuta su acción.
        return {**decision, "veredicto_humano": veredicto, "clase_reclasificada": clase_reclasificada,
                "orden": None, "ejecucion": None, "verificacion": None}
    o = ordenm.construir(decision, alerta, perfil)
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
    parcial = {**decision, "veredicto_humano": veredicto, "clase_reclasificada": clase_reclasificada,
               "orden": o, "ejecucion": ejecucion, "verificacion": verif}
    if not (ejecucion.get("exito") and verif.get("verificado")) and perfil.get("topologia"):
        desde = o.get("nodo_objetivo")
        if diferir_escalada is None:
            escalada = _escalar(alerta, decision, perfil, catalogo, ejecutor, leer, timestamp, desde,
                                id_decision)
        else:
            lineas = []
            def _no_bloquear(prompt=""):
                raise _PreguntaPendiente(prompt)
            try:
                escalada = _escalar(alerta, decision, perfil, catalogo, ejecutor, _no_bloquear, timestamp,
                                    desde, id_decision, escribir=lineas.append)
            except _PreguntaPendiente as e:
                diferir_escalada({**parcial, "escalada_previa": _acumular(parcial, e)}, alerta,
                                 getattr(e, "reanudar_desde", desde), lineas)
                return {**parcial, "escalada": None, "en_cola": True}
    return {**parcial, "escalada": escalada}


def procesar_lazo(alerta, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, id_decision, timestamp,
                  leer=input, justificar_fn=analisis.justificar, mitigar_fn=None, escribir=print, encolar=None,
                  diferir_escalada=None):
    decision = decidir_incidente(alerta, hallazgos, perfil, perfil_nombre, catalogo, id_decision, timestamp,
                                 justificar_fn=justificar_fn)
    # Modo agente: si hay contención que aplicar, delega la mitigación al agente ReAct, que decide la
    # estrategia, ESCALA de dispositivo y aprueba POR PASO (RF-08). El daemon no hace su prompt único.
    if mitigar_fn is not None and decision.get("accion_final"):
        plan = mitigar_fn(decision, alerta, leer)
        return {**decision, "veredicto_humano": None, "clase_reclasificada": None,
                "mitigacion_agente": plan, "orden": None, "ejecucion": None, "verificacion": None}
    # Modo web no bloqueante: si requiere humano y hay `encolar`, se encola y se difiere; el veredicto
    # se aplica (ejecuta + traza) cuando el analista responde, sin bloquear el lazo.
    if encolar is not None and decision.get("requiere_humano"):
        encolar(decision, alerta)
        return {**decision, "veredicto_humano": None, "clase_reclasificada": None, "en_cola": True,
                "orden": None, "ejecucion": None, "verificacion": None}
    veredicto, clase_reclasificada = None, None
    if decision.get("requiere_humano"):
        v = validacion.pedir(decision, alerta, leer=leer, escribir=escribir)
        veredicto, clase_reclasificada = v["veredicto"], v.get("clase_nueva")
    return aplicar_veredicto(decision, alerta, perfil, catalogo, ejecutor, id_decision, timestamp,
                             veredicto=veredicto, clase_reclasificada=clase_reclasificada, leer=leer,
                             diferir_escalada=diferir_escalada)

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
        cadena = traza.Cadena(fout, nombre=os.path.basename(salida))   # fichero nuevo: empieza en GENESIS
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
