import os, unittest
from prototipo import conector, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
ORDEN = {"decision_id": "d1", "accion_id": "BLOQUEAR_IP", "nodo_objetivo": "objetivo-vuln",
         "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}, "impacto": "localizado"}

class EjecutorFalso:
    """Simula iptables: la regla no existe hasta que se aplica."""
    def __init__(self): self.aplicada = False; self.llamadas = []
    def __call__(self, nodo_ip, comando):
        self.llamadas.append(comando)
        if "grep" in comando:                       # verificación
            return (0, "DROP ... 192.168.1.10") if self.aplicada else (1, "")
        if "-A INPUT" in comando:                    # aplicar
            self.aplicada = True; return (0, "")
        return (0, "")

class TestConector(unittest.TestCase):
    def test_render_rellena_params(self):
        cmd = conector.render_comando(CAT, "BLOQUEAR_IP", {"ip": "1.2.3.4"})
        self.assertEqual(cmd, "iptables -A INPUT -s 1.2.3.4 -j DROP")

    def test_ejecuta_y_verifica(self):
        ej = EjecutorFalso()
        r = conector.ejecutar_orden(ORDEN, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["exito"])
        self.assertFalse(r["idempotente"])
        self.assertEqual(r["comando_ejecutado"], "iptables -A INPUT -s 192.168.1.10 -j DROP")

    def test_idempotente_si_ya_aplicada(self):
        ej = EjecutorFalso(); ej.aplicada = True     # ya está
        r = conector.ejecutar_orden(ORDEN, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["idempotente"])
        self.assertTrue(r["exito"])
        self.assertNotIn("-A INPUT", " ".join(ej.llamadas))   # NO reejecutó la acción

    def test_params_con_inyeccion_se_rechazan_sin_ejecutar(self):
        ej = EjecutorFalso()
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "1.2.3.4; rm -rf /"}
        r = conector.ejecutar_orden(orden_mala, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertFalse(r["exito"])
        self.assertEqual(ej.llamadas, [])   # el ejecutor NUNCA se llamó

    def test_params_con_salto_de_linea_se_rechazan(self):
        ej = EjecutorFalso()
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "1.2.3.4\n"}
        r = conector.ejecutar_orden(orden_mala, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertFalse(r["exito"]); self.assertEqual(ej.llamadas, [])

    def test_params_con_guion_inicial_se_rechazan(self):
        ej = EjecutorFalso()
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "--algo"}
        r = conector.ejecutar_orden(orden_mala, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertFalse(r["exito"]); self.assertEqual(ej.llamadas, [])

    def test_matar_conexion_transitoria_siempre_se_ejecuta(self):
        # ss -K dst {ip}: verificación con rc0 significa "la conexión EXISTE", no "ya matada".
        # Para una acción transitoria, la idempotencia por verificación-antes-de-actuar NO aplica:
        # debe ejecutarse siempre, aunque la primera verificación dé rc0.
        orden = {"decision_id": "d1", "accion_id": "MATAR_CONEXION", "nodo_objetivo": "objetivo-vuln",
                 "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}, "impacto": "localizado"}
        class EjecutorConexion:
            def __init__(self): self.llamadas = []
            def __call__(self, nodo_ip, comando):
                self.llamadas.append(comando)
                if "grep" in comando:
                    return (0, "ESTAB ... 192.168.1.10")   # la conexión existe (antes y después)
                return (0, "")   # ss -K
        ej = EjecutorConexion()
        r = conector.ejecutar_orden(orden, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertIsNotNone(r["comando_ejecutado"])   # SÍ se ejecutó, no se saltó por "idempotencia"
        self.assertFalse(r["idempotente"])
        self.assertIn("ss -K", " ".join(ej.llamadas))


class TestEjecutorClave(unittest.TestCase):
    def test_la_linea_no_lleva_contrasena_y_verifica_el_host(self):
        linea = conector.comando_ssh_clave("192.168.1.30", "iptables -L -n | grep 1.2.3.4",
                                            usuario="triaje", clave="/k", known_hosts="/kh")
        self.assertNotIn("msfadmin", linea); self.assertNotIn("sshpass", linea)
        self.assertIn("-o StrictHostKeyChecking=yes", linea)
        self.assertIn("-o UserKnownHostsFile=/kh", linea)
        self.assertIn("-o BatchMode=yes", linea)
        self.assertIn("-o PasswordAuthentication=no", linea)
        self.assertIn("triaje@192.168.1.30", linea)

    def test_sudo_sin_contrasena_y_con_la_entrada_cerrada_a_nivel_de_ssh(self):
        # La tuberia de la verificacion debe quedar intacta: el '</dev/null' pegado al comando se
        # lo llevaba el grep y dejaba la verificacion siempre falsa (medido en vivo).
        linea = conector.comando_ssh_clave("10.0.0.1", "iptables -L -n | grep 1.2.3.4")
        self.assertIn("ssh -n ", linea)
        self.assertIn('"sudo -S iptables -L -n | grep 1.2.3.4"', linea)
        self.assertNotIn("</dev/null", linea)
        self.assertNotIn("echo", linea)

    def test_la_variable_de_entorno_decide_el_ejecutor(self):
        import os
        for modo, esperado in (("password", conector.ejecutor_ssh_lab), ("clave", conector.ejecutor_ssh_clave)):
            os.environ["TRIAJE_SSH_MODO"] = modo
            try:
                self.assertIs(conector.ejecutor_por_defecto(escribir=lambda *a: None), esperado)
            finally:
                os.environ.pop("TRIAJE_SSH_MODO", None)


class TestNodoGestion(unittest.TestCase):
    """H3: el nodo desde el que ejecuta el conector es configurable; por defecto, el de la red pequeña."""
    def test_por_defecto_el_auditor_de_la_red_pequena(self):
        import os
        from unittest import mock
        from prototipo import conector
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_NODO_GESTION", None)
            self.assertEqual(conector.nodo_gestion(), "clab-red-cliente-auditor")

    def test_configurable_por_entorno(self):
        import os
        from unittest import mock
        from prototipo import conector
        with mock.patch.dict(os.environ, {"TRIAJE_NODO_GESTION": "clab-banco-mdr-siem"}):
            self.assertEqual(conector.nodo_gestion(), "clab-banco-mdr-siem")

    def test_el_ssh_se_lanza_en_el_nodo_configurado(self):
        import os, subprocess
        from unittest import mock
        from prototipo import conector
        visto = {}
        def falso_run(args, **kw):
            visto["args"] = args
            return subprocess.CompletedProcess(args, 0, "ok", "")
        with mock.patch.dict(os.environ, {"TRIAJE_NODO_GESTION": "clab-banco-mdr-siem"}), \
             mock.patch("subprocess.run", falso_run):
            conector._ssh_en_auditor("true")
        self.assertEqual(visto["args"][:3], ["docker", "exec", "clab-banco-mdr-siem"])

