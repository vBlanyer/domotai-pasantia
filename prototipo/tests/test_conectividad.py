"""Conectividad del conector con cada equipo: ajustes operativos (puerto/usuario por equipo), prueba
de conexión y clave del host fijada. Todo lo que toca procesos se prueba con un `correr` inyectado."""
import os
import tempfile
import unittest

from prototipo.accion import conectividad as cx


class TestValidacion(unittest.TestCase):
    def test_puerto(self):
        self.assertEqual(cx.validar_puerto(2222), 2222)
        self.assertEqual(cx.validar_puerto("22"), 22)
        self.assertIsNone(cx.validar_puerto(None))
        for malo in (0, 70000, "22; rm", -1, 2.5, True):
            with self.assertRaises(ValueError):
                cx.validar_puerto(malo)

    def test_usuario(self):
        self.assertEqual(cx.validar_usuario("triaje"), "triaje")
        self.assertIsNone(cx.validar_usuario(None))
        for malo in ("", "root;id", "-oProxyCommand", "a b", "x" * 40, "Raíz"):
            with self.assertRaises(ValueError):
                cx.validar_usuario(malo)


class TestAjustes(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "conectividad.yml")

    def test_sin_fichero_es_vacio(self):
        self.assertEqual(cx.cargar(self.ruta), {"usuario_defecto": None, "equipos": {}})

    def test_cambio_guardar_y_leer(self):
        a = cx.con_cambio(cx.cargar(self.ruta), "10.0.0.1", "fw-core", puerto=2222, usuario=None)
        cx.guardar(self.ruta, a)
        self.assertEqual(cx.cargar(self.ruta)["equipos"], {"10.0.0.1": {"nombre": "fw-core", "puerto": 2222}})
        self.assertEqual(cx.ajustes_de("10.0.0.1", self.ruta), (None, 2222))
        self.assertEqual(cx.ajustes_de("10.0.0.9", self.ruta), (None, None))

    def test_borrar_todos_los_campos_quita_el_equipo(self):
        a = cx.con_cambio({"usuario_defecto": None, "equipos": {"10.0.0.1": {"nombre": "fw", "puerto": 2222}}},
                          "10.0.0.1", "fw", puerto=None, usuario=None)
        self.assertEqual(a["equipos"], {})

    def test_usuario_por_defecto(self):
        cx.guardar(self.ruta, {"usuario_defecto": "mdr", "equipos": {}})
        self.assertEqual(cx.ajustes_de("10.0.0.1", self.ruta), ("mdr", None))

    def test_fichero_corrupto_no_tumba_y_se_ignora(self):
        with open(self.ruta, "w") as f:
            f.write("equipos: [esto no es un mapa\n")
        self.assertEqual(cx.cargar(self.ruta), {"usuario_defecto": None, "equipos": {}})

    def test_valores_invalidos_en_el_fichero_se_descartan(self):
        with open(self.ruta, "w") as f:
            f.write("usuario_defecto: 'root;id'\nequipos:\n  10.0.0.1: {nombre: fw, puerto: 99999, usuario: ok}\n  'no-ip': {puerto: 22}\n")
        self.assertEqual(cx.cargar(self.ruta), {"usuario_defecto": None, "equipos": {"10.0.0.1": {"nombre": "fw", "usuario": "ok"}}})


class TestDiagnostico(unittest.TestCase):
    def test_clasifica_la_salida_de_ssh(self):
        self.assertEqual(cx.diagnosticar(0, "Chain INPUT"), "ok")
        self.assertEqual(cx.diagnosticar(255, "@@@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!\nHost key verification failed."), "host_cambiada")
        self.assertEqual(cx.diagnosticar(255, "No ED25519 host key is known for 10.0.0.1 and you have requested strict checking.\nHost key verification failed."), "sin_fijar")
        self.assertEqual(cx.diagnosticar(255, "triaje@10.0.0.1: Permission denied (publickey)."), "sin_clave")
        self.assertEqual(cx.diagnosticar(255, "ssh: connect to host 10.0.0.1 port 22: Connection refused"), "sin_acceso")
        self.assertEqual(cx.diagnosticar(124, "sin respuesta en 30 s"), "sin_acceso")
        self.assertEqual(cx.diagnosticar(1, "sudo: a password is required"), "fallo")


class TestProbar(unittest.TestCase):
    def _ej(self, respuestas):
        vistos = []
        def ej(ip, cmd):
            vistos.append(cmd)
            return respuestas[len(vistos) - 1]
        return ej, vistos

    def test_verificada(self):
        ej, vistos = self._ej([(0, "Chain INPUT"), (1, "sudo: a password is required")])
        r = cx.probar(ej, "10.0.0.1")
        self.assertEqual(r["estado"], "verificada")
        self.assertTrue(r["ok"])
        self.assertEqual(vistos, ["iptables -L -n", "cat /etc/shadow"])
        self.assertEqual([p["ok"] for p in r["pasos"]], [True, True])

    def test_privilegio_de_mas(self):
        ej, _ = self._ej([(0, "Chain INPUT"), (0, "root:x:0:0")])
        r = cx.probar(ej, "10.0.0.1")
        self.assertEqual(r["estado"], "privilegio_de_mas")
        self.assertFalse(r["ok"])
        self.assertNotIn("root:x", str(r))      # la salida del comando prohibido no se devuelve

    def test_clave_del_host_cambiada_para_en_el_primer_paso(self):
        ej, vistos = self._ej([(255, "Host key verification failed. REMOTE HOST IDENTIFICATION HAS CHANGED")])
        r = cx.probar(ej, "10.0.0.1")
        self.assertEqual(r["estado"], "host_cambiada")
        self.assertEqual(len(vistos), 1)

    def test_sin_aprovisionar(self):
        ej, _ = self._ej([(255, "Permission denied (publickey).")])
        self.assertEqual(cx.probar(ej, "10.0.0.1")["estado"], "sin_aprovisionar")


# Vectores reales: claves públicas de usar y tirar y su huella según `ssh-keygen -lf`.
K1 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF/7bYGREpCZ8SnmFLNPD1CnPsD4G/c633ZnOV5cwanv"
F1 = "SHA256:JcWCSH40l44QWi8kL8QsTR2bI4S5BdN67D8vbs7dwgw"
K2 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPfIkXId/44Af8ZGI0lr8U1AEgWRC44IjLDmEMWLSVXA"
F2 = "SHA256:hfkI2kFyRcGZperGJEZdq/898aGz+D3ZOyw4HSiItVg"
K3 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPCVe3SEAOp7dGJg57zZQnPdXwUARhVeR0cXIGonfGE+"
F3 = "SHA256:6EkGHKQ2IdQHkuC+P7SU00CfEbNAqWVbiUJWn24cOD4"


class TestHuellas(unittest.TestCase):
    def test_huella_igual_que_ssh_keygen(self):
        self.assertEqual(cx.huella_de(K1 + " prueba"), (F1, "ED25519"))
        self.assertEqual(cx.huella_de("10.0.0.1 " + K2), (F2, "ED25519"))
        self.assertEqual(cx.huella_de("no es una clave"), (None, None))
        self.assertEqual(cx.huella_de("ssh-ed25519 %%%"), (None, None))

    def test_known_hosts_prefiere_ed25519_y_entiende_puertos(self):
        texto = f"10.0.0.1 ssh-rsa AAAAB3NzaC1yc2E=\n10.0.0.1 {K1}\n[10.0.10.6]:2222 {K2}\n|1|hash= {K3}\n"
        self.assertEqual(cx.huellas_fijadas(texto), {"10.0.0.1": F1, "10.0.10.6": F2})
        self.assertEqual([t for t, _ in cx.claves_de_known_hosts(texto)["10.0.0.1"]], ["RSA", "ED25519"])

    def test_reemplazar_host_solo_toca_ese_equipo(self):
        texto = f"10.0.0.1 {K1}\n10.0.0.2 {K2}\n[10.0.0.1]:2222 {K3}\n"
        self.assertEqual(cx.reemplazar_host(texto, "10.0.0.1", [f"10.0.0.1 {K3}"]), f"10.0.0.2 {K2}\n10.0.0.1 {K3}\n")

    def _correr(self, presenta, con_keyscan=True):
        llamadas = []
        def correr(args, entrada=None):
            llamadas.append((args, entrada))
            if args[0] == "ssh-keyscan":
                return (0, f"10.0.0.1 {presenta}\n") if con_keyscan else (127, "exec: ssh-keyscan: not found")
            if args[:1] == ["cat"] and args[1].startswith("/tmp/mdr-escaneo"):
                return 0, f"10.0.0.1 {presenta}\n"
            if args[:1] == ["cat"]:
                return 0, f"10.0.0.1 {K1}\n10.0.0.2 {K2}\n"
            if args[:1] == ["tee"]:
                return 0, entrada
            return 0, ""
        return correr, llamadas

    def test_aceptar_exige_la_huella_confirmada(self):
        correr, llamadas = self._correr(K3)
        with self.assertRaises(cx.HuellaDistinta):
            cx.aceptar_clave_host("10.0.0.1", 22, F2, "/kh", correr)
        self.assertFalse(any(a[:1] == ["tee"] for a, _ in llamadas))      # no escribió nada
        self.assertEqual(cx.aceptar_clave_host("10.0.0.1", 22, F3, "/kh", correr), F3)
        self.assertEqual([e for a, e in llamadas if a[:1] == ["tee"]], [f"10.0.0.2 {K2}\n10.0.0.1 {K3}\n"])

    def test_sin_ssh_keyscan_usa_ssh_hacia_un_fichero_temporal(self):
        correr, llamadas = self._correr(K3, con_keyscan=False)
        self.assertEqual(cx.huella_presentada("10.0.0.1", 2222, correr), F3)
        ssh = next(a for a, _ in llamadas if a[0] == "ssh")
        self.assertIn("StrictHostKeyChecking=accept-new", ssh)
        self.assertIn("UserKnownHostsFile=/tmp/mdr-escaneo-10.0.0.1-2222", ssh)
        self.assertEqual(ssh[ssh.index("-p") + 1], "2222")
        self.assertIn(["rm", "-f", "/tmp/mdr-escaneo-10.0.0.1-2222"], [a for a, _ in llamadas])

    def test_ip_invalida(self):
        with self.assertRaises(ValueError):
            cx.huella_presentada("10.0.0.1; rm -rf /", 22, lambda *a: (0, ""))


class TestConectorUsaLosAjustes(unittest.TestCase):
    def setUp(self):
        from prototipo.accion import conector
        self.cn = conector
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "c.yml")
        cx.guardar(self.ruta, {"usuario_defecto": "mdr", "equipos": {"10.0.0.1": {"nombre": "fw", "puerto": 2222, "usuario": "ops"}}})
        self._prev = os.environ.get("TRIAJE_CONECTIVIDAD")
        os.environ["TRIAJE_CONECTIVIDAD"] = self.ruta

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("TRIAJE_CONECTIVIDAD", None)
        else:
            os.environ["TRIAJE_CONECTIVIDAD"] = self._prev

    def test_linea_ssh_con_puerto_solo_si_no_es_22(self):
        self.assertNotIn(" -p ", self.cn.comando_ssh_clave("10.0.0.1", "iptables -L -n"))
        self.assertIn(" -p 2222", self.cn.comando_ssh_clave("10.0.0.1", "iptables -L -n", puerto=2222))
        self.assertEqual(self.cn._args_ssh_directo("10.0.0.1", "x", puerto=2222)[-4:-2], ["-p", "2222"])

    def test_el_ejecutor_lee_usuario_y_puerto_del_equipo(self):
        lineas = []
        orig = self.cn._ssh_en_auditor
        self.cn._ssh_en_auditor = lambda linea: lineas.append(linea) or (0, "")
        try:
            self.cn.ejecutor_ssh_clave("10.0.0.1", "iptables -L -n")
            self.cn.ejecutor_ssh_clave("10.0.0.2", "iptables -L -n")          # sin ajuste propio: usuario por defecto
            self.cn.ejecutor_ssh_clave("10.0.0.1", "iptables -L -n", usuario="cand", puerto=22)   # prueba de candidatos
        finally:
            self.cn._ssh_en_auditor = orig
        self.assertIn(" -p 2222", lineas[0]); self.assertIn("ops@10.0.0.1", lineas[0])
        self.assertNotIn(" -p ", lineas[1]); self.assertIn("mdr@10.0.0.2", lineas[1])
        self.assertNotIn(" -p ", lineas[2]); self.assertIn("cand@10.0.0.1", lineas[2])

    def test_ejecutor_con_en_laboratorio_no_ejecuta(self):
        rc, salida = self.cn.ejecutor_con("password")("10.0.0.1", "iptables -L -n")
        self.assertEqual(rc, 126)
