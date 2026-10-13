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

_MAX_LINEA = 1024 * 1024        # anti-OOM: una alerta real es < 64 KiB
_MAX_CONEXIONES = 64


def _crear_servidor(host, puerto):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, puerto))
    srv.listen(_MAX_CONEXIONES)
    return srv


def _atender_cliente(cli, contexto_tls, cola, parar, max_linea):
    try:
        if contexto_tls is not None:
            cli = contexto_tls.wrap_socket(cli, server_side=True)
        cli.settimeout(1.0)
        buf, descartando = b"", False
        while not parar.is_set():
            try:
                datos = cli.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not datos:
                break                                   # EOF: el reenviador cerró
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
                    cola.put(linea.decode("utf-8", "replace"))
                # línea vacía o sobredimensionada: se ignora
    finally:
        try:
            cli.close()
        except OSError:
            pass


def escuchar(host, puerto, permitir=None, intervalo=0.5, contexto_tls=None, max_linea=_MAX_LINEA,
             _socket_servidor=None, _parar=None):
    """Generador: rinde las líneas recibidas por TCP (una por línea) y `None` en reposo (para que la
    ventana de agrupación pueda cerrarse sin alertas nuevas), igual que `stream.leer_lineas_stdin`.
    Solo acepta conexiones cuyo IP de origen esté en `permitir` (None = sin filtro); con `contexto_tls`
    envuelve cada conexión. Cierra todo al agotar el generador (.close())."""
    permitidas = set(permitir) if permitir else None
    cola = queue.Queue()
    parar = _parar or threading.Event()
    srv = _socket_servidor or _crear_servidor(host, puerto)

    def _aceptador():
        srv.settimeout(intervalo)
        while not parar.is_set():
            try:
                cli, addr = srv.accept()
            except (socket.timeout, OSError):
                continue
            if permitidas is not None and addr[0] not in permitidas:
                try:
                    cli.close()                         # origen no autorizado: se descarta (R1)
                except OSError:
                    pass
                continue
            threading.Thread(target=_atender_cliente,
                             args=(cli, contexto_tls, cola, parar, max_linea), daemon=True).start()

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
