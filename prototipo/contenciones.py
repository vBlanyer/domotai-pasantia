"""Vista derivada de la traza: qué contenciones siguen activas ahora mismo.

La traza (RF-09) ya es la fuente de verdad de lo que el motor decidió y ejecutó. En vez de mantener
un registro de bloqueos en memoria —que se perdería al reiniciar y habría que sincronizar—, esta vista
se calcula de la propia traza: una contención está activa si se ejecutó con éxito, se verificó, deja
estado reversible (`reversion: definida`, igual que `revertir._REVERSIBLES`) y no se ha revertido
después. Así el daemon «recuerda» qué tiene bloqueado aunque se reinicie, y queda la base para el
des-bloqueo en masa (kill switch)."""

_REVERSIBLES = ("definida",)   # alineado con prototipo.revertir._REVERSIBLES


def _orden_efectiva(reg):
    """La orden y el nodo donde el bloqueo quedó aplicado. Si el paso en el activo falló y la escalada
    (o el agente) contuvo aguas arriba, lo vigente es su `orden_efectiva` (mismo criterio que revertir)."""
    orden = reg.get("orden")
    ejec = reg.get("ejecucion") or {}
    plan = reg.get("escalada") or reg.get("mitigacion_agente") or {}
    if not ejec.get("exito") and plan.get("orden_efectiva"):
        return plan["orden_efectiva"], True          # efectiva en el dispositivo de contención
    verif = reg.get("verificacion") or {}
    if ejec.get("exito") and verif.get("verificado"):
        return orden, False
    return None, False                                # ni aplicada en el activo ni contenida arriba


def activas(registros, catalogo):
    """Lista de contenciones activas reconstruidas de la traza, deduplicadas por (ip, nodo, accion_id)
    —un re-bloqueo conserva la entrada más reciente—; una reversión con éxito posterior la retira.

    Cada entrada: {id_decision, ip, activo, nodo, accion_id, ts, via_escalada}."""
    revertidas = {r.get("id_decision_revertida") for r in registros
                  if r.get("tipo") == "reversion" and r.get("exito")}
    vivas = {}
    for reg in registros:
        if reg.get("tipo") not in (None, "decision"):
            continue
        if reg.get("id_decision") in revertidas:
            continue
        orden, via_escalada = _orden_efectiva(reg)
        if not orden:
            continue
        accion_id = orden.get("accion_id")
        acc = catalogo.get(accion_id, {})
        if acc.get("reversion") not in _REVERSIBLES or not acc.get("reversion_cmd"):
            continue                                  # transitoria / sin reversión: no deja estado que listar
        ip = (orden.get("params") or {}).get("ip")
        nodo = orden.get("nodo_objetivo")
        vivas[(ip, nodo, accion_id)] = {
            "id_decision": reg.get("id_decision"),
            "ip": ip, "activo": reg.get("activo"), "nodo": nodo, "accion_id": accion_id,
            "ts": reg.get("decidido_en") or reg.get("timestamp"), "via_escalada": via_escalada,
        }
    return list(vivas.values())
