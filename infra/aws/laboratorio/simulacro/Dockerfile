# La «máquina EC2» del simulacro del laboratorio: Amazon Linux 2023 (la distribución de la AMI) con systemd
# como PID 1, para que el arranque de AWS se ejecute como en una instancia. Solo lo que una AMI trae de
# serie y el simulacro necesita para observarla (udev, losetup, socat para la consola); Docker, Containerlab
# y el resto los instala el propio arranque.
FROM amazonlinux:2023
RUN dnf install -y -q systemd systemd-udev util-linux findutils procps-ng socat && dnf clean all
CMD ["/usr/sbin/init"]
