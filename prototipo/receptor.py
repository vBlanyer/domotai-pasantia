"""Receptor de alertas por red (#1): un servidor TCP que entrega al daemon las líneas que le reenvía
el SIEM del cliente, en vez de leerlas de un fichero/stdin. Es la fuente para `stream.ejecutar`.

Seguridad (mitiga R1 del análisis CEF — un syslog UDP abierto convierte el auto-bloqueo en un arma de
DoS por alertas falsas):
  - **Lista blanca de IPs** (`permitir`): solo se aceptan conexiones de las IPs del SIEM; el resto se
    cierran al instante, con aviso (frenado) en el log.
  - **TCP** (no UDP: no spoofeable) y **TLS opcional** (`contexto_tls`), con **mTLS opcional** (`ca`:
    exige certificado de cliente, autentica al emisor); alternativa: terminar TLS en un proxy delante.
  - Tope de tamaño de línea (anti-OOM), de conexiones concurrentes, **por IP** (una sola IP no
    monopoliza los slots) y **plazo de inactividad** (una conexión ociosa no retiene su slot).

Alcance: transporte. Asume el MISMO formato de línea que el daemon ya parsea (un JSON de alerta por
línea, como el alerts.json de Wazuh). El enmarcado syslog / multi-formato CEF es un ítem aparte.
"""
import collections
import queue
import socket
import sys
import threading
import time

_MAX_LINEA = 1024 * 1024        # anti-OOM por línea: una alerta real es < 64 KiB
_MAX_CONEXIONES = 64            # tope de conexiones vivas a la vez (no solo backlog)
_MAX_POR_IP = 8                 # tope por IP de origen: un emisor comprometido no agota los slots
_MAX_COLA = 10000               # anti-OOM del total en vuelo: al llenarse, se aplica backpressure TCP
_HANDSHAKE_S = 10.0             # tope del handshake TLS: corta slowloris en el saludo
_INACTIVIDAD_S = 900.0          # sin datos en 15 min -> cierre (el reenviador reconecta; systemd)
_AVISO_CADA_S = 60.0            # freno de los avisos por motivo: visibilidad sin inundar el log


def _avisador(avisar):
    """Avisos con freno por motivo (uno cada _AVISO_CADA_S, con el conteo de los suprimidos): un
    rechazo deja rastro —cerrar en silencio esconde tanto el ataque como el error de configuración—
    pero un atacante no convierte el log en su arma."""
    emitir = avisar if avisar is not None else (lambda m: print(m, file=sys.stderr))
    ultimo, lock = {}, threading.Lock()
    def _f(clave, mensaje):
        with lock:
            t, suprimidos = ultimo.get(clave, (None, 0))
            if t is not None and time.monotonic() - t < _AVISO_CADA_S:
                ultimo[clave] = (t, suprimidos + 1)
                return
            ultimo[clave] = (time.monotonic(), 0)
        extra = f" (y {suprimidos} más desde el último aviso)" if suprimidos else ""
        emitir(f"[aviso] receptor: {mensaje}{extra}")
    return _f


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

def _atender_cliente(cli, contexto_tls, cola, parar, max_linea, liberar, intervalo, inactividad_s,
                     aviso, ip):
    import ssl
    try:
        cli.settimeout(_HANDSHAKE_S)                    # tope del handshake TLS (anti-slowloris)
        if contexto_tls is not None:
            try:
                cli = contexto_tls.wrap_socket(cli, server_side=True)
            except (ssl.SSLError, OSError):
                return                                  # handshake fallido (p. ej. cliente sin TLS o sin cert): cierre limpio
        cli.settimeout(min(1.0, inactividad_s))         # timeout corto: mirar `parar` y la inactividad
        ultimo_dato = time.monotonic()
        buf, descartando = b"", False
        while not parar.is_set():
            try:
                datos = cli.recv(65536)
            except socket.timeout:
                if time.monotonic() - ultimo_dato >= inactividad_s:
                    aviso("inactiva", f"conexión de {ip} sin datos en {int(inactividad_s)} s: "
                                      "cerrada (el reenviador reconecta)")
                    break                               # ociosa: libera el slot (M1), no lo retiene
                continue
            except OSError:
                break
            if not datos:
                break                                   # EOF: el reenviador cerró
            ultimo_dato = time.monotonic()
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
        liberar()                                       # libera la cuota de conexión (total y por IP)


def escuchar(host, puerto, permitir=None, intervalo=0.5, contexto_tls=None, max_linea=_MAX_LINEA,
             cola_max=_MAX_COLA, max_conexiones=_MAX_CONEXIONES, max_por_ip=_MAX_POR_IP,
             inactividad_s=_INACTIVIDAD_S, avisar=None, _socket_servidor=None, _parar=None):
    """Generador: rinde las líneas recibidas por TCP (una por línea) y `None` en reposo (para que la
    ventana de agrupación pueda cerrarse sin alertas nuevas), igual que `stream.leer_lineas_stdin`.

    `permitir`: lista blanca de IPs de origen. **None = sin filtro (abierto)**; una lista vacía `[]`
    (se dio la lista pero sin IPs) **rechaza a todos** (fail-closed), no abre. Con `contexto_tls`
    envuelve cada conexión. La cola está acotada (`cola_max`): si se llena, se aplica backpressure al
    emisor en vez de agotar memoria. `max_conexiones` y `max_por_ip` acotan las conexiones vivas (en
    total y por IP de origen); `inactividad_s` cierra la conexión que no envía nada (una ociosa no
    retiene su slot). Los rechazos y cierres se avisan con freno vía `avisar` (por defecto, stderr).
    Cierra todo al agotar el generador (.close())."""
    permitidas = set(permitir) if permitir is not None else None   # [] -> set() -> rechaza a todos
    cola = queue.Queue(maxsize=cola_max)
    parar = _parar or threading.Event()
    sem = threading.BoundedSemaphore(max_conexiones)
    aviso = _avisador(avisar)
    conteo_ip, lock_ip = collections.Counter(), threading.Lock()
    srv = _socket_servidor or _crear_servidor(host, puerto)

    def _aceptador():
        srv.settimeout(intervalo)
        while not parar.is_set():
            try:
                cli, addr = srv.accept()
            except (socket.timeout, OSError):
                continue
            ip, motivo = addr[0], None
            if permitidas is not None and ip not in permitidas:
                motivo = ("no-autorizada", f"conexión de {ip} rechazada: no autorizada (fuera de --permitir)")
            else:
                with lock_ip:
                    if conteo_ip[ip] >= max_por_ip:
                        motivo = ("tope-ip", f"conexión de {ip} rechazada: tope por IP ({max_por_ip})")
                    elif not sem.acquire(blocking=False):
                        motivo = ("tope-total", f"conexión de {ip} rechazada: tope de conexiones ({max_conexiones})")
                    else:
                        conteo_ip[ip] += 1
            if motivo is not None:
                aviso(*motivo)                          # el rechazo deja rastro (M1): nunca en silencio
                try:
                    cli.close()
                except OSError:
                    pass
                continue

            def _liberar(ip=ip):
                with lock_ip:
                    conteo_ip[ip] -= 1
                    if conteo_ip[ip] <= 0:
                        del conteo_ip[ip]
                sem.release()

            threading.Thread(target=_atender_cliente, daemon=True,
                             args=(cli, contexto_tls, cola, parar, max_linea, _liberar, intervalo,
                                   inactividad_s, aviso, ip)).start()

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


def contexto_tls(cert, clave, ca=None):
    """SSLContext de servidor para el receptor (TLS directo, sin proxy delante). Carga cert+clave.
    Con `ca` (fichero de CA) exige certificado de CLIENTE firmado por ella (mTLS, M2): el TLS pasa
    de solo cifrar a autenticar al emisor — la lista blanca de IPs deja de ser la única barrera."""
    import ssl
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=clave)
    if ca:
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=ca)
    return ctx
