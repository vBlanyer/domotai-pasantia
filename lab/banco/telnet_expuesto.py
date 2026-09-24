"""Servicio telnet EXPUESTO a propósito, para demostrar la familia `servicio_expuesto` del banco.

Escucha en el puerto 23 y registra `connect from <ip>` por cada conexión —el formato que decodifica
el telnet decoder de Wazuh ([lab/wazuh/local_decoder_telnetd.xml]) para sacar el srcip—. No ofrece
shell: es un señuelo de un servicio que no debería estar expuesto en un banco. El reenviador
(`reenviador.py --telnet`) manda ese log a Wazuh, que lo levanta con la regla local 100210 (grupo
`telnet`), que el adaptador mapea a `servicio_expuesto`.
"""
import socket
import sys


def main(puerto=23, registro="/var/log/banco/telnet.log"):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", puerto))
    s.listen(16)
    while True:
        try:
            conn, (ip, _) = s.accept()
        except OSError:
            continue
        try:
            # Formato de in.telnetd/tcpd ("connect from <ip> (<ip>)") que espera el telnet decoder.
            with open(registro, "a", encoding="utf-8") as f:
                f.write(f"connect from {ip} ({ip})\n")
        except OSError:
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 23
    r = sys.argv[2] if len(sys.argv) > 2 else "/var/log/banco/telnet.log"
    main(p, r)
