# Imagen comun de los nodos del laboratorio del banco: servicio, monitor, reenviador, sshd para el
# conector (minimo privilegio: lab/scripts/aprovisionar-minimo-privilegio.sh) e iptables para la
# contencion. Se construye una vez: sh lab/banco/construir-imagen.sh
FROM alpine:3.20
RUN apk add --no-cache python3 openssh sudo iptables sshpass nmap curl busybox-extras \
 && ssh-keygen -A \
 && mkdir -p /opt/banco /var/log/banco \
 && sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
 && adduser -D cliente && echo 'cliente:Cliente2026' | chpasswd
COPY servicio.py monitor.py reenviador.py telnet_expuesto.py /opt/banco/
