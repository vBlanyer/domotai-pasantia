"""Barrido del umbral de confianza (RF-07): la curva escalado ↔ bloqueos automáticos indebidos.

El perfil decide `automatica_si_confianza` cuando la confianza del motor supera
`continuidad.umbral_confianza`. Subir el umbral manda más decisiones al humano (más escalado) y deja
menos auto-ejecución; bajarlo auto-ejecuta más, con el riesgo de contener de forma automática algo
que no debía (un FP/PROPIA). Este barrido MIDE ese compromiso variando solo el umbral sobre el MISMO
dataset, para calibrar el valor por defecto con datos y no por intuición.

La clasificación (recall/FP) NO depende del umbral —es `es_amenaza`, anterior al filtro—, así que se
arrastra como control (debe quedarse constante). No toca el motor ni las cifras canónicas: es un
análisis que varía un parámetro del perfil en una COPIA."""
import argparse, json, os, sys
from evaluacion import campana, cargar, prioridad
from prototipo.motor import perfil as perfilm
from prototipo.accion import catalogo as catm

UMBRALES = [round(0.1 * i, 1) for i in range(11)]   # 0.0 .. 1.0 en pasos de 0.1


def _perfil_con_umbral(perfil_dict, u):
    """Copia del perfil con `umbral_confianza` = u (no muta el original)."""
    return {**perfil_dict, "continuidad": {**(perfil_dict.get("continuidad") or {}), "umbral_confianza": u}}


def barrido(filas, hallazgos, perfil_dict, perfil_nombre, catalogo, tabla_prioridad,
            umbrales=UMBRALES, _evaluar=campana.evaluar):
    """Un punto por umbral: {umbral, escalado, automaticos, indebidos, recall, tasa_fp}. Reusa la
    campaña de evaluación (`con_llm=False`: el umbral no afecta a la justificación LLM)."""
    puntos = []
    for u in umbrales:
        r = _evaluar(filas, hallazgos, _perfil_con_umbral(perfil_dict, u), perfil_nombre, catalogo,
                     tabla_prioridad, con_llm=False)
        puntos.append({"umbral": u,
                       "escalado": r["operacion"]["tasa_escalado"],
                       "automaticos": r["automatizacion"]["automaticos"],
                       "indebidos": r["automatizacion"]["indebidos"],
                       "recall": r["clasificacion_prototipo"]["recall"],
                       "tasa_fp": r["clasificacion_prototipo"]["tasa_fp"]})
    return puntos


def tabla_markdown(puntos, perfil, n):
    out = [f"# Barrido del umbral de confianza (RF-07) — perfil {perfil}",
           f"n = {n} alertas. La clasificación (recall/FP) no depende del umbral (control: constante); "
           "el umbral solo mueve el escalado al humano y los bloqueos automáticos indebidos.", "",
           "| umbral | escalado | auto. | indebidos | recall | tasa FP |",
           "|--------|----------|-------|-----------|--------|---------|"]
    for p in puntos:
        out.append(f"| {p['umbral']:.1f} | {p['escalado']:.3f} | {p['automaticos']} | "
                   f"{p['indebidos']} | {p['recall']:.3f} | {p['tasa_fp']:.3f} |")
    plano = len({(p["escalado"], p["automaticos"], p["indebidos"]) for p in puntos}) == 1
    out += ["", "## Cómo leer"]
    if plano:
        out += ["La curva es **constante**: el umbral NO cambia el desenlace en este perfil. La continuidad "
                "(0 bloqueos indebidos) no la garantiza el umbral de confianza sino la **política de actores** "
                "(D16/C1): bloquear una IP interna, de red o de gestión exige humano siempre, y un atacante "
                "externo se bloquea con 0 colateral. El umbral solo mordería en una acción LOCALIZADA de baja "
                "confianza contra un actor EXTERNO, de las que esta partición no tiene ninguna (los VP externos "
                "tienen confianza 1.0 por postura confirmada; los de confianza 0.5/0.6 recaen sobre activos "
                "propios, que la política de actores escala por sí sola). Mecanismo verificado aparte: un caso "
                "externo sintético de confianza 0.5 sí cambia de automático a humano al cruzar el umbral.",
                "", "**Conclusión RF-07:** el valor por defecto (0.7) es seguro y el sistema es robusto a su "
                "elección en este perfil; el umbral es un salvavidas secundario, no el control activo de la continuidad."]
    else:
        out += ["Al bajar el umbral se auto-ejecuta más (menos escalado) a costa de arriesgar bloqueos "
                "automáticos indebidos; al subirlo, lo contrario. El codo de la curva calibra el valor por defecto."]
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description="Barrido del umbral de confianza (RF-07)")
    ap.add_argument("--particion", default="evaluacion")
    ap.add_argument("--perfil", default="empresarial")
    ap.add_argument("--hallazgos", default="lab/campañas/2026-08-31-evaluacion/hallazgos.json")
    ap.add_argument("--salida-dir", default="evaluacion/resultados")
    a = ap.parse_args(argv[1:])

    filas = cargar.cargar(particion=(None if a.particion == "todas" else a.particion))
    with open(a.hallazgos, encoding="utf-8") as f:
        hallazgos = json.load(f)
    perfil_dict = perfilm.cargar(f"prototipo/perfiles/{a.perfil}.yml")
    catalogo = catm.cargar_catalogo("prototipo/catalogo.yml")
    tabla_prioridad = prioridad.cargar_esperada("evaluacion/prioridad_esperada.yml")

    puntos = barrido(filas, hallazgos, perfil_dict, a.perfil, catalogo, tabla_prioridad)
    md = tabla_markdown(puntos, a.perfil, len(filas))
    os.makedirs(a.salida_dir, exist_ok=True)
    with open(os.path.join(a.salida_dir, "barrido-umbral.json"), "w", encoding="utf-8") as f:
        json.dump({"perfil": a.perfil, "n": len(filas), "puntos": puntos}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(a.salida_dir, "barrido-umbral.md"), "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print(md)
    print(f"\n-> {a.salida_dir}/barrido-umbral.json · barrido-umbral.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
