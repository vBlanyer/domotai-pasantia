"""Validación humana por terminal (RF-08): muestra la decisión y captura el veredicto.

Veredictos: "aprobar" ejecuta la acción propuesta; "rechazar" retiene sin ejecutar; "reclasificar"
retiene sin ejecutar y captura la **clase corregida** por el analista, que el lazo registra como
feedback (RF-12) — si el triaje se equivocó de clase, no se ejecuta su acción. `pedir` devuelve un
dict `{"veredicto", "clase_nueva"}` (`clase_nueva` solo con "reclasificar").

La clase corregida se elige de un **menú cerrado** (las clases de `analisis.CLASES` menos la actual
del incidente), no por texto libre: así no entran typos ni clases inexistentes al feedback (misma
filosofía de catálogo cerrado que RF-15).
"""
from prototipo.analisis import CLASES

def filtro_legible(decision):
    """Qué significa para el analista el `resultado_filtro` (el valor de la traza no cambia). `veta`
    tiene dos lecturas según haya acción final: RETENIDA (se ejecuta si el analista aprueba) o VETADA
    (veto duro: gestión, sin reversión o fuera del catálogo; no se ejecuta aunque se apruebe)."""
    r, final = decision.get("resultado_filtro"), decision.get("accion_final")
    if r == "veta":
        return "retenida — espera tu aprobación" if final else "vetada — no se puede ejecutar"
    if r == "degrada":
        txt = f"degradada — se sustituye por {final}"
        return txt + "; espera tu aprobación" if decision.get("requiere_humano") else txt
    return {"permite": "automática", "sin_accion": "sin acción"}.get(r, str(r))

def mostrar(decision, alerta):
    est = decision.get("justificacion_estructurada", {}) or {}
    mitre = ", ".join(est.get("tecnica_mitre") or []) or "—"
    # La consecuencia de aprobar: a quién bloquea y qué servicios detiene (impacto determinado, RF-17).
    det = decision.get("impacto_determinado") or {}
    motivo = det.get("motivo")
    if motivo and decision.get("accion_final") is None:
        # Sin acción final no hay nada que aprobar: la consecuencia es la del veto duro, no la de
        # una acción que se fuera a ejecutar. Sin el prefijo se lee como si ya hubiera pasado.
        motivo = f"(vetada) {motivo}"
    consecuencia = f"Consecuencia: {motivo}\n" if motivo else ""
    return (
        "── Validación humana requerida ──\n"
        f"Activo: {alerta.get('activo')}  ·  Origen: {alerta.get('origen_ip')}  ·  Servicio: {alerta.get('servicio')}\n"
        f"Clase: {decision.get('clase')}  ·  Prioridad: {decision.get('prioridad')}  ·  Confianza: {decision.get('confianza')}\n"
        f"Técnica MITRE: {mitre}\n"
        f"Justificación: {decision.get('justificacion')}\n"
        f"Acción sugerida: {est.get('accion_sugerida', decision.get('accion_propuesta'))}  ·  Impacto: {decision.get('impacto')}  ·  Filtro: {filtro_legible(decision)}\n"
        f"{consecuencia}"
        f"Acción final: {decision.get('accion_final')}\n"
    )

def _menu(escribir, leer, titulo, etiquetas):
    """Menú numerado cerrado, compartido por el prompt de veredicto y el de clase. Devuelve el índice
    0-based elegido, o None si el analista deja la respuesta en blanco (se echa atrás). Entrada
    inválida (no es un número de la lista) -> repregunta. Números, no texto libre: sin typos ni
    opciones inexistentes (misma filosofía de catálogo cerrado que RF-15)."""
    cuerpo = titulo + "\n" + "\n".join(f"  {i}) {e}" for i, e in enumerate(etiquetas, 1))
    while True:
        escribir(cuerpo)
        resp = leer(f"Elige [1-{len(etiquetas)}]: ").strip()
        if not resp:
            return None
        if resp.isdigit() and 1 <= int(resp) <= len(etiquetas):
            return int(resp) - 1
        escribir("  opción no válida; elige un número de la lista")

_VEREDICTOS = ("aprobar", "rechazar", "reclasificar")
_ETIQUETAS_VEREDICTO = ("aprobar       — ejecuta la acción propuesta",
                        "rechazar      — retiene sin ejecutar",
                        "reclasificar  — corrige la clase")

def pedir(decision, alerta, leer=input, escribir=print):
    escribir(mostrar(decision, alerta))
    i = _menu(escribir, leer, "¿Qué hacer con este incidente?", _ETIQUETAS_VEREDICTO)
    veredicto = _VEREDICTOS[i] if i is not None else "rechazar"   # en blanco -> rechazar seguro
    if veredicto == "aprobar":
        return {"veredicto": "aprobar", "clase_nueva": None}
    if veredicto == "reclasificar":
        return _elegir_clase(decision, leer, escribir)
    return {"veredicto": "rechazar", "clase_nueva": None}

def _elegir_clase(decision, leer, escribir):
    """Submenú de clases: las de `analisis.CLASES` menos la actual del incidente (reclasificar es
    cambiarla, no repetirla). Índice válido -> reclasificar con esa clase; en blanco -> rechazar
    (se echa atrás, sin corregir)."""
    opciones = [c for c in CLASES if c != decision.get("clase")]
    i = _menu(escribir, leer, "Nueva clase:", opciones)
    if i is None:
        return {"veredicto": "rechazar", "clase_nueva": None}
    return {"veredicto": "reclasificar", "clase_nueva": opciones[i]}
