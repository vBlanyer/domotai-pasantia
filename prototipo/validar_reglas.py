"""Validador de cobertura de reglas (#2): dice qué fracción de una muestra de alertas del SIEM del
cliente cubre el motor, ANTES de desplegar.

El motor clasifica por FAMILIA (el adaptador mapea grupos/reglas de Wazuh → familia). Si el ruleset
del cliente usa otros grupos/IDs, sus alertas caen en `otra` y el motor no actúa. Esta herramienta
toma una muestra del `alerts.json` del cliente y reporta cuántas caen en cada familia con playbook y
cuáles quedan sin cobertura (con su regla/grupos), para afinar el adaptador/ruleset en la fase de alta.

No necesita el entorno del cliente: basta una exportación de ejemplo de sus alertas.

    python3 -m prototipo.validar_reglas <muestra-alerts.json>
"""
import collections
import json
import sys

from prototipo import adaptador_wazuh, familias


def cobertura(crudas, campaña="validacion"):
    """Reporte de cobertura de una lista de alertas crudas de Wazuh:
    {total, propias, malformadas, por_familia:{fam:n}, cubiertas, sin_cobertura:[{regla_id,grupos}],
     soportadas, nivel:{fam:nivel}}.
    `cubiertas` = las de una familia con playbook (familias.registro()); el resto (`otra`/`plataforma`)
    van a `sin_cobertura`. La telemetría propia del triaje se descarta (propias). Una entrada que no
    sea un dict o reviente el adaptador (export sucio del cliente) se cuenta como `malformada` y NO
    aborta el informe —misma tolerancia que la barrera de `stream._parsear`—.
    Invariante: cubiertas + len(sin_cobertura) + propias + malformadas == total."""
    normalizar = adaptador_wazuh.adaptador(campaña)
    registro = familias.registro()
    soportadas = set(registro)
    por_familia = collections.Counter()
    sin_cobertura, propias, malformadas = [], 0, 0
    for c in crudas:
        if not isinstance(c, dict):
            malformadas += 1
            continue
        try:
            d = normalizar(c)
        except Exception:                              # contenedor hostil (rule=null, data=lista…)
            malformadas += 1
            continue
        if d is None:                                  # telemetría del propio triaje (ancla): no es del cliente
            propias += 1
            continue
        fam = d.get("familia")
        por_familia[fam] += 1
        if fam not in soportadas:
            sin_cobertura.append({"regla_id": d.get("regla_id"),
                                  "grupos": list((c.get("rule") or {}).get("groups", []))})
    return {"total": len(crudas), "propias": propias, "malformadas": malformadas,
            "por_familia": dict(por_familia),
            "cubiertas": sum(n for f, n in por_familia.items() if f in soportadas),
            "sin_cobertura": sin_cobertura, "soportadas": sorted(soportadas),
            "nivel": {f: (registro[f] or {}).get("nivel") for f in soportadas}}


def _main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("uso: python3 -m prototipo.validar_reglas <muestra-alerts.json>")
        return 2
    try:
        f = open(argv[0], encoding="utf-8")
    except OSError as e:
        print(f"no se pudo abrir {argv[0]}: {e}")
        return 1
    crudas = []
    with f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                crudas.append(json.loads(linea))
            except ValueError:
                crudas.append(linea)                   # no-JSON: entra y se cuenta como malformada
    r = cobertura(crudas)
    print(f"{r['total']} alertas · {r['cubiertas']} con familia y playbook · "
          f"{len(r['sin_cobertura'])} sin cobertura · {r['propias']} propias · {r['malformadas']} malformadas")
    _ETIQUETA_NIVEL = {"actuar": "contiene", "triar_y_enrutar": "tria y encamina (no contiene)"}
    for fam in sorted(r["por_familia"]):
        if fam in r["soportadas"]:
            marca = f"   ({_ETIQUETA_NIVEL.get(r['nivel'].get(fam), r['nivel'].get(fam))})"
        else:
            marca = "   <- SIN soporte (el motor no actúa)"
        print(f"  {fam}: {r['por_familia'][fam]}{marca}")
    if r["sin_cobertura"]:
        print("Reglas sin mapear (afinar el adaptador/ruleset en el alta del cliente):")
        vistos = set()
        for s in r["sin_cobertura"]:
            clave = (s["regla_id"], tuple(s["grupos"]))
            if clave in vistos:
                continue
            vistos.add(clave)
            print(f"  regla {s['regla_id']} · grupos {s['grupos']}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
