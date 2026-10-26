"""Benchmark de carga del motor de triaje (#12): mide cuántas decisiones por segundo procesa un
daemon, para documentar la escala de un proceso.

Usa un ejecutor SIMULADO (sin SSH), así mide el MOTOR (ingesta → análisis → decisión → filtro →
traza encadenada), no la contención: el coste real por contención es el SSH (segundos cada una) y es
un límite aparte. Tampoco mide el ritmo del SIEM, que es el otro límite externo.

    python3 -m prototipo.herramientas.banco_carga [N]
"""
import io
import json
import os
import sys
import time

from prototipo.motor import perfil as perfilm
from prototipo.accion import catalogo as catm
from prototipo.servicio import stream, lazo


def _linea(i):
    """Una alerta cruda de Wazuh con origen variado (para no auto-suprimirse) y tiempo creciente."""
    srcip = f"198.51.{(i // 254) % 254}.{i % 254 + 1}"
    return json.dumps({
        "id": f"a{i}",
        "rule": {"id": "5760", "level": 10, "groups": ["sshd", "authentication_failed"],
                 "mitre": {"id": ["T1110.001"]}},
        "predecoder": {"hostname": "objetivo-vuln", "program_name": "sshd"},
        "data": {"srcip": srcip},
        "timestamp": f"2026-08-31T{(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}Z"})


def medir(n=1000, perfil_ruta=None, hallazgos_ruta=None):
    """Procesa `n` alertas sintéticas por el motor y devuelve el throughput:
    {alertas, incidentes, segundos, decisiones_por_seg, ms_por_alerta}."""
    perfil = perfilm.cargar(perfil_ruta or stream._PERFIL_DEF)
    with open(hallazgos_ruta or stream._HALLAZGOS_DEF, encoding="utf-8") as f:
        hallazgos = json.load(f)
    cat = catm.cargar_catalogo(os.path.join(stream._RAIZ, "prototipo", "catalogo.yml"))
    lineas = [_linea(i) for i in range(n)]
    resumen = stream._resumen_nuevo()
    t0 = time.perf_counter()
    stream.ejecutar(lineas, hallazgos=hallazgos, perfil=perfil, perfil_nombre="carga", catalogo=cat,
                    ejecutor=lazo._EjecutorAuto(), justificar_fn=None, ventana_agrupacion=0,
                    salida_traza=io.StringIO(), escribir=lambda *a, **k: None, resumen=resumen)
    seg = time.perf_counter() - t0
    return {"alertas": n, "incidentes": resumen["incidentes"], "segundos": round(seg, 3),
            "decisiones_por_seg": round(n / seg) if seg else 0,
            "ms_por_alerta": round(1000 * seg / n, 3) if n else 0}


def _main(argv):
    n = int(argv[0]) if argv and argv[0].isdigit() else 1000
    r = medir(n)
    print(f"{r['alertas']} alertas · {r['incidentes']} incidentes · {r['segundos']} s · "
          f"{r['decisiones_por_seg']} decisiones/seg · {r['ms_por_alerta']} ms/alerta")
    print("  (ejecutor simulado: mide el MOTOR; el SSH por contención —segundos cada una— y el ritmo "
          "del SIEM son los límites reales, aparte)")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
