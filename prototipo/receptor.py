"""Receptor de alertas por red (#1): un servidor TCP que entrega al daemon las líneas que le reenvía
el SIEM del cliente, en vez de leerlas de un fichero/stdin. Es la fuente para `stream.ejecutar`.

Seguridad (mitiga R1 del análisis CEF — un syslog UDP abierto convierte el auto-bloqueo en un arma de
DoS por alertas falsas):
  - **Lista blanca de IPs** (`permitir`): solo se aceptan conexiones de las IPs del SIEM; el resto se
    cierran al instante.
  - **TCP** (no UDP: no spoofeable) y **TLS opcional** (`contexto_tls`); alternativa: terminar TLS en
    un proxy de la empresa delante.
  - Tope de tamaño de línea (anti-OOM) y de conexiones concurrentes.

Alcance: transporte. Asume el MISMO formato de línea que el daemon ya parsea (un JSON de alerta por
línea, como el alerts.json de Wazuh). El enmarcado syslog / multi-formato CEF es un ítem aparte.
"""
import queue
import socket
import threading

_MAX_LINEA = 1024 * 1024        # anti-OOM por línea: una alerta real es < 64 KiB
_MAX_CONEXIONES = 64            # tope de conexiones vivas a la vez (no solo backlog)
_MAX_COLA = 10000               # anti-OOM del total en vuelo: al llenarse, se aplica backpressure TCP
_HANDSHAKE_S = 10.0             # tope del handshake (TLS y primera lectura): corta slowloris


def _crear_servidor(host, puerto):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, puerto))
    srv.listen(_MAX_CONEXIONES)
    return srv


def _encolar(cola, linea, parar, intervalo):
    """Encola la línea aplicando backpressure: si la cola está llena, espera (no descarta alertas ni
    agota memoria); el TCP del emisor se frena solo. Mira `parar` para no colgar en el apagado."""
    while not parar.is_set():
        try:
            cola.put(linea, timeout=intervalo); return
        except queue.Full:
            continue

def _atender_cliente(cli, contexto_tls, cola, parar, max_linea, sem, intervalo):
    import ssl
    try:
        cli.settimeout(_HANDSHAKE_S)                    # tope del handshake/primera lectura (anti-slowloris)
        if contexto_tls is not None:
            try:
                cli = contexto_tls.wrap_socket(cli, server_side=True)
            except (ssl.SSLError, OSError):
                return                                  # handshake fallido (p. ej. cliente sin TLS): cierre limpio
        buf, descartando = b"", False
        while not parar.is_set():
            try:
                datos = cli.recv(65536)
            except socket.timeout:
                cli.settimeout(1.0)                     # tras el primer dato, timeout corto para mirar `parar`
                continue
            except OSError:
                break
            if not datos:
                break                                   # EOF: el reenviador cerró
            cli.settimeout(1.0)
            buf += datos
            if descartando:                             # reanuda tras una línea sin fin sobredimensionada
                nl = buf.find(b"\n")
                if nl == -1:
                    buf = b""; continue
                buf, descartando = buf[nl + 1:], False
            while True:
                nl = buf.find(b"\n")
                if nl == -1:
                    if len(buf) > max_linea:
                        buf, descartando = b"", True    # línea sin fin demasiado grande: descartar y resync
                    break
                linea, buf = buf[:nl], buf[nl + 1:]
                if 0 < len(linea) <= max_linea:
                    _encolar(cola, linea.decode("utf-8", "replace"), parar, intervalo)
                # línea vacía o sobredimensionada: se ignora
    finally:
        try:
            cli.close()
        except OSError:
            pass
        sem.release()                                   # libera la cuota de conexión


def escuchar(host, puerto, permitir=None, intervalo=0.5, contexto_tls=None, max_linea=_MAX_LINEA,
             cola_max=_MAX_COLA, max_conexiones=_MAX_CONEXIONES, _socket_servidor=None, _parar=None):
    """Generador: rinde las líneas recibidas por TCP (una por línea) y `None` en reposo (para que la
    ventana de agrupación pueda cerrarse sin alertas nuevas), igual que `stream.leer_lineas_stdin`.

    `permitir`: lista blanca de IPs de origen. **None = sin filtro (abierto)**; una lista vacía `[]`
    (se dio la lista pero sin IPs) **rechaza a todos** (fail-closed), no abre. Con `contexto_tls`
    envuelve cada conexión. La cola está acotada (`cola_max`): si se llena, se aplica backpressure al
    emisor en vez de agotar memoria. `max_conexiones` acota las conexiones vivas a la vez. Cierra todo
    al agotar el generador (.close())."""
    permitidas = set(permitir) if permitir is not None else None   # [] -> set() -> rechaza a todos
    cola = queue.Queue(maxsize=cola_max)
    parar = _parar or threading.Event()
    sem = threading.BoundedSemaphore(max_conexiones)
    srv = _socket_servidor or _crear_servidor(host, puerto)

    def _aceptador():
        srv.settimeout(intervalo)
        while not parar.is_set():
            try:
                cli, addr = srv.accept()
            except (socket.timeout, OSError):
                continue
            if (permitidas is not None and addr[0] not in permitidas) or not sem.acquire(blocking=False):
                try:
                    cli.close()                         # origen no autorizado (R1) o tope de conexiones
                except OSError:
                    pass
                continue
            threading.Thread(target=_atender_cliente, daemon=True,
                             args=(cli, contexto_tls, cola, parar, max_linea, sem, intervalo)).start()

    threading.Thread(target=_aceptador, daemon=True).start()
    try:
        while True:
            try:
                yield cola.get(timeout=intervalo)
            except queue.Empty:
                yield None                              # reposo
    finally:
        parar.set()
        try:
            srv.close()
        except OSError:
            pass


def contexto_tls(cert, clave):
    """SSLContext de servidor para el receptor (TLS directo, sin proxy delante). Carga cert+clave."""
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=clave)
    return ctx
