"""Agrupación y deduplicación de alertas por incidente (RF-11).

Colapsa las ráfagas de alertas relacionadas —misma `(origen_ip, activo, servicio, familia)` dentro de una
ventana temporal— en un solo **incidente**, por encima de la correlación que Wazuh ya hace. El motor triaja
el **representante** del incidente (la alerta más informativa: mayor `nivel_wazuh`), no cada alerta, lo que
reduce los ítems que el analista debe revisar. Puro y tolerante (RNF-07): una alerta sin timestamp no rompe.
"""
import json, sys
from collections import Counter, defaultdict
from datetime import datetime

def clave_incidente(alerta):
    return (alerta.get("origen_ip"), alerta.get("activo"), alerta.get("servicio"), alerta.get("familia"))

def _ts(alerta):
    v = alerta.get("timestamp")
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):
        return None

def representante(alertas):
    """La alerta más informativa del incidente: mayor nivel_wazuh; empate → la más reciente."""
    def clave(a):
        t = _ts(a)
        return (a.get("nivel_wazuh") or 0, t.timestamp() if t else float("-inf"))
    return max(alertas, key=clave)

def _incidente(clave, alertas):
    ts = [t for t in (_ts(a) for a in alertas) if t is not None]
    return {
        "clave": {"origen_ip": clave[0], "activo": clave[1], "servicio": clave[2], "familia": clave[3]},
        "conteo": len(alertas),
        "representante": representante(alertas),
        "primera_ts": min(ts).isoformat() if ts else None,
        "ultima_ts": max(ts).isoformat() if ts else None,
        "reglas": dict(Counter(a.get("regla_id") for a in alertas)),
        "ids": [a.get("id_alerta") for a in alertas],
    }

def agrupar(alertas, ventana_seg=300):
    """Agrupa las alertas en incidentes por clave; dentro de cada clave, parte en ventanas temporales."""
    por_clave = defaultdict(list)
    for a in alertas:
        por_clave[clave_incidente(a)].append(a)
    incidentes = []
    for clave, grupo in por_clave.items():
        # ordenar por tiempo; las alertas sin timestamp van al final, de forma estable
        orden = sorted(range(len(grupo)), key=lambda i: (_ts(grupo[i]) is None, _ts(grupo[i]) or datetime.min))
        grupo = [grupo[i] for i in orden]
        actual = []
        for a in grupo:
            if actual:
                t_prev, t_cur = _ts(actual[-1]), _ts(a)
                if t_prev and t_cur and (t_cur - t_prev).total_seconds() > ventana_seg:
                    incidentes.append(_incidente(clave, actual))
                    actual = []
            actual.append(a)
        if actual:
            incidentes.append(_incidente(clave, actual))
    return incidentes

def main(argv):
    ruta, salida = argv[1:3]
    ventana = int(argv[3]) if len(argv) > 3 else 300
    alertas = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                alertas.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    incidentes = agrupar(alertas, ventana)
    with open(salida, "w", encoding="utf-8") as f:
        for inc in incidentes:
            f.write(json.dumps(inc, ensure_ascii=False) + "\n")
    print(f"{len(alertas)} alertas -> {len(incidentes)} incidentes  (ventana {ventana}s) -> {salida}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
