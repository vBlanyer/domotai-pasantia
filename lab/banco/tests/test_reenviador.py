import unittest
from lab.banco import reenviador


class TestLineas(unittest.TestCase):
    def test_linea_syslog_con_programa(self):
        self.assertEqual(reenviador.linea_syslog(38, "web-banking", "sshd[7]", "hola", 0),
                         "<38>Jan 01 00:00:00 web-banking sshd[7]: hola")

    def test_linea_syslog_sin_programa(self):
        self.assertEqual(reenviador.linea_syslog(30, "atm", None, "x", 0), "<30>Jan 01 00:00:00 atm x")

    def test_sshd_conserva_pid_y_mensaje(self):
        l = "Sep 22 10:00:00 web-banking sshd[123]: Failed password for root from 198.51.100.10 port 5 ssh2"
        self.assertEqual(reenviador.desde_sshd("web-banking", l, 0),
                         "<38>Jan 01 00:00:00 web-banking sshd[123]: "
                         "Failed password for root from 198.51.100.10 port 5 ssh2")

    def test_sshd_sin_prefijo_usa_la_linea_entera(self):
        self.assertEqual(reenviador.desde_sshd("hsm", "Failed password for x from 1.2.3.4 port 1 ssh2\n", 0),
                         "<38>Jan 01 00:00:00 hsm sshd[0]: Failed password for x from 1.2.3.4 port 1 ssh2")

    def test_sshd_con_retorno_de_carro_real_de_sshd_E(self):
        # sshd -E (banco.sh) escribe las lineas SIN el prefijo "sshd[pid]:" y con un \r final
        # (forma real observada en el laboratorio): sin prefijo, cae siempre por el camino de
        # respaldo (pid "0"), y el \r no debe colarse en lo que se manda a Wazuh.
        l = "Failed password for cliente from 198.51.100.10 port 40000 ssh2\r\n"
        self.assertEqual(reenviador.desde_sshd("hsm", l, 0),
                         "<38>Jan 01 00:00:00 hsm sshd[0]: "
                         "Failed password for cliente from 198.51.100.10 port 40000 ssh2")

    def test_web_como_apache(self):
        l = '198.51.100.10 - - [01/Jan/1970:00:00:00 +0000] "GET / HTTP/1.1" 200 2 "-" "curl"'
        self.assertEqual(reenviador.desde_web("web-banking", l, 0),
                         "<30>Jan 01 00:00:00 web-banking apache: " + l)


if __name__ == "__main__":
    unittest.main()
