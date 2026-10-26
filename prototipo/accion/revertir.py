"""Reversión de una acción ya ejecutada, a partir de su registro de traza (RF-18).

El catálogo declara para cada acción de contención su `reversion_cmd`; hasta ahora esa
promesa solo se ejercía a mano. Aquí la reversión sale del propio registro de la decisión
---la orden que se ejecutó, con sus parámetros--- y del catálogo, se ejecuta por el mismo
conector que ejecutó la acción, se verifica con la misma verificación (que ahora debe
fallar: el estado que la acción dejó ya no está), y se anota como un registro más en la
misma cadena de la traza, con el identificador de la decisión revertida y el motivo.

    python3 -m prototipo.accion.revertir run/trazas-stream.jsonl s7 --motivo "falso positivo confirmado por el cliente"
"""
import datetime
import json
import os
import sys

from prototipo.accion import catalogo as catm, conector
from prototipo.servicio import traza

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
    # Si el paso en el activo fallo y contuvo la escalada (o el agente), lo que hay que revertir
    # es la orden EFECTIVA: la del dispositivo donde el bloqueo se verifico.
    plan = registro.get("escalada") or registro.get("mitigacion_agente") or {}
    if not ejec.get("exito") and plan.get("orden_efectiva"):
        orden, ejec = plan["orden_efectiva"], {"exito": True}
        base["escalada"] = True
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
    if not conector.ip_valida(orden.get("nodo_ip")):
        # nodo_ip sale de la traza (manipulable) y se interpola en la linea SSH: exigir una IP real.
        return {**base, "comando_ejecutado": None, "codigo_salida": -1, "exito": False,
                "salida": "nodo_ip rechazado: no es una IP valida"}
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


def revertir_todas(ruta, catalogo, ejecutor, motivo="", operador=None, _ahora=None):
    """Des-bloqueo en masa (kill switch #8): revierte TODAS las contenciones activas de la traza y
    anota cada reversión en la MISMA cadena (fichero bloqueado y releído, como la CLI), con
    `indice_revertido` y `operador`. Las activas salen de contenciones.activas (mismo criterio que
    la vista /api/contenciones). Síncrono: cada reversión ejecuta su comando real (acotado por el
    timeout del conector). Devuelve {revertidas, fallidas, detalle}."""
    from prototipo.accion import contenciones
    regs = traza.leer_registros(ruta)
    activas = contenciones.activas(regs, catalogo)
    if not activas:
        return {"revertidas": 0, "fallidas": 0, "detalle": []}
    ts = _ahora or (datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+0000")
    revertidas = fallidas = 0
    detalle = []
    with traza.abrir_append(ruta) as f:                  # 0600; flock + relectura para coexistir con el daemon
        previos = traza.leer_registros(ruta)
        cadena = traza.Cadena(f, traza.ultimo_hash(ruta), n=len(previos),
                              nombre=os.path.basename(ruta), linaje=traza.linaje_de(previos), ruta=ruta)
        for a in activas:
            reg = regs[a["indice"]]
            r = {**revertir(reg, catalogo, ejecutor, ts, motivo), "indice_revertido": a["indice"]}
            if operador:
                r["operador"] = operador
            cadena.escribir(r)
            if r.get("exito"):
                revertidas += 1
            else:
                fallidas += 1
            detalle.append({"id_decision": reg.get("id_decision"), "accion_id": r.get("accion_id"),
                            "nodo": r.get("nodo"), "objetivo": a.get("objetivo"), "exito": r.get("exito")})
    return {"revertidas": revertidas, "fallidas": fallidas, "detalle": detalle}


def _main(argv):
    if len(argv) < 2:
        print("uso: python3 -m prototipo.accion.revertir <traza.jsonl> <id_decision> [--indice N] [--motivo \"...\"]")
        return 2
    ruta, id_decision = argv[0], argv[1]
    motivo = argv[argv.index("--motivo") + 1] if "--motivo" in argv else ""
    regs = traza.leer_registros(ruta)
    # Cada sesion del daemon numera desde s1 y retoma el mismo fichero: el id se repite. Por defecto
    # la ULTIMA decision con ese id (la de la sesion en curso); --indice N elige una concreta (el
    # indice que muestra el visor).
    candidatas = [i for i, r in enumerate(regs) if r.get("id_decision") == id_decision and r.get("tipo") != "reversion"]
    if "--indice" in argv:
        indice = int(argv[argv.index("--indice") + 1])
        if indice not in candidatas:
            print(f"el registro {indice} de {ruta} no es la decision {id_decision!r}"); return 1
    elif candidatas:
        indice = candidatas[-1]
    else:
        print(f"no hay ninguna decision {id_decision!r} en {ruta}"); return 1
    reg = regs[indice]
    ya = [r for r in regs if r.get("tipo") == "reversion" and r.get("exito")
          and (r.get("indice_revertido") == indice
               or ("indice_revertido" not in r and r.get("id_decision_revertida") == id_decision))]
    if ya:
        print(f"la decision {id_decision} (registro {indice}) ya fue revertida el {ya[-1].get('timestamp')}"); return 0
    cat = catm.cargar_catalogo(os.path.join(os.path.dirname(os.path.dirname(__file__)), "catalogo.yml"))
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+0000"
    r = {**revertir(reg, cat, conector.ejecutor_por_defecto(), ts, motivo), "indice_revertido": indice}
    # La reversion se anota en la MISMA cadena, con el fichero bloqueado y releido (Cadena con
    # `ruta`): el daemon puede estar escribiendo en el. Nombre, recuento y linaje, para que el ancla
    # identifique el fichero como las del daemon.
    with traza.abrir_append(ruta) as f:                  # permisos 0600 (integridad de la traza)
        previos = traza.leer_registros(ruta)
        traza.Cadena(f, traza.ultimo_hash(ruta), n=len(previos), nombre=os.path.basename(ruta),
                     linaje=traza.linaje_de(previos), ruta=ruta).escribir(r)
    estado = "revertida" if r["exito"] else "NO revertida"
    print(f"{id_decision}: {r['accion_id']} en {r['nodo']} -> {estado} · comando: {r['comando_ejecutado']}")
    if not r["exito"]:
        print("  detalle:", (r.get("salida") or "").strip()[:300])
    return 0 if r["exito"] else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
