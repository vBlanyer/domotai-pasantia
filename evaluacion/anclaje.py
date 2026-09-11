"""Corre el justificador LLM sobre las alertas soportadas y mide el anclaje (RNF-02).

El resumen se desglosa por clase porque la tasa global esconde el comportamiento que
interesa: la justificacion de una amenaza y la de un descarte responden a preguntas
distintas y han fallado de formas distintas."""
from prototipo import analisis
from prototipo import justificador_llm

def soportadas(filas):
    return [f for f in filas if f.get("etiqueta") in ("VP", "FP")]

def medir(filas, hallazgos, perfil_dict, generador=None, recuperar_fn=None):
    # Se resuelve en la llamada, no al importar, para que respete la variable de entorno.
    generador = generador or justificador_llm.generador_por_defecto()
    res = []
    for fila in soportadas(filas):
        contexto = analisis.enriquecer(fila, hallazgos, perfil_dict)
        clase = analisis.clasificar(fila, contexto)["clase"]
        if recuperar_fn is not None:
            r = justificador_llm.justificar_con_rag(fila, contexto, clase, generador, recuperar_fn)
        else:
            r = justificador_llm.justificar_llm(fila, contexto, clase, generador)
        res.append({"id_alerta": fila.get("id_alerta"), "etiqueta": fila.get("etiqueta"),
                    # La clase decidida: sin ella no se puede leer el anclaje por clase, que es
                    # donde se vio que la recuperacion ayudaba a las amenazas y estropeaba los
                    # descartes. La tasa global no lo habria mostrado.
                    "clase": clase,
                    "justificador": r["justificador"], "anclaje_verificado": r["anclaje_verificado"],
                    # Sin esto, una corrida no dice con que modelo se hizo y deja de ser
                    # comparable con las anteriores (RF-09/RNF-03).
                    "version_justificador": r.get("version_justificador"),
                    "texto": r["texto"], "pasajes_usados": r.get("pasajes_usados", []),
                    "consulta_usada": r.get("consulta_usada", ""),
                    "recuperacion_agentica": r.get("recuperacion_agentica", False)})
    return res

def resumen(resultados):
    usaron_llm = [r for r in resultados if r["justificador"] == "llm"]
    anclados = sum(1 for r in usaron_llm if r["anclaje_verificado"])
    degradados = sum(1 for r in resultados if r["justificador"] == "plantilla")
    # pct_anclaje is the meaningful rate: LLM-anchored vs degraded to template,
    # because justificar_llm only tags "llm" when anchoring check already passed.
    total = len(usaron_llm) + degradados
    pct = len(usaron_llm) / total if total else "n/d"
    versiones = sorted({r.get("version_justificador") for r in resultados if r.get("version_justificador")})
    return {"llm_total": len(usaron_llm), "anclados": anclados,
            "degradados": degradados, "pct_anclaje": pct, "versiones": versiones,
            "por_clase": por_clase(resultados)}

def por_clase(resultados):
    """Anclaje desglosado por la clase que decidio el motor."""
    salida = {}
    for r in resultados:
        d = salida.setdefault(r.get("clase", "?"), {"llm": 0, "plantilla": 0})
        d["llm" if r["justificador"] == "llm" else "plantilla"] += 1
    for d in salida.values():
        total = d["llm"] + d["plantilla"]
        d["pct_anclaje"] = d["llm"] / total if total else "n/d"
    return salida
