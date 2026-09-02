"""Corre el justificador LLM 1B sobre las alertas soportadas y mide el anclaje (RNF-02)."""
from prototipo import analisis
from prototipo import justificador_llm

def soportadas(filas):
    return [f for f in filas if f.get("etiqueta") in ("VP", "FP")]

def medir(filas, hallazgos, perfil_dict, generador=justificador_llm.generador_llama, recuperar_fn=None):
    res = []
    for fila in soportadas(filas):
        contexto = analisis.enriquecer(fila, hallazgos, perfil_dict)
        clase = analisis.clasificar(fila, contexto)["clase"]
        if recuperar_fn is not None:
            r = justificador_llm.justificar_con_rag(fila, contexto, clase, generador, recuperar_fn)
        else:
            r = justificador_llm.justificar_llm(fila, contexto, clase, generador)
        res.append({"id_alerta": fila.get("id_alerta"), "etiqueta": fila.get("etiqueta"),
                    "justificador": r["justificador"], "anclaje_verificado": r["anclaje_verificado"],
                    "texto": r["texto"], "pasajes_usados": r.get("pasajes_usados", [])})
    return res

def resumen(resultados):
    usaron_llm = [r for r in resultados if r["justificador"] == "llm"]
    anclados = sum(1 for r in usaron_llm if r["anclaje_verificado"])
    degradados = sum(1 for r in resultados if r["justificador"] == "plantilla")
    # pct_anclaje is the meaningful rate: LLM-anchored vs degraded to template,
    # because justificar_llm only tags "llm" when anchoring check already passed.
    total = len(usaron_llm) + degradados
    pct = len(usaron_llm) / total if total else "n/d"
    return {"llm_total": len(usaron_llm), "anclados": anclados,
            "degradados": degradados, "pct_anclaje": pct}
