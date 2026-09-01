"""Validación humana por terminal (D11): muestra la decisión y captura el veredicto (RF-08).

Veredictos: "aprobar" ejecuta la acción propuesta; "rechazar" y "modificar" retienen la alerta
sin ejecutar nada. "modificar" NO sustituye la acción por una alternativa concreta (eso es trabajo
futuro) -- hoy es una salvaguarda honesta: se registra el veredicto en la traza como semilla para
esa sustitución futura, pero el lazo no ejecuta la acción original bajo ese veredicto.
"""

def mostrar(decision, alerta):
    return (
        "── Validación humana requerida ──\n"
        f"Activo: {alerta.get('activo')}  ·  Origen: {alerta.get('origen_ip')}  ·  Servicio: {alerta.get('servicio')}\n"
        f"Clase: {decision.get('clase')}  ·  Prioridad: {decision.get('prioridad')}  ·  Confianza: {decision.get('confianza')}\n"
        f"Justificación: {decision.get('justificacion')}\n"
        f"Acción propuesta: {decision.get('accion_propuesta')}  ·  Impacto: {decision.get('impacto')}  ·  Filtro: {decision.get('resultado_filtro')}\n"
        f"Acción final: {decision.get('accion_final')}\n"
    )

def pedir(decision, alerta, leer=input, escribir=print):
    escribir(mostrar(decision, alerta))
    resp = leer("¿aprobar / rechazar / modificar? ").strip().lower()
    if resp.startswith("a"):
        return "aprobar"
    if resp.startswith("m"):
        return "modificar"
    return "rechazar"   # por defecto, seguro
