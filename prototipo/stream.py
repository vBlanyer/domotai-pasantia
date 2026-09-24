"""Runner en streaming (daemon / listener MDR): escucha alertas de Wazuh sin cerrarse y las pasa
por el pipeline existente (ingesta -> agrupacion -> triaje -> explicabilidad -> validacion ->
mitigacion -> traza) en tiempo real. Es una capa de orquestacion: no reimplementa logica del motor.

La fuente de lineas es inyectable (fichero seguido estilo `tail -f`, o stdin), lo que hace el bucle
testeable con una lista y resuelve que en el laboratorio el `alerts.json` de Wazuh vive dentro del
contenedor: se canaliza `docker exec ... tail -F ... | python3 -m prototipo.stream -`.
"""
import io, json, os, select, sys, threading, time
from prototipo import ingesta, adaptador_wazuh, agrupacion, lazo, rafaga, traza, validacion

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
    base = (f"  Clase: {d['clase']} · Prioridad: {d['prioridad']} · Confianza: {d['confianza']} · "
            f"accion {d['accion_propuesta']} -> {d['accion_final']} (filtro: {validacion.filtro_legible(d)}) · "
            f"justificador {d.get('version_justificador')}")
    det = d.get("impacto_determinado") or {}
    motivo = det.get("motivo")
    if motivo:
        if d.get("accion_final") is None:   # veto duro: la consecuencia no llegó a ejecutarse
            motivo = f"(vetada) {motivo}"
        base += f"\n  Consecuencia: {motivo}"
    mit = d.get("mitigacion_agente")
    if mit:
        base += (f"\n  Agente: {mit.get('resultado')} · ejecutor {mit.get('dispositivo_ejecutor')} · "
                 f"escalado {mit.get('escalado')}")
    esc = d.get("escalada")
    if esc:
        base += (f"\n  Escalada (el activo no respondio): {esc.get('resultado')} · "
                 f"contenido en {esc.get('dispositivo_ejecutor')}")
    if d.get("clase") == "amenaza_enrutada":
        base += f"\n  Enrutado a: {d.get('ruta')} (triaje sin contencion automatica)"
    return base

# --------------------------------------------------------------------- bucle --

def _clave_supresion(inc):
    c = inc["clave"]
    return (c.get("origen_ip"), c.get("familia"))


def _ordenar_por_severidad(incidentes):
    """Incidentes por severidad del SIEM (nivel_wazuh del representante) descendente; estable.

    E-minimo bajo carga: cuando llegan muchos ataques distintos a la vez, se procesan los mas graves
    primero. La prioridad fina se calcula al decidir, aqui usamos el nivel de la regla como proxy."""
    return sorted(incidentes, key=lambda inc: inc["representante"].get("nivel_wazuh") or 0, reverse=True)


class MemoriaDecisiones:
    """Recuerda las claves (origen_ip, familia) ya decididas en la sesion, para suprimir sus
    repeticiones (RF-11): una vez tomada una decision sobre un ataque, las alertas siguientes del
    mismo origen y tipo no se re-justifican ni se vuelven a preguntar. La traza recibe un
    registro-resumen 'actividad_suprimida' que referencia la decision original, para que muestre que
    el ataque siguio sin un registro por alerta. Es memoria de sesion: se pierde al reiniciar."""
    def __init__(self):
        self._decididas = {}
        self.suprimidas = 0

    def decidida(self, inc):
        return _clave_supresion(inc) in self._decididas

    def recordar(self, inc, id_decision, veredicto):
        self._decididas[_clave_supresion(inc)] = {"id_decision": id_decision, "veredicto": veredicto}

    def registro_supresion(self, inc):
        clave = _clave_supresion(inc)
        prev = self._decididas[clave]
        self.suprimidas += inc["conteo"]
        return {"id_decision": f"{prev['id_decision']}~sup", "tipo": "actividad_suprimida",
                "referencia": prev["id_decision"],
                "clave": {"origen_ip": clave[0], "familia": clave[1]},
                "alertas_suprimidas": inc["conteo"],
                "primera_ts": inc.get("primera_ts"), "ultima_ts": inc.get("ultima_ts"),
                "veredicto_previo": prev["veredicto"]}


def _linea_supresion(reg):
    c = reg["clave"]
    return (f"↩ {c['origen_ip']} · {c['familia']} — ya decidido ({reg['veredicto_previo'] or 'auto'}) "
            f"· +{reg['alertas_suprimidas']} suprimida(s) [ref {reg['referencia']}]")


def _procesar_incidente(inc, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn,
                        id_decision, cadena, escribir, leer, mitigar_fn=None, encolar=None,
                        escribir_traza=None):
    rep = inc["representante"]
    escribir(_resumen_incidente(inc))
    kw = {} if justificar_fn is None else {"justificar_fn": justificar_fn}
    if mitigar_fn is not None:
        kw["mitigar_fn"] = mitigar_fn
    if encolar is not None:
        kw["encolar"] = encolar
    d = lazo.procesar_lazo(rep, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                           id_decision, rep.get("timestamp", ""), leer=leer, escribir=escribir, **kw)
    if d.get("en_cola"):            # modo web no bloqueante: se resolverá y trazará al aprobar
        escribir(_linea_en_cola(d))
        return d
    escribir(_linea_decision(d))
    if cadena is not None:
        (escribir_traza or cadena.escribir)(d)   # traza.Cadena: cada registro encadenado al anterior
    return d


def _linea_en_cola(d):
    return f"⏸ En cola (espera al analista) · {d.get('clase')} · confianza {d.get('confianza')}"


def _entrada_cola(decision, alerta):
    """Construye la entrada de la cola: contexto para resolver + líneas para mostrar (mismas que el
    prompt de la terminal, para que el visor las presente igual)."""
    from prototipo import validacion
    menu = "¿Qué hacer con este incidente?\n" + "\n".join(
        f"  {i}) {e}" for i, e in enumerate(validacion._ETIQUETAS_VEREDICTO, 1))
    incid = (f"⚠ Incidente: {alerta.get('origen_ip')} -> {alerta.get('activo')} "
             f"({alerta.get('servicio')})")
    return {"clave": (alerta.get("origen_ip"), alerta.get("familia")),
            "severidad": decision.get("prioridad") or 0,
            "decision": decision, "alerta": alerta, "recibido_en": time.time(),
            "tipo": "menu", "prompt": "Elige [1-3]: ",
            "lineas": [incid, validacion.mostrar(decision, alerta), menu]}


def _construir_resolutor(estado, perfil, catalogo, ejecutor, escribir_traza, escribir):
    """Devuelve resolver(pid, respuesta)->bool: aplica el veredicto del analista a una decisión en
    cola (ejecuta la contención + escribe la traza), sin bloquear el lazo. Reclasificar es en dos
    pasos: '3' pasa al submenú de clases; el número de clase finaliza."""
    from prototipo import analisis
    def resolver(pid, respuesta):
        entrada = estado.ver_decision(pid)
        if entrada is None:
            return False
        respuesta = (respuesta or "").strip()
        if not entrada.get("esperando_clase"):
            if respuesta == "3":                       # reclasificar -> submenú de clases (no finaliza)
                clases = [c for c in analisis.CLASES if c != entrada["decision"].get("clase")]
                menu = "Nueva clase:\n" + "\n".join(f"  {i}) {c}" for i, c in enumerate(clases, 1))
                estado.actualizar_decision(pid, {"esperando_clase": True, "clases": clases,
                                                 "lineas": entrada["lineas"][:1] + [menu],
                                                 "prompt": f"Elige [1-{len(clases)}]: "})
                return True
            veredicto, clase = {"1": "aprobar", "2": "rechazar"}.get(respuesta, "rechazar"), None
        else:
            clases = entrada.get("clases", [])
            if respuesta.isdigit() and 1 <= int(respuesta) <= len(clases):
                veredicto, clase = "reclasificar", clases[int(respuesta) - 1]
            else:
                veredicto, clase = "rechazar", None
        if estado.sacar_decision(pid) is None:         # otra respuesta ya la resolvió (carrera)
            return False
        decision, alerta = entrada["decision"], entrada["alerta"]
        r = lazo.aplicar_veredicto(decision, alerta, perfil, catalogo, ejecutor,
                                   decision.get("id_decision", ""), alerta.get("timestamp", ""),
                                   veredicto=veredicto, clase_reclasificada=clase, leer=lambda *_: "s")
        # Marcas de tiempo para el MTTR (tiempo de respuesta del analista) en el panel de métricas.
        r = {**r, "recibido_en": entrada.get("recibido_en"), "resuelto_en": time.time()}
        escribir(_linea_decision(r))
        escribir_traza(r)
        return True
    return resolver

def _contar(resumen, d):
    resumen["incidentes"] += 1
    v = d.get("veredicto_humano")
    if v == "aprobar": resumen["aprobadas"] += 1
    elif v == "reclasificar": resumen["reclasificadas"] += 1
    elif v == "rechazar": resumen["rechazadas"] += 1
    if (d.get("ejecucion") or {}).get("exito"):                    # camino determinista
        resumen["ejecutadas"] += 1
    elif (d.get("escalada") or {}).get("resultado") == "mitigado":   # el activo no respondio: escalada
        resumen["ejecutadas"] += 1
    if (d.get("mitigacion_agente") or {}).get("resultado") == "mitigado":   # camino agente
        resumen["ejecutadas"] += 1

def ejecutar(fuente_lineas, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
             justificar_fn=None, ventana_agrupacion=0, salida_traza=None,
             escribir=print, leer=input, reloj=time.monotonic, mitigar_fn=None, suprimir=True,
             hash_previo=traza.GENESIS, n_previos=0, nombre_traza="", linaje=None, estado_web=None):
    """Consume `fuente_lineas` (iterable de str crudas o None en reposo) y triaja cada incidente.

    `salida_traza` es un objeto fichero; los registros se escriben encadenados por hash (RF-09)
    a partir de `hash_previo`, que es el ultimo hash del fichero si se retoma uno existente.

    ventana_agrupacion == 0  -> cada alerta se procesa al instante (un incidente por alerta).
    ventana_agrupacion  > 0  -> se acumulan las alertas y, cuando pasan N segundos de pared desde la
                                primera (o al agotarse la fuente), se agrupan (RF-11) y se emiten los
                                incidentes; los ticks None permiten vencer la ventana sin lineas nuevas.
    """
    resumen = {"alertas": 0, "incidentes": 0, "aprobadas": 0, "rechazadas": 0,
               "reclasificadas": 0, "ejecutadas": 0, "suprimidas": 0}
    cadena = (traza.Cadena(salida_traza, hash_previo, n=n_previos, nombre=nombre_traza, linaje=linaje)
              if salida_traza is not None else None)
    # La traza puede escribirse desde dos hilos (el lazo y el servidor web al resolver una decisión
    # en cola): un lock serializa la cadena de hashes.
    _traza_lock = threading.Lock()
    def escribir_traza(reg):
        with _traza_lock:
            if cadena is not None:
                cadena.escribir(reg)
    # Modo web no bloqueante: encolar en vez de bloquear, y registrar cómo se resuelve (ejecuta+traza).
    encolar = None
    if estado_web is not None:
        def encolar(decision, alerta):
            estado_web.encolar_decision(_entrada_cola(decision, alerta))
        estado_web.fijar_resolutor(
            _construir_resolutor(estado_web, perfil, catalogo, ejecutor, escribir_traza, escribir))
    seq = [0]
    ventana_rafaga = rafaga.Ventana()
    memoria = MemoriaDecisiones()
    def _procesa_lote(lote):
        # E-minimo: bajo carga (muchos ataques distintos a la vez) se decide primero lo mas grave.
        for inc in _ordenar_por_severidad(agrupacion.agrupar(lote, ventana_seg=max(ventana_agrupacion, 1))):
            if suprimir and memoria.decidida(inc):
                # Ya se decidio sobre esta (origen_ip, familia): no se re-justifica ni se pregunta;
                # se cuenta y se deja un resumen encadenado en la traza (el ataque siguio).
                reg = memoria.registro_supresion(inc)
                escribir(_linea_supresion(reg))
                escribir_traza(reg)
                continue
            seq[0] += 1
            # La rafaga del representante se toma al emitir el incidente, cuando la ventana ya
            # contiene toda la rafaga, no al llegar la primera alerta.
            inc["representante"][rafaga.CAMPO] = ventana_rafaga.contar(inc["representante"].get("origen_ip"))
            d = _procesar_incidente(
                inc, hallazgos, perfil, perfil_nombre, catalogo, ejecutor, justificar_fn,
                f"s{seq[0]}", cadena, escribir, leer, mitigar_fn=mitigar_fn,
                encolar=encolar, escribir_traza=escribir_traza)
            _contar(resumen, d)
            # Las decisiones en cola aún no se deciden: no se recuerdan (la cola deduplica sus
            # repeticiones incrementando el contador del pendiente).
            if suprimir and not d.get("en_cola"):
                memoria.recordar(inc, f"s{seq[0]}", d.get("veredicto_humano"))

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
            resumen["alertas"] += 1; ventana_rafaga.registrar(alerta)
            _procesa_lote([alerta])
            continue
        # modo con ventana
        if linea is not None:
            alerta = _parsear(linea)
            if alerta is not None:
                resumen["alertas"] += 1; ventana_rafaga.registrar(alerta)
                if t0 is None:
                    t0 = reloj()
                buffer.append(alerta)
        if _vencio():
            _descargar()
    _descargar()                                   # fuente agotada: descarga lo pendiente
    resumen["suprimidas"] = memoria.suprimidas
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
    pos, con_llm, ventana, salida, sin_lab, agente = [], False, 5, "trazas-stream.jsonl", False, False
    web, web_puerto, sin_supresion = False, 8787, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--con-llm": con_llm = True
        elif a == "--sin-llm": con_llm = False
        elif a == "--sin-lab": sin_lab = True
        elif a == "--agente": agente = True
        elif a == "--sin-supresion": sin_supresion = True
        elif a == "--web":
            web = True
            if i + 1 < len(argv) and argv[i + 1].isdigit(): i += 1; web_puerto = int(argv[i])
        elif a == "--ventana-agrupacion": i += 1; ventana = int(argv[i])
        elif a == "--salida": i += 1; salida = argv[i]
        else: pos.append(a)
        i += 1
    return {"ruta": pos[0] if pos else "-",
            "perfil": pos[1] if len(pos) > 1 else _PERFIL_DEF,
            "hallazgos": pos[2] if len(pos) > 2 else _HALLAZGOS_DEF,
            "con_llm": con_llm, "ventana": ventana, "salida": salida, "sin_lab": sin_lab,
            "agente": agente, "web": web, "web_puerto": web_puerto, "sin_supresion": sin_supresion}

def construir_mitigar_fn(agente, perfil, catalogo, ejecutor, escribir=print, hallazgos=None):
    """Modo --agente: devuelve un `mitigar_fn(decision, alerta, leer) -> plan` que delega en el agente
    ReAct (decide estrategia, ESCALA host->firewall, aprueba POR PASO, consulta ATT&CK/D3FEND). Usa el 1B
    para el ReAct; sin modelo/indice, bucle_react degrada al motor determinista (RNF-09)."""
    if not agente:
        return None
    from prototipo import agente_mitigacion as ag, justificador_llm, rag
    try:
        indice = rag.cargar_indice()
    except Exception as e:
        escribir(f"[aviso] indice RAG no disponible para el agente ({e}); sin herramienta de conocimiento.")
        indice = None
    # El esquema se deriva del catalogo y de la topologia, y restringe el muestreo: el modelo
    # no puede nombrar una herramienta, un dispositivo ni una accion que no existan (RF-15).
    esquema = ag.esquema_accion(catalogo, ag.resolver_topologia(perfil))
    base = justificador_llm.generador_por_defecto()
    # Solo el generador por servidor entiende el esquema; con el subproceso se cae al formato
    # textual, que `parsear_accion` sigue aceptando.
    gen = ((lambda p: base(p, esquema=esquema))
           if base is justificador_llm.generador_servidor else base)
    def _fn(decision, alerta, leer):
        return ag.bucle_react(alerta, decision.get("clase"), perfil, catalogo, ejecutor,
                              gen, leer=leer, autonomo=False,
                              timestamp=decision.get("timestamp", ""),
                              indice=indice, embedder=rag.embedder_por_defecto(), escribir=escribir,
                              hallazgos=hallazgos)
    return _fn

def construir_justificar_fn(con_llm, escribir=print):
    if not con_llm:
        return None
    try:
        from prototipo import justificador_llm, rag
        indice = rag.cargar_indice()
        # RAG AGÉNTICO (Opción C): la consulta la decide el 1B y se excluyen las fichas regla-* del
        # conocimiento (palanca 3). La traza registra consulta_rag/recuperacion_agentica/pasajes_usados.
        gen = justificador_llm.generador_por_defecto()
        recuperar_fn = rag.recuperar_fn_agentico(indice, rag.embedder_por_defecto(), generador=gen, k=3)
        return justificador_llm.justificar_fn_rag(gen, recuperar_fn)
    except Exception as e:                          # sin indice/modelo -> degradar a plantilla (RNF-09)
        escribir(f"[aviso] justificador LLM/RAG no disponible ({e}); se usara la plantilla.")
        return None

_SALUD_DEF = {"contenedor": "clab-banco-mdr-siem", "fichero_en_contenedor": "/var/log/banco/salud.jsonl"}

def construir_web(cfg, perfil):
    """Arma el tablero para --web: EstadoTablero, el servidor (ligado a 127.0.0.1, SIN arrancar el
    hilo), y los `escribir`/`leer` web que se inyectan en ejecutar. Las dependencias salen del perfil."""
    from prototipo import tablero
    estado = tablero.EstadoTablero()
    activos = perfil.get("activos") or {}
    deps = {n: (a or {}).get("depende_de", []) for n, a in activos.items()}
    # Cola de aprobación no bloqueante salvo en modo agente (que aprueba por paso, bloqueante).
    async_web = not cfg.get("agente")
    servidor = tablero.crear_servidor(estado, cfg["salida"], salud=_SALUD_DEF, dependencias=deps,
                                      puerto=cfg["web_puerto"], activos=activos,
                                      topologia=perfil.get("topologia") or {}, async_web=async_web)
    return estado, servidor, tablero.escribir_web(estado), tablero.LectorWeb(estado)

_NOMBRE_EJECUTOR = {"ejecutor_ssh_clave": "conector SSH con clave (usuario dedicado, sudo acotado)",
                    "ejecutor_ssh_lab": "conector SSH del laboratorio (contrasena por defecto)"}

def banner(cfg, ejecutor=None):
    fuente = "stdin (canalizado)" if cfg["ruta"] == "-" else cfg["ruta"]
    just = "LLM+RAG" if cfg["con_llm"] else "plantilla"
    # El banner dice QUE ejecutor se usa de verdad: con cual credencial entra al nodo importa
    # tanto como con que perfil decide, y se vio un ensayo con la clave anunciando 'lab'.
    nombre = getattr(ejecutor, "__name__", "")
    lab = "simulado (--sin-lab)" if cfg["sin_lab"] else _NOMBRE_EJECUTOR.get(nombre, "conector SSH")
    ancla = f"anclada en {traza.ANCLA_DESTINO}" if traza.ANCLA_DESTINO else "SIN ancla (TRIAJE_ANCLA no definida)"
    return ("\n" + "=" * 72 +
            "\n  Monitor MDR en tiempo real — ACTIVO"
            f"\n  Perfil: {os.path.basename(cfg['perfil'])} · Justificador: {just} · Ejecutor: {lab}"
            f"\n  Escuchando: {fuente} · ventana de agrupacion: {cfg['ventana']}s · traza {ancla}"
            "\n  (Ctrl+C para detener)\n" + "=" * 72)

def _resumen_final(r):
    return ("\n── Resumen de la sesion ──\n"
            f"  Alertas vistas: {r['alertas']} · Incidentes: {r['incidentes']} · "
            f"Suprimidas: {r.get('suprimidas', 0)}\n"
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
    ejecutor = lazo._EjecutorAuto() if cfg["sin_lab"] else conector.ejecutor_por_defecto()
    mitigar_fn = construir_mitigar_fn(cfg["agente"], perfil, catalogo, ejecutor, hallazgos=hallazgos)
    fuente = leer_lineas_stdin() if cfg["ruta"] == "-" else leer_lineas_fichero(cfg["ruta"])
    print(banner(cfg, ejecutor))
    resumen = {"alertas": 0, "incidentes": 0, "aprobadas": 0, "rechazadas": 0,
               "reclasificadas": 0, "ejecutadas": 0}
    servidor, estado_web = None, None
    if cfg["web"]:
        estado, servidor, escribir_fn, leer_fn = construir_web(cfg, perfil)
        if not cfg["agente"]:
            estado_web = estado          # cola no bloqueante (fuera del modo agente)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        print(f"[web] tablero en http://127.0.0.1:{servidor.server_address[1]}")
    else:
        escribir_fn, leer_fn = print, _leer_interactivo()   # comportamiento actual (terminal)
    try:
        # Se retoma la cadena del fichero si ya existe: el ultimo hash escrito es el primer
        # hash_previo de esta sesion, asi que la traza de varias sesiones es una sola cadena.
        hash_previo = traza.ultimo_hash(cfg["salida"])
        try:
            previos = traza.leer_registros(cfg["salida"])
        except FileNotFoundError:
            previos = []
        n_previos, linaje = len(previos), traza.linaje_de(previos)
        with open(cfg["salida"], "a", encoding="utf-8") as traza_f:
            resumen = ejecutar(fuente, hallazgos, perfil, perfil_nombre, catalogo, ejecutor,
                               justificar_fn=justificar_fn, ventana_agrupacion=cfg["ventana"],
                               salida_traza=traza_f, escribir=escribir_fn, leer=leer_fn,
                               mitigar_fn=mitigar_fn, suprimir=not cfg["sin_supresion"],
                               hash_previo=hash_previo, n_previos=n_previos,
                               nombre_traza=os.path.basename(cfg["salida"]), linaje=linaje,
                               estado_web=estado_web)
    except KeyboardInterrupt:                        # Ctrl+C / SIGINT: cierre limpio con resumen
        pass
    print(_resumen_final(resumen))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
