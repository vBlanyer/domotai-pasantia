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

def mostrar(decision, alerta):
    est = decision.get("justificacion_estructurada", {}) or {}
    mitre = ", ".join(est.get("tecnica_mitre") or []) or "—"
    return (
        "── Validación humana requerida ──\n"
        f"Activo: {alerta.get('activo')}  ·  Origen: {alerta.get('origen_ip')}  ·  Servicio: {alerta.get('servicio')}\n"
        f"Clase: {decision.get('clase')}  ·  Prioridad: {decision.get('prioridad')}  ·  Confianza: {decision.get('confianza')}\n"
        f"Técnica MITRE: {mitre}\n"
        f"Justificación: {decision.get('justificacion')}\n"
        f"Acción sugerida: {est.get('accion_sugerida', decision.get('accion_propuesta'))}  ·  Impacto: {decision.get('impacto')}  ·  Filtro: {decision.get('resultado_filtro')}\n"
        f"Acción final: {decision.get('accion_final')}\n"
    )

def pedir(decision, alerta, leer=input, escribir=print):
    escribir(mostrar(decision, alerta))
    resp = leer("¿aprobar / rechazar / reclasificar? ").strip().lower()
    if resp.startswith("a"):
        return {"veredicto": "aprobar", "clase_nueva": None}
    if resp.startswith("recl"):
        return _elegir_clase(decision, leer, escribir)
    return {"veredicto": "rechazar", "clase_nueva": None}   # por defecto, seguro

def _elegir_clase(decision, leer, escribir):
    """Menú numerado de las clases válidas menos la actual. Número válido -> reclasificar con esa
    clase; entrada inválida -> repregunta; Enter en blanco -> rechazar (seguro, sin corregir)."""
    opciones = [c for c in CLASES if c != decision.get("clase")]
    menu = "Nueva clase:\n" + "\n".join(f"  {i}) {c}" for i, c in enumerate(opciones, 1))
    while True:
        escribir(menu)
        resp = leer(f"Elige [1-{len(opciones)}]: ").strip()
        if not resp:                                       # se echa atrás -> rechazar seguro
            return {"veredicto": "rechazar", "clase_nueva": None}
        if resp.isdigit() and 1 <= int(resp) <= len(opciones):
            return {"veredicto": "reclasificar", "clase_nueva": opciones[int(resp) - 1]}
        escribir("  opción no válida; elige un número de la lista")
