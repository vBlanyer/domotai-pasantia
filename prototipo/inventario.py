"""Reconciliación del inventario declarado con la red descubierta (RF-17).

Compara lo que el cliente declara en su perfil (`activos` y sus `servicios_prestados`) con lo que el
auditor vio en la red (hallazgos de Nmap). Hace visibles las discrepancias en vez de resolverlas: si
un puerto abierto no declarado es una exposición o un olvido del inventario, lo decide el cliente.

Uso:  python3 -m prototipo.inventario <perfil.yml> <hallazgos.json>
"""
import json, sys
from prototipo import impacto, perfil as perfilm


def reconciliar(perfil, hallazgos):
    """{activos: {nombre: {abiertos_no_declarados, declarados_no_abiertos}}, no_inventariados,
    no_escaneados}. Un activo no escaneado no se compara: no escaneado no es «sin servicios»."""
    activos = (perfil or {}).get("activos") or {}
    nodos = (hallazgos or {}).get("nodos") or {}
    por_activo = {}
    for nombre in sorted(activos):
        abiertos = impacto.puertos_abiertos(hallazgos, nombre)
        if abiertos is None:
            continue
        declarados = set((activos[nombre] or {}).get("servicios_prestados") or [])
        por_activo[nombre] = {
            "abiertos_no_declarados": [{"puerto": p, "servicio": abiertos[p]}
                                       for p in sorted(set(abiertos) - declarados)],
            "declarados_no_abiertos": sorted(declarados - set(abiertos)),
        }
    return {"activos": por_activo,
            "no_inventariados": sorted(set(nodos) - set(activos)),
            "no_escaneados": sorted(set(activos) - set(nodos))}


def formatear(rep):
    lineas = []
    for nombre, r in rep["activos"].items():
        nd, dn = r["abiertos_no_declarados"], r["declarados_no_abiertos"]
        if nd:
            lineas.append(f"{nombre}: {len(nd)} abierto(s) no declarado(s) (exposición no reconocida): "
                          + ", ".join(f"{s['servicio']}/{s['puerto']}" for s in nd))
        if dn:
            lineas.append(f"{nombre}: declarado(s) y no abierto(s) (¿servicio caído?): "
                          + ", ".join(map(str, dn)))
        if not nd and not dn:
            lineas.append(f"{nombre}: coincide con lo declarado")
    if rep["no_inventariados"]:
        lineas.append("escaneados y no inventariados: " + ", ".join(rep["no_inventariados"]))
    if rep["no_escaneados"]:
        lineas.append("inventariados y no escaneados: " + ", ".join(rep["no_escaneados"]))
    return "\n".join(lineas)


def main(argv):
    if len(argv) != 2:
        print("uso: python3 -m prototipo.inventario <perfil.yml> <hallazgos.json>")
        return 2
    perfil = perfilm.cargar(argv[0])
    with open(argv[1], encoding="utf-8") as f:
        hallazgos = json.load(f)
    print(formatear(reconciliar(perfil, hallazgos)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
