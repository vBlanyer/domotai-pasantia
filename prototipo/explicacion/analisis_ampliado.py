"""Análisis ampliado para la tarjeta de Aprobaciones.

Cuando una decisión espera al analista, la tarjeta ya dice qué propone el motor y por qué. Esto añade
el contexto que el analista buscaría a mano antes de aprobar: qué más ha hecho ese origen en la última
hora, qué tiene abierto el equipo atacado según el último escaneo, qué dice el playbook de la familia,
y una lista corta de cosas que comprobar.

Lo arma el MDR con REGLAS sobre sus propios datos (sin modelo de lenguaje): es reproducible y cada
línea sale de una fuente que se cita. Es solo lectura: NO cambia la decisión, la clase ni la acción;
si falla, la tarjeta sale igual, sin él.
"""
import collections
import threading

from prototipo.motor import actores, rafaga

VENTANA_S = 3600          # «la última hora», con el reloj de las alertas (RNF-03), no el de pared
MAX_POR_ORIGEN = 20       # lo que se guarda de cada origen: basta para el resumen y el detalle
MAX_ORIGENES = 5000       # cota de orígenes: un atacante que rota la IP no agota memoria
MAX_DETALLE = 5           # líneas de detalle del historial en la tarjeta

GENERADO_POR = "reglas"
_CAMPOS = ("id_alerta", "regla_id", "familia", "activo", "servicio", "nivel_wazuh")


class Recientes:
    """Las últimas alertas de cada origen dentro de la ventana. Mismo patrón que `rafaga.Ventana`
    (LRU por origen, tiempo de las alertas), pero guarda qué fue cada alerta, no solo cuándo.
    Con lock: el lazo registra y la cola consulta desde hilos distintos en el modo agente."""

    def __init__(self, ventana_s=VENTANA_S, max_por_origen=MAX_POR_ORIGEN, max_origenes=MAX_ORIGENES):
        self.ventana_s = ventana_s
        self.max_por_origen = max_por_origen
        self.max_origenes = max_origenes
        self._por_origen = collections.OrderedDict()
        self._lock = threading.Lock()

    def registrar(self, alerta):
        origen, t = alerta.get("origen_ip"), rafaga._instante(alerta)
        if not origen or t is None:
            return
        entrada = {"t": t, **{k: alerta.get(k) for k in _CAMPOS}}
        with self._lock:
            cola = self._por_origen.get(origen)
            if cola is None:
                cola = self._por_origen[origen] = collections.deque(maxlen=self.max_por_origen)
            else:
                self._por_origen.move_to_end(origen)
            cola.append(entrada)
            self._purgar(cola, t)
            while len(self._por_origen) > self.max_origenes:
                self._por_origen.popitem(last=False)

    def de(self, origen):
        """Las alertas del origen que siguen en la ventana (copias, de la más antigua a la última)."""
        if not origen:
            return []
        with self._lock:
            cola = self._por_origen.get(origen)
            if not cola:
                return []
            self._purgar(cola, cola[-1]["t"])
            return [dict(e) for e in cola]

    def _purgar(self, cola, ahora):
        while cola and (ahora - cola[0]["t"]).total_seconds() > self.ventana_s:
            cola.popleft()


def _plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def _historial(alerta, recientes):
    """Sección «Este origen en la última hora» + lo que de ella hay que comprobar."""
    otras = recientes.de(alerta.get("origen_ip"))
    # Se quita UNA vez la propia alerta (la última que coincide en id e instante): Wazuh no siempre trae
    # id, y un id repetido no puede borrar del historial alertas que son otras.
    propia = (alerta.get("id_alerta"), rafaga._instante(alerta))
    for i in range(len(otras) - 1, -1, -1):
        if (otras[i].get("id_alerta"), otras[i]["t"]) == propia:
            del otras[i]
            break
    if not otras:
        return ["Es la primera alerta de este origen en la última hora."], []
    equipos = sorted({e["activo"] for e in otras if e.get("activo")} | (
        {alerta["activo"]} if alerta.get("activo") else set()))
    lineas = [f"{_plural(len(otras), 'alerta más', 'alertas más')} de este origen en la última hora, "
              f"contra {_plural(len(equipos), 'equipo', 'equipos')}: {', '.join(equipos) or '—'}."]
    for e in otras[-MAX_DETALLE:]:
        regla = f" (regla {e['regla_id']})" if e.get("regla_id") else ""
        lineas.append(f"{e['t'].strftime('%H:%M:%S')} · {e.get('familia') or '—'} · "
                      f"{e.get('activo') or '—'}{regla}")
    if len(otras) > MAX_DETALLE:
        lineas.append(f"… y {len(otras) - MAX_DETALLE} más.")
    comprobar = []
    if alerta.get("familia") != "reconocimiento" and any(e.get("familia") == "reconocimiento" for e in otras):
        comprobar.append("Este origen hizo reconocimiento (escaneo) antes del ataque: parece dirigido, "
                         "no casual.")
    if len(equipos) > 1:
        comprobar.append(f"El origen tocó {len(equipos)} equipos: valora contenerlo en el perímetro, "
                         "no solo en este equipo.")
    return lineas, comprobar


def _equipo(alerta, hallazgos, perfil):
    """Sección «El equipo atacado» + lo que de ella hay que comprobar."""
    activo = alerta.get("activo")
    if not activo:
        return ["La alerta no dice qué equipo es."], []
    lineas, comprobar = [], []
    criticidad = (((perfil or {}).get("activos") or {}).get(activo) or {}).get("criticidad")
    if criticidad:
        lineas.append(f"Criticidad declarada de {activo}: {criticidad}.")
    nodos = (hallazgos or {}).get("nodos") or {}
    if activo not in nodos:
        lineas.append(f"{activo} no aparece en el último escaneo de la red.")
        return lineas, comprobar
    abiertos = [p for p in nodos[activo] or [] if p.get("estado") == "open"]
    lista = ", ".join(f"{p.get('servicio')}/{p.get('puerto')}" for p in abiertos) or "ninguno"
    lineas.append(f"Servicios abiertos según el último escaneo: {lista}.")
    servicio = alerta.get("servicio")
    if servicio and servicio not in {p.get("servicio") for p in abiertos}:
        comprobar.append(f"El servicio atacado ({servicio}) no figura abierto en el escaneo: puede ser un "
                         "falso positivo o un escaneo desactualizado.")
    return lineas, comprobar


def _playbook(alerta, corpus):
    familia = alerta.get("familia")
    ficha = next((d for d in corpus or [] if d.get("id") == f"mapeo-{familia}"), None) if familia else None
    if ficha is None:
        return ["Sin ficha de playbook para esta familia."], None
    return [ficha.get("texto") or ""], f"corpus del playbook: {ficha['id']}"


def _origen_interno(ip, perfil):
    if not ip:
        return False
    tipo = (actores.quien_es(ip, perfil) or {}).get("tipo")
    return actores._ALCANCE.get(tipo, "externo") != "externo"


def construir(alerta, decision, recientes=None, hallazgos=None, perfil=None, corpus=None):
    """El análisis ampliado de una decisión en cola:
    {generado_por, secciones: [{titulo, lineas}], comprobar: [str], fuentes: [str]}.
    No modifica `alerta` ni `decision`."""
    alerta, decision = alerta or {}, decision or {}
    secciones, comprobar, fuentes = [], [], []

    if recientes is not None:
        lineas, extra = _historial(alerta, recientes)
        secciones.append({"titulo": "Este origen en la última hora", "lineas": lineas})
        comprobar += extra
        fuentes.append("alertas recibidas por el MDR en la última hora")

    lineas, extra = _equipo(alerta, hallazgos, perfil)
    secciones.append({"titulo": "El equipo atacado", "lineas": lineas})
    comprobar += extra
    if hallazgos:
        fuentes.append("último escaneo de la red")
    if perfil:
        fuentes.append("perfil del cliente")

    lineas, fuente = _playbook(alerta, corpus)
    secciones.append({"titulo": "Qué dice el playbook", "lineas": lineas})
    if fuente:
        fuentes.append(fuente)

    ip = alerta.get("origen_ip")
    if _origen_interno(ip, perfil):
        comprobar.insert(0, f"El origen ({ip}) es interno (de la red del cliente): confirma con el responsable del equipo "
                            "que no es una tarea programada o un administrador.")
    cascada = (decision.get("impacto_determinado") or {}).get("activos_afectados_en_cascada") or []
    if cascada:
        comprobar.append(f"Aprobar afecta también a: {', '.join(cascada)} (dependen de lo que se contiene).")
    if "accion_final" in decision and decision.get("accion_final") is None:
        comprobar.append("La acción está vetada: aprobar no ejecuta ninguna contención.")
    if not comprobar:
        comprobar.append("Nada fuera de lo normal en los datos del MDR: revisa la justificación y decide.")

    return {"generado_por": GENERADO_POR, "secciones": secciones, "comprobar": comprobar,
            "fuentes": fuentes}
