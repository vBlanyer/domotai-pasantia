import os, unittest
from prototipo.accion import conector, catalogo

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

    def test_registra_la_hora_real_de_ejecucion(self):
        # `timestamp` es la hora de la alerta; cuándo se contuvo de verdad va en `ejecutado_en`.
        import datetime
        r = conector.ejecutar_orden(ORDEN, CAT, EjecutorFalso(), "2026-08-31T00:00:00Z")
        self.assertEqual(r["timestamp"], "2026-08-31T00:00:00Z")
        hora = datetime.datetime.fromisoformat(r["ejecutado_en"])
        self.assertIsNotNone(hora.tzinfo)
        self.assertLess(abs((datetime.datetime.now(datetime.timezone.utc) - hora).total_seconds()), 60)

    def test_idempotente_si_ya_aplicada(self):
        ej = EjecutorFalso(); ej.aplicada = True     # ya está
        r = conector.ejecutar_orden(ORDEN, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["idempotente"])
        self.assertTrue(r["exito"])
        self.assertNotIn("-A INPUT", " ".join(ej.llamadas))   # NO reejecutó la acción

    def test_un_parametro_ausente_no_se_renderiza_como_none(self):
        self.assertFalse(conector._params_seguros({"ip": None}))
        self.assertFalse(conector._params_seguros({"ip": "None"}))
        self.assertTrue(conector._params_seguros({"ip": "192.168.1.10"}))

    def test_env_filtrado_excluye_secretos(self):
        # V1.1 #3: el subproceso (docker/ssh) no debe heredar los secretos del MDR en su entorno.
        os.environ["TRIAJE_TRAZA_CLAVE"] = "secreto-hmac"
        try:
            env = conector._env_filtrado()
            self.assertNotIn("TRIAJE_TRAZA_CLAVE", env)
            self.assertIn("PATH", env)      # lo que docker/ssh SÍ necesitan sigue presente
        finally:
            os.environ.pop("TRIAJE_TRAZA_CLAVE", None)

    def test_main_orden_malformada_falla_cerrado(self):
        # V1.1 #5 (#19): una orden sin accion_id no revienta con traceback; se reporta y sale != 0.
        import io, sys
        orig_in, orig_out = sys.stdin, sys.stdout
        sys.stdin, sys.stdout = io.StringIO("{}"), io.StringIO()
        try:
            rc = conector._main(["conector"])
            salida = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = orig_in, orig_out
        self.assertEqual(rc, 1)
        self.assertIn("error", salida)

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

    def test_limitar_banda_con_interfaz_hostil_se_rechaza_sin_ejecutar(self):
        # 7ª familia (DoS): if/rate se interpolan en la línea SSH; una interfaz con metacaracteres
        # (de un perfil comprometido) se rechaza fail-closed antes de renderizar el `tc`.
        ej = EjecutorFalso()
        orden_mala = {**ORDEN, "accion_id": "LIMITAR_BANDA", "params": {"if": "eth0; reboot", "rate": "1mbit"}}
        r = conector.ejecutar_orden(orden_mala, CAT, ej, "t")
        self.assertFalse(r["exito"])
        self.assertEqual(ej.llamadas, [])   # nunca se ejecutó

    def test_nodo_ip_con_inyeccion_se_rechaza_sin_ejecutar(self):
        # #2: nodo_ip se interpola en la linea SSH que corre por `sh -c` en el nodo de gestion ->
        # un valor con metacaracteres seria RCE en el auditor. Debe rechazarse sin ejecutar nada.
        ej = EjecutorFalso()
        orden_mala = {**ORDEN, "nodo_ip": "192.168.1.30; touch /tmp/pwned #"}
        r = conector.ejecutar_orden(orden_mala, CAT, ej, "t")
        self.assertFalse(r["exito"])
        self.assertEqual(ej.llamadas, [])
        self.assertIn("nodo_ip", r["salida"])

    def test_nodo_ip_valida_se_ejecuta(self):
        r = conector.ejecutar_orden(ORDEN, CAT, EjecutorFalso(), "t")   # nodo_ip 192.168.1.30
        self.assertTrue(r["exito"])

    def test_ip_valida_acepta_v4_y_v6_y_rechaza_el_resto(self):
        self.assertTrue(conector.ip_valida("192.168.1.1"))
        self.assertTrue(conector.ip_valida("::1"))
        for mala in ("1.2.3.4; rm -rf /", "host.local", "", None, "1.2.3.4 2.2.2.2"):
            self.assertFalse(conector.ip_valida(mala), mala)

    def test_params_con_guion_inicial_se_rechazan(self):
        ej = EjecutorFalso()
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "--algo"}
        r = conector.ejecutar_orden(orden_mala, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertFalse(r["exito"]); self.assertEqual(ej.llamadas, [])

    def test_matar_conexion_transitoria_siempre_se_ejecuta(self):
        # ss -K dst {ip}: la verificación lista conexiones (`ss -tunap`) y el match es sobre la salida.
        # Para una acción transitoria, la idempotencia por verificación-antes-de-actuar NO aplica:
        # debe ejecutarse siempre, aunque la conexión siga presente.
        orden = {"decision_id": "d1", "accion_id": "MATAR_CONEXION", "nodo_objetivo": "objetivo-vuln",
                 "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}, "impacto": "localizado"}
        class EjecutorConexion:
            def __init__(self): self.llamadas = []
            def __call__(self, nodo_ip, comando):
                self.llamadas.append(comando)
                if "ss -K" in comando:
                    return (0, "")   # el corte "corrió"
                return (0, "tcp ESTAB 0 0 10.10.0.10:22 192.168.1.10:51000")   # la conexión sigue listada
        ej = EjecutorConexion()
        r = conector.ejecutar_orden(orden, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertIsNotNone(r["comando_ejecutado"])   # SÍ se ejecutó, no se saltó por "idempotencia"
        self.assertFalse(r["idempotente"])
        self.assertIn("ss -K", " ".join(ej.llamadas))
        self.assertFalse(r["exito"])   # la conexión SIGUE viva tras el corte -> NO es éxito (transitoria)

    def test_matar_conexion_corte_efectivo_es_exito(self):
        # Transitoria: tras `ss -K`, si el listado corre (rc0) y la IP YA NO aparece, el corte
        # funcionó -> exito True.
        orden = {"decision_id": "d1", "accion_id": "MATAR_CONEXION", "nodo_objetivo": "objetivo-vuln",
                 "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}, "impacto": "localizado"}
        class EjecutorCorta:
            def __init__(self): self.llamadas = []
            def __call__(self, nodo_ip, comando):
                self.llamadas.append(comando)
                if "ss -K" in comando:
                    return (0, "")   # el corte corrió
                return (0, "tcp ESTAB 0 0 10.10.0.10:22 10.0.0.5:4000")   # la IP objetivo YA NO está
        ej = EjecutorCorta()
        r = conector.ejecutar_orden(orden, CAT, ej, "2026-08-31T00:00:00Z")
        self.assertTrue(r["exito"])
        self.assertIn("ss -K", " ".join(ej.llamadas))

    def test_matar_conexion_fail_closed_si_el_post_check_no_puede_ejecutarse(self):
        # El post-check de una transitoria usaba `rc != 0 = cortada`, así que un FALLO del chequeo
        # (ss ausente rc127, SSH caído rc255, timeout rc124, error rc2) se leía como corte exitoso
        # aunque la sesión siguiera viva: FAIL-OPEN. Como el match es sobre la salida con rc0, un
        # rc!=0 del listado (ni corrió) debe fallar CERRADO.
        orden = {"decision_id": "d1", "accion_id": "MATAR_CONEXION", "nodo_objetivo": "objetivo-vuln",
                 "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}, "impacto": "localizado"}
        for rc_fallo in (127, 255, 124, 2):
            class EjecutorChequeoRoto:
                def __call__(self, nodo_ip, comando, rc=rc_fallo):
                    return (0, "") if "ss -K" in comando else (rc, "")   # el listado NO pudo correr
            r = conector.ejecutar_orden(orden, CAT, EjecutorChequeoRoto(), "t")
            self.assertFalse(r["exito"], f"rc {rc_fallo} debe fallar cerrado")


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

    def test_fail_closed_sin_clave_ni_modo_no_cae_a_msfadmin(self):
        # #7: sin clave aprovisionada y sin TRIAJE_SSH_MODO explicito, el conector NO debe caer en
        # silencio a la credencial de laboratorio (msfadmin); rechaza (fail-closed).
        import os
        from unittest import mock
        os.environ.pop("TRIAJE_SSH_MODO", None)
        with mock.patch.object(conector, "_clave_aprovisionada", return_value=False):
            ej = conector.ejecutor_por_defecto(escribir=lambda *a: None)
        self.assertIsNot(ej, conector.ejecutor_ssh_lab)
        rc, _ = ej("1.2.3.4", "iptables -A INPUT -s 1.2.3.4 -j DROP")
        self.assertNotEqual(rc, 0)


class TestSshConPlazo(unittest.TestCase):
    """Un docker exec colgado bloqueaba el lazo (o el hilo HTTP) sin límite."""
    def test_un_ssh_colgado_devuelve_un_codigo_en_lugar_de_bloquear(self):
        import subprocess
        from unittest import mock
        visto = {}
        def colgado(args, **kw):
            visto.update(kw); raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        with mock.patch("subprocess.run", colgado):
            rc, salida = conector._ssh_en_auditor("ssh x")
        self.assertEqual(rc, 124)
        self.assertTrue(visto.get("timeout"))

    def test_sin_docker_devuelve_un_codigo(self):
        from unittest import mock
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("docker")):
            rc, salida = conector._ssh_en_auditor("ssh x")
        self.assertEqual(rc, 127)
        self.assertIn("docker", salida)


class TestNodoGestion(unittest.TestCase):
    """H3: el nodo desde el que ejecuta el conector es configurable; por defecto, el de la red pequeña."""
    def test_por_defecto_el_auditor_de_la_red_pequena(self):
        import os
        from unittest import mock
        from prototipo.accion import conector
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_NODO_GESTION", None)
            self.assertEqual(conector.nodo_gestion(), "clab-red-cliente-auditor")

    def test_configurable_por_entorno(self):
        import os
        from unittest import mock
        from prototipo.accion import conector
        with mock.patch.dict(os.environ, {"TRIAJE_NODO_GESTION": "clab-banco-mdr-siem"}):
            self.assertEqual(conector.nodo_gestion(), "clab-banco-mdr-siem")

    def test_el_ssh_se_lanza_en_el_nodo_configurado(self):
        import os, subprocess
        from unittest import mock
        from prototipo.accion import conector
        visto = {}
        def falso_run(args, **kw):
            visto["args"] = args
            return subprocess.CompletedProcess(args, 0, "ok", "")
        with mock.patch.dict(os.environ, {"TRIAJE_NODO_GESTION": "clab-banco-mdr-siem"}), \
             mock.patch("subprocess.run", falso_run):
            conector._ssh_en_auditor("true")
        self.assertEqual(visto["args"][:3], ["docker", "exec", "clab-banco-mdr-siem"])



class TestVerificacionExacta(unittest.TestCase):
    """La verificación no puede dar por bloqueada una IP que solo es prefijo de otra ya bloqueada."""
    def _orden(self, ip):
        return {**ORDEN, "params": {"ip": ip}}

    def test_una_ip_prefijo_de_otra_bloqueada_no_es_idempotente(self):
        from prototipo.tests.iptables_falso import NodoIptables
        for ya, nueva in (("198.51.100.110", "198.51.100.11"), ("192.168.1.10", "192.168.1.1")):
            nodo = NodoIptables(drop_input=[ya])
            r = conector.ejecutar_orden(self._orden(nueva), CAT, nodo, "t")
            self.assertFalse(r["idempotente"], (ya, nueva))
            self.assertEqual(r["comando_ejecutado"], f"iptables -A INPUT -s {nueva} -j DROP")
            self.assertTrue(r["exito"])
            self.assertIn(("DROP", nueva), nodo.reglas["INPUT"])

    def test_una_regla_accept_no_cuenta_como_bloqueo(self):
        from prototipo.tests.iptables_falso import NodoIptables
        from prototipo.accion import verificacion
        nodo = NodoIptables(accept_input=["192.168.1.10"])
        self.assertFalse(verificacion.confirmar(ORDEN, CAT, nodo)["verificado"])
        nodo.reglas["INPUT"].append(("DROP", "192.168.1.10"))
        self.assertTrue(verificacion.confirmar(ORDEN, CAT, nodo)["verificado"])


class TestEjecutorDirecto(unittest.TestCase):
    """Modo `directo` (v2 adelantado): SSH desde el HOST del daemon, sin docker exec — para
    desplegar donde no hay Docker. Mismas opciones endurecidas que el modo clave."""

    def test_los_args_llevan_el_endurecimiento_y_sin_shell(self):
        args = conector._args_ssh_directo("192.168.1.30", "iptables -L -n")
        self.assertIsInstance(args, list)                      # argv, nunca una cadena por sh -c
        self.assertEqual(args[0], "ssh")
        self.assertIn("-n", args)                              # stdin cerrado: sudo -S falla, no espera
        self.assertIn("BatchMode=yes", args)
        self.assertIn("StrictHostKeyChecking=yes", args)
        self.assertTrue(any(a.startswith("UserKnownHostsFile=") for a in args))
        self.assertEqual(args[-1], "sudo -S iptables -L -n")
        self.assertEqual(args[-2], f"{conector.SSH_USUARIO}@192.168.1.30")

    def test_ejecuta_con_entorno_filtrado_y_plazo(self):
        from unittest import mock
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            rc, salida = conector.ejecutor_ssh_directo("192.168.1.30", "iptables -L -n")
        self.assertEqual((rc, salida), (0, "ok"))
        args, kw = run.call_args
        self.assertEqual(args[0][0], "ssh")
        self.assertEqual(kw["timeout"], conector.PLAZO_SSH_S)
        self.assertFalse([k for k in kw["env"] if k.startswith("TRIAJE_")])   # sin secretos al hijo

    def test_timeout_devuelve_124(self):
        from unittest import mock
        import subprocess as sp
        with mock.patch("subprocess.run", side_effect=sp.TimeoutExpired("ssh", 1)):
            rc, _ = conector.ejecutor_ssh_directo("192.168.1.30", "iptables -L -n")
        self.assertEqual(rc, 124)

    def test_modo_directo_sin_clave_en_el_host_queda_fail_closed(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {"TRIAJE_SSH_MODO": "directo"}), \
             mock.patch.object(conector, "SSH_CLAVE", "/no/existe/clave"):
            ej = conector.ejecutor_por_defecto(escribir=lambda *a: None)
            rc, salida = ej("192.168.1.30", "iptables -L -n")
        self.assertEqual(rc, 126)                              # el ejecutor que rechaza, no ssh

    def test_modo_directo_con_clave_usa_el_ejecutor_directo(self):
        import tempfile
        from unittest import mock
        with tempfile.NamedTemporaryFile() as clave, \
             mock.patch.dict(os.environ, {"TRIAJE_SSH_MODO": "directo"}), \
             mock.patch.object(conector, "SSH_CLAVE", clave.name):
            ej = conector.ejecutor_por_defecto(escribir=lambda *a: None)
        self.assertIs(ej, conector.ejecutor_ssh_directo)
