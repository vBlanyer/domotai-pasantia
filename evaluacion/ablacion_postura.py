"""Ablación de postura: ¿cuánto margen tendría un LLM como segunda opinión en los casos grises?

Dimensiona la mejora B.1 (trabajo futuro, `estado-y-riesgos` §7) y sostiene la decisión D15 (los
modelos de lenguaje asisten el triaje, no deciden la clase). Replica EXACTAMENTE el pipeline de la
campaña —ráfaga incluida: sin ella la 6ª regla no actúa y los grises reales desaparecen— y compara
dos escenarios sobre la misma partición:

  - postura real del auditor: los grises son los que ya van al humano;
  - postura retirada (el auditor no escaneó nada): el peor caso para el clasificador determinista.

En cada uno cuenta los casos grises (confianza bajo el umbral del perfil) y cuántos acertaría el
fallback determinista, que es tratar todo gris como VP. El margen para una segunda opinión es lo que
ese fallback falla: se mide, no se estima.

Uso:  python3 -m evaluacion.ablacion_postura [--particion evaluacion|entrenamiento|todas]
                                             [--perfil empresarial] [--hallazgos RUTA]
"""
import argparse, copy, json
from collections import Counter

from evaluacion import cargar, prediccion
from prototipo import rafaga, catalogo as catm, perfil as perfilm

SOPORTADAS = ("VP", "FP", "PROPIA")


def grises(filas, hallazgos, perfil_dict, catalogo, umbral):
    """Pares (fila, predicción) de las alertas soportadas con confianza por debajo de `umbral`.

    Trabaja sobre una copia: la ráfaga se anota en las filas (`rafaga_60s`) y no debe filtrarse al
    llamador, que podría reutilizarlas en otro escenario."""
    filas = copy.deepcopy(filas)
    rafaga.contar_en_lote(filas)                      # igual que evaluacion.campana.evaluar
    preds = prediccion.predecir_todas(filas, hallazgos, perfil_dict, "ablacion", catalogo)
    return [(f, p) for f, p in zip(filas, preds)
            if f.get("etiqueta") in SOPORTADAS and p["confianza"] < umbral]


def resumen(pares):
    """Cuántos grises hay, su verdad, y cuántos acierta el fallback «todo gris es VP»."""
    vp = sum(1 for f, _ in pares if f["etiqueta"] == "VP")
    return {"n": len(pares),
            "por_verdad": dict(Counter(f["etiqueta"] for f, _ in pares)),
            "aciertos_fallback_vp": vp,
            "margen_max": len(pares) - vp}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ablación de postura: margen para un LLM en los grises")
    ap.add_argument("--particion", default="evaluacion")
    ap.add_argument("--perfil", default="empresarial")
    ap.add_argument("--hallazgos", default="lab/campañas/2026-08-31-evaluacion/hallazgos.json")
    a = ap.parse_args(argv)

    filas = cargar.cargar(particion=(None if a.particion == "todas" else a.particion))
    with open(a.hallazgos, encoding="utf-8") as f:
        hallazgos = json.load(f)
    perfil_dict = perfilm.cargar(f"prototipo/perfiles/{a.perfil}.yml")
    catalogo = catm.cargar_catalogo("prototipo/catalogo.yml")
    umbral = perfil_dict.get("continuidad", {}).get("umbral_confianza", perfilm.UMBRAL_CONFIANZA)

    print(f"Ablación de postura · partición {a.particion} ({len(filas)} alertas) · perfil {a.perfil} "
          f"· umbral {umbral}")
    for nombre, hall in (("postura real", hallazgos), ("postura retirada", {"nodos": {}})):
        pares = grises(filas, hall, perfil_dict, catalogo, umbral)
        r = resumen(pares)
        print(f"\n[{nombre}] grises: {r['n']} · verdad: {r['por_verdad']} · fallback «gris = VP» acierta "
              f"{r['aciertos_fallback_vp']}/{r['n']} · margen máximo para una segunda opinión: "
              f"{r['margen_max']}")
        print("  por (familia, verdad):", dict(Counter((f["familia"], f["etiqueta"]) for f, _ in pares)))
        for f, p in pares:
            if f["etiqueta"] != "VP":
                print(f"  no-VP: {f['id_alerta']} · {f['origen_ip']} -> {f['activo']} ({f['servicio']}) "
                      f"· verdad {f['etiqueta']} por «{f.get('etiqueta_por')}» · ráfaga {f.get('rafaga_60s')}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
