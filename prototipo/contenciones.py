"""Vista derivada de la traza: qué contenciones siguen activas ahora mismo.

La traza (RF-09) ya es la fuente de verdad de lo que el motor decidió y ejecutó. En vez de mantener
un registro de bloqueos en memoria —que se perdería al reiniciar y habría que sincronizar—, esta vista
se calcula de la propia traza: una contención está activa si se ejecutó con éxito, se verificó, deja
estado reversible (`reversion: definida`, igual que `revertir._REVERSIBLES`) y no se ha revertido
después. Así el daemon «recuerda» qué tiene bloqueado aunque se reinicie, y queda la base para el
des-bloqueo en masa (kill switch)."""

_REVERSIBLES = ("definida",)   # alineado con prototipo.revertir._REVERSIBLES


def revertidas(registros):
    """(índices revertidos, ids revertidos-heredados). Una reversión con éxito retira su decisión;
    se prefiere `indice_revertido` (único en la traza) y se cae al id solo para reversiones heredadas
    —mismo criterio que revertir.py—, porque en una traza multi-sesión (--salida estable) los id se
    repiten (s1, s2… reinician en cada arranque) y excluir por id pelado descartaría la decisión de
    otra sesión."""
    idx = {r["indice_revertido"] for r in registros
           if r.get("tipo") == "reversion" and r.get("exito") and "indice_revertido" in r}
    ids = {r.get("id_decision_revertida") for r in registros
           if r.get("tipo") == "reversion" and r.get("exito") and "indice_revertido" not in r}
    return idx, ids


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
    rev_idx, rev_id = revertidas(registros)
    vivas = {}
    for i, reg in enumerate(registros):
        if reg.get("tipo") not in (None, "decision"):
            continue
        if i in rev_idx or reg.get("id_decision") in rev_id:
            continue
        orden, via_escalada = _orden_efectiva(reg)
        if not orden:
            continue
        accion_id = orden.get("accion_id")
        acc = catalogo.get(accion_id, {})
        if acc.get("reversion") not in _REVERSIBLES or not acc.get("reversion_cmd"):
            continue                                  # transitoria / sin reversión: no deja estado que listar
        # El objetivo depende de la acción: IP (BLOQUEAR_IP), cuenta (FORZAR_CAMBIO_PASS) o servicio/
        # puerto (CERRAR_SERVICIO…). Sin esto, dos bloqueos sobre cuentas/servicios distintos del mismo
        # nodo (ip None) se colapsarían en una sola entrada.
        params = orden.get("params") or {}
        objetivo = params.get("ip") or params.get("usuario") or params.get("servicio") or params.get("puerto")
        nodo = orden.get("nodo_objetivo")
        vivas[(objetivo, nodo, accion_id)] = {
            "id_decision": reg.get("id_decision"), "objetivo": objetivo,
            "ip": params.get("ip"), "usuario": params.get("usuario"), "servicio": params.get("servicio"),
            "activo": reg.get("activo"), "nodo": nodo, "accion_id": accion_id,
            "ts": reg.get("decidido_en") or reg.get("timestamp"), "via_escalada": via_escalada,
        }
    return list(vivas.values())
