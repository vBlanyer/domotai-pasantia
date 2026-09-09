"""Runner en streaming (daemon / listener MDR): escucha alertas de Wazuh sin cerrarse y las pasa
por el pipeline existente (ingesta -> agrupacion -> triaje -> explicabilidad -> validacion ->
mitigacion -> traza) en tiempo real. Es una capa de orquestacion: no reimplementa logica del motor.

La fuente de lineas es inyectable (fichero seguido estilo `tail -f`, o stdin), lo que hace el bucle
testeable con una lista y resuelve que en el laboratorio el `alerts.json` de Wazuh vive dentro del
contenedor: se canaliza `docker exec ... tail -F ... | python3 -m prototipo.stream -`.
"""
import io, json, os, select, sys, time
from prototipo import ingesta, adaptador_wazuh, agrupacion, lazo

_ADAPTADOR = adaptador_wazuh.adaptador("tiempo-real")

# ------------------------------------------------------------------ parseo/UX --

def _parsear(linea):
    """Linea cruda JSON -> alerta normalizada, o None si vacia/corrupta (RNF-07: no inventar)."""
    linea = (linea or "").strip()
    if not linea:
        return None
    try:
        cruda = json.loads(linea)
    except json.JSONDecodeError:
        return None
    return ingesta.normalizar(cruda, _ADAPTADOR)

def _resumen_incidente(inc):
    c = inc["clave"]
    reglas = ", ".join(f"{k}x{v}" for k, v in inc["reglas"].items())
    return (f"⚠ Incidente: {inc['conteo']} alerta(s) · {c['origen_ip']} -> {c['activo']} "
            f"({c['servicio']}) · reglas [{reglas}]")

def _linea_decision(d):
    return (f"  Clase: {d['clase']} · Prioridad: {d['prioridad']} · Confianza: {d['confianza']} · "
            f"accion {d['accion_propuesta']} -> {d['accion_final']} (filtro {d['resultado_filtro']}) · "
            f"justificador {d.get('version_justificador')}")

# --------------------------------------------------------------------- bucle --

def _procesar_incidente(inc, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn,
                        id_decision, salida_traza, escribir, leer):
    rep = inc["representante"]
    escribir(_resumen_incidente(inc))
    kw = {} if justificar_fn is None else {"justificar_fn": justificar_fn}
    d = lazo.procesar_lazo(rep, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                           id_decision, rep.get("timestamp", ""), leer=leer, **kw)
    escribir(_linea_decision(d))
    if salida_traza is not None:
        salida_traza.write(json.dumps(d, ensure_ascii=False) + "\n")
        salida_traza.flush()
    return d

def _contar(resumen, d):
    resumen["incidentes"] += 1
    v = d.get("veredicto_humano")
    if v == "aprobar": resumen["aprobadas"] += 1
    elif v == "reclasificar": resumen["reclasificadas"] += 1
    elif v == "rechazar": resumen["rechazadas"] += 1
    if (d.get("ejecucion") or {}).get("exito"):
        resumen["ejecutadas"] += 1

def ejecutar(fuente_lineas, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
             justificar_fn=None, ventana_agrupacion=0, salida_traza=None,
             escribir=print, leer=input, reloj=time.monotonic):
    """Consume `fuente_lineas` (iterable de str crudas o None en reposo) y triaja cada incidente.

    ventana_agrupacion == 0  -> cada alerta se procesa al instante (un incidente por alerta).
    ventana_agrupacion  > 0  -> se acumulan las alertas y, cuando pasan N segundos de pared desde la
                                primera (o al agotarse la fuente), se agrupan (RF-11) y se emiten los
                                incidentes; los ticks None permiten vencer la ventana sin lineas nuevas.
    """
    resumen = {"alertas": 0, "incidentes": 0, "aprobadas": 0, "rechazadas": 0,
               "reclasificadas": 0, "ejecutadas": 0}
    seq = [0]
    def _procesa_lote(lote):
        for inc in agrupacion.agrupar(lote, ventana_seg=max(ventana_agrupacion, 1)):
            seq[0] += 1
            _contar(resumen, _procesar_incidente(
                inc, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn,
                f"s{seq[0]}", salida_traza, escribir, leer))

    buffer, t0 = [], None
    def _vencio():
        return t0 is not None and (reloj() - t0) >= ventana_agrupacion
    def _descargar():
        nonlocal buffer, t0
        if buffer:
            _procesa_lote(buffer)
            buffer, t0 = [], None

    for linea in fuente_lineas:
        if ventana_agrupacion <= 0:                # modo inmediato
            if linea is None:
                continue
            alerta = _parsear(linea)
            if alerta is None:
                continue
            resumen["alertas"] += 1
            _procesa_lote([alerta])
            continue
        # modo con ventana
        if linea is not None:
            alerta = _parsear(linea)
            if alerta is not None:
                resumen["alertas"] += 1
                if t0 is None:
                    t0 = reloj()
                buffer.append(alerta)
        if _vencio():
            _descargar()
    _descargar()                                   # fuente agotada: descarga lo pendiente
    return resumen

# ------------------------------------------------------------------ fuentes --

def leer_lineas_stdin(stream=sys.stdin, intervalo=0.5):
    """Rinde líneas de stdin y, en reposo, `None` (tick) para que la ventana de agrupación pueda
    cerrarse aunque no lleguen alertas nuevas. Usa select sobre el descriptor; si no hay uno real
    (tests con StringIO), cae a iteración simple sin ticks."""
    try:
        fd = stream.fileno()
    except (OSError, ValueError, io.UnsupportedOperation):
        for linea in stream:
            yield linea
        return
    while True:
        listos, _, _ = select.select([fd], [], [], intervalo)
        if not listos:
            yield None                      # reposo -> permite vencer la ventana
            continue
        linea = stream.readline()
        if not linea:                       # EOF
            return
        yield linea

def leer_lineas_fichero(ruta, intervalo=0.5, desde_inicio=False, detener=None, dormir=time.sleep):
    """Sigue un fichero como `tail -f`. Tolera que no exista aun (espera activa). Reabre en
    rotacion/truncado. Rinde None en reposo para que la ventana pueda vencer sin lineas nuevas."""
    f, pos = None, 0
    try:
        while detener is None or not detener():
            if f is None:
                if not os.path.exists(ruta):
                    yield None
                    dormir(intervalo)
                    continue
                f = open(ruta, encoding="utf-8", errors="replace")
                if not desde_inicio:
                    f.seek(0, os.SEEK_END)          # tail -f: solo lo nuevo
                pos = f.tell()
            try:
                if os.path.getsize(ruta) < pos:    # truncado/rotacion -> reabrir desde 0
                    f.close(); f, pos = None, 0
                    continue
            except OSError:
                f.close(); f = None
                continue
            linea = f.readline()
            if linea:
                pos = f.tell()
                yield linea
            else:
                yield None
                dormir(intervalo)
    finally:
        if f is not None:
            f.close()

# ---------------------------------------------------------------------- CLI --

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PERFIL_DEF = os.path.join(_RAIZ, "prototipo", "perfiles", "empresarial.yml")
_HALLAZGOS_DEF = os.path.join(_RAIZ, "lab", "campañas", "2026-08-31-evaluacion", "hallazgos.json")

def parsear_args(argv):
    pos, con_llm, ventana, salida, sin_lab = [], False, 5, "trazas-stream.jsonl", False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--con-llm": con_llm = True
        elif a == "--sin-llm": con_llm = False
        elif a == "--sin-lab": sin_lab = True
        elif a == "--ventana-agrupacion": i += 1; ventana = int(argv[i])
        elif a == "--salida": i += 1; salida = argv[i]
        else: pos.append(a)
        i += 1
    return {"ruta": pos[0] if pos else "-",
            "perfil": pos[1] if len(pos) > 1 else _PERFIL_DEF,
            "hallazgos": pos[2] if len(pos) > 2 else _HALLAZGOS_DEF,
            "con_llm": con_llm, "ventana": ventana, "salida": salida, "sin_lab": sin_lab}

def construir_justificar_fn(con_llm, escribir=print):
    if not con_llm:
        return None
    try:
        from prototipo import justificador_llm, rag
        indice = rag.cargar_indice()
        # RAG AGÉNTICO (Opción C): la consulta la decide el 1B y se excluyen las fichas regla-* del
        # conocimiento (palanca 3). La traza registra consulta_rag/recuperacion_agentica/pasajes_usados.
        recuperar_fn = rag.recuperar_fn_agentico(indice, rag.embedder_llama,
                                                 generador=justificador_llm.generador_llama, k=3)
        return justificador_llm.justificar_fn_rag(justificador_llm.generador_llama, recuperar_fn)
    except Exception as e:                          # sin indice/modelo -> degradar a plantilla (RNF-09)
        escribir(f"[aviso] justificador LLM/RAG no disponible ({e}); se usara la plantilla.")
        return None

def banner(cfg):
    fuente = "stdin (canalizado)" if cfg["ruta"] == "-" else cfg["ruta"]
    just = "LLM+RAG" if cfg["con_llm"] else "plantilla"
    lab = "simulado (--sin-lab)" if cfg["sin_lab"] else "conector SSH (lab)"
    return ("\n" + "=" * 72 +
            "\n  Monitor MDR en tiempo real — ACTIVO"
            f"\n  Perfil: {os.path.basename(cfg['perfil'])} · Justificador: {just} · Ejecutor: {lab}"
            f"\n  Escuchando: {fuente} · ventana de agrupacion: {cfg['ventana']}s"
            "\n  (Ctrl+C para detener)\n" + "=" * 72)

def _resumen_final(r):
    return ("\n── Resumen de la sesion ──\n"
            f"  Alertas vistas: {r['alertas']} · Incidentes: {r['incidentes']}\n"
            f"  Aprobadas: {r['aprobadas']} · Rechazadas: {r['rechazadas']} · "
            f"Reclasificadas: {r['reclasificadas']} · Ejecutadas: {r['ejecutadas']}")

def _leer_interactivo():
    """Lector de la respuesta del ANALISTA desde el terminal de control (/dev/tty), no de stdin.
    Imprescindible cuando las alertas llegan por stdin (pipe `… tail -F | stream -`): si se leyera de
    stdin, el input() consumiría líneas de alerta como si fueran la respuesta. Cae a input() si no hay
    tty (tests/CI/background)."""
    try:
        tty = open("/dev/tty")
    except OSError:
        return input
    def _leer(prompt=""):
        if prompt:
            print(prompt, end="", flush=True)
        linea = tty.readline()
        if not linea:
            raise EOFError
        return linea.rstrip("\n")
    return _leer

def main(argv):
    from prototipo import perfil as perfilm, catalogo as catm, conector
    cfg = parsear_args(argv)
    perfil = perfilm.cargar(cfg["perfil"])
    perfil_nombre = os.path.basename(cfg["perfil"]).replace(".yml", "")
    with open(cfg["hallazgos"], encoding="utf-8") as f:
        hallazgos = json.load(f)
    catalogo = catm.cargar_catalogo(os.path.join(_RAIZ, "prototipo", "catalogo.yml"))
    justificar_fn = construir_justificar_fn(cfg["con_llm"])
    ejecutor = lazo._EjecutorAuto() if cfg["sin_lab"] else conector.ejecutor_ssh_lab
    fuente = leer_lineas_stdin() if cfg["ruta"] == "-" else leer_lineas_fichero(cfg["ruta"])
    print(banner(cfg))
    resumen = {"alertas": 0, "incidentes": 0, "aprobadas": 0, "rechazadas": 0,
               "reclasificadas": 0, "ejecutadas": 0}
    try:
        with open(cfg["salida"], "a", encoding="utf-8") as traza_f:
            resumen = ejecutar(fuente, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                               justificar_fn=justificar_fn, ventana_agrupacion=cfg["ventana"],
                               salida_traza=traza_f, leer=_leer_interactivo())
    except KeyboardInterrupt:                        # Ctrl+C / SIGINT: cierre limpio con resumen
        pass
    print(_resumen_final(resumen))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
