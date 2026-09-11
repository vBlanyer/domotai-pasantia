"""Reversión de una acción ya ejecutada, a partir de su registro de traza (RF-18).

El catálogo declara para cada acción de contención su `reversion_cmd`; hasta ahora esa
promesa solo se ejercía a mano. Aquí la reversión sale del propio registro de la decisión
---la orden que se ejecutó, con sus parámetros--- y del catálogo, se ejecuta por el mismo
conector que ejecutó la acción, se verifica con la misma verificación (que ahora debe
fallar: el estado que la acción dejó ya no está), y se anota como un registro más en la
misma cadena de la traza, con el identificador de la decisión revertida y el motivo.

    python3 -m prototipo.revertir trazas-stream.jsonl s7 --motivo "falso positivo confirmado por el cliente"
"""
import datetime
import json
import os
import sys

from prototipo import catalogo as catm, conector, traza

_REVERSIBLES = ("definida",)


def _render(plantilla, params):
    try:
        return plantilla.format(**params)
    except (KeyError, IndexError):
        return None


def revertir(registro, catalogo, ejecutor, timestamp, motivo=""):
    """Devuelve el registro de reversión (nunca lanza): {tipo, id_decision_revertida, accion_id,
    nodo, comando_ejecutado, codigo_salida, salida, exito, motivo, timestamp}. `exito` exige que la
    reversión devuelva 0 y que la verificación de la acción original deje de cumplirse."""
    base = {"tipo": "reversion", "id_decision_revertida": registro.get("id_decision"),
            "motivo": motivo, "timestamp": timestamp}
    orden, ejec = registro.get("orden"), registro.get("ejecucion") or {}
    if not orden:
        return {**base, "accion_id": None, "nodo": None, "comando_ejecutado": None, "codigo_salida": -1,
                "salida": "la decision no ejecuto ninguna orden", "exito": False}
    acc = catalogo.get(orden.get("accion_id"), {})
    base.update({"accion_id": orden.get("accion_id"), "nodo": orden.get("nodo_objetivo")})
    if acc.get("reversion") not in _REVERSIBLES or not acc.get("reversion_cmd"):
        return {**base, "comando_ejecutado": None, "codigo_salida": -1, "exito": False,
                "salida": f"la accion no tiene reversion definida (reversion={acc.get('reversion')})"}
    params = orden.get("params") or {}
    if not conector._params_seguros(params):
        return {**base, "comando_ejecutado": None, "codigo_salida": -1, "exito": False,
                "salida": "params rechazados: caracteres no permitidos"}
    cmd = _render(acc["reversion_cmd"], params)
    verif = _render(acc.get("verificacion", ""), params)
    if cmd is None:
        return {**base, "comando_ejecutado": None, "codigo_salida": -1, "exito": False,
                "salida": "la plantilla de reversion pide un parametro que la orden no tiene"}
    if not ejec.get("exito") and not ejec.get("idempotente"):
        # Se avisa pero se intenta igual: si la accion fallo a medias, revertir es lo prudente.
        base["aviso"] = "la ejecucion original no consta como exitosa"
    rc, salida = ejecutor(orden["nodo_ip"], cmd)
    # La verificacion de la ACCION debe dejar de cumplirse (rc != 0) para dar la reversion por buena.
    rc_v, salida_v = (ejecutor(orden["nodo_ip"], verif) if verif else (1, ""))
    return {**base, "comando_ejecutado": cmd, "codigo_salida": rc, "salida": salida + salida_v,
            "exito": rc == 0 and rc_v != 0}


def _main(argv):
    if len(argv) < 2:
        print("uso: python3 -m prototipo.revertir <traza.jsonl> <id_decision> [--motivo \"...\"]"); return 2
    ruta, id_decision = argv[0], argv[1]
    motivo = argv[argv.index("--motivo") + 1] if "--motivo" in argv else ""
    regs = traza.leer_registros(ruta)
    reg = next((r for r in regs if r.get("id_decision") == id_decision), None)
    if reg is None:
        print(f"no hay ninguna decision {id_decision!r} en {ruta}"); return 1
    ya = [r for r in regs if r.get("tipo") == "reversion" and r.get("id_decision_revertida") == id_decision and r.get("exito")]
    if ya:
        print(f"la decision {id_decision} ya fue revertida el {ya[-1].get('timestamp')}"); return 0
    cat = catm.cargar_catalogo(os.path.join(os.path.dirname(__file__), "catalogo.yml"))
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+0000"
    r = revertir(reg, cat, conector.ejecutor_por_defecto(), ts, motivo)
    # La reversion se anota en la MISMA cadena: es una decision mas, y la traza debe contarla.
    with open(ruta, "a", encoding="utf-8") as f:
        traza.Cadena(f, traza.ultimo_hash(ruta)).escribir(r)
    estado = "revertida" if r["exito"] else "NO revertida"
    print(f"{id_decision}: {r['accion_id']} en {r['nodo']} -> {estado} · comando: {r['comando_ejecutado']}")
    if not r["exito"]:
        print("  detalle:", (r.get("salida") or "").strip()[:300])
    return 0 if r["exito"] else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
