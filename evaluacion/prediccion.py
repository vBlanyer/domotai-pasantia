"""Corre el motor de triaje por alerta y mapea la traza a prediccion binaria + tiempo."""
import time
from prototipo import triaje

# Nota: una traza sin clase (None) cuenta como no-amenaza (negativo benigno).
# `amenaza_enrutada` (nivel triar_y_enrutar) es una amenaza reconocida que se encamina en vez de
# contenerse: cuenta como amenaza para la detección (no es vp_* pero sí es positivo verdadero).
def es_amenaza(clase):
    return str(clase).startswith("vp_") or clase == "amenaza_enrutada"

def predecir_todas(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, _procesar=triaje.procesar):
    res = []
    for i, fila in enumerate(filas):
        t0 = time.perf_counter()
        traza = _procesar(fila, hallazgos, perfil_dict, perfil_nombre, catalogo,
                          id_decision=f"e{i}", timestamp=fila.get("timestamp", ""))
        ms = (time.perf_counter() - t0) * 1000.0
        res.append({
            "id_alerta": fila.get("id_alerta"),
            "clase": traza.get("clase"),
            "amenaza": es_amenaza(traza.get("clase")),
            "prioridad": traza.get("prioridad"),
            "confianza": traza.get("confianza"),
            "accion_final": traza.get("accion_final"),
            "impacto": traza.get("impacto"),
            "requiere_humano": traza.get("requiere_humano"),
            "ms": ms,
        })
    return res
