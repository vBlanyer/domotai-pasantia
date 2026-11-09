"""API de la vista «Conectividad»: resumen (GET), prueba, guardado (solo si la prueba pasa) y clave del
host. Sin red ni docker: el modo, el `correr` y el ejecutor se inyectan en el servidor."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from prototipo.accion import conectividad as cx
from prototipo.servicio import tablero

PERFIL = {"ip_gestion": "10.0.30.3",
          "activos": {"fw-core": {"ip": "10.0.0.1"}, "db-core": {"ip": "10.0.20.10"}, "monitor": {"ip": "10.0.30.3"}},
          "red": {"zonas": {"Borde": ["fw-core"], "Servidores": ["db-core"], "Gestion": ["monitor"]}}}
from prototipo.tests.test_conectividad import K1, F1, K2, F2, K3, F3
PUB = K1 + " conector-triaje"
KNOWN = f"10.0.0.1 {K2}\n10.0.20.10 {K3}\n"            # fw-core -> F2, db-core -> F3 (la vieja)
NUEVA_DB = K1                                              # lo que presenta db-core ahora -> F1


class _Falso:
    """Lo que el servidor ejecutaría: ficheros de claves (correr) y ssh a los equipos (ejecutor)."""
    def __init__(self):
        self.ssh = {}            # ip -> [(rc, salida), ...] por orden
        self.vistos = []         # (ip, usuario, puerto, cmd)
        self.escrito = None

    def correr(self, args, entrada=None):
        if args[:1] == ["cat"] and args[1].endswith(".pub"):
            return 0, PUB + "\n"
        if args[0] == "ssh-keyscan":
            return 0, f"10.0.20.10 {NUEVA_DB}\n"
        if args[:1] == ["cat"]:
            return 0, KNOWN
        if args[:1] == ["tee"]:
            self.escrito = entrada
            return 0, entrada
        if args[0] in ("cp", "mv", "rm", "ssh-keygen"):
            self.ficheros.append(args)
            return 0, ""
        return 1, "?"

    ficheros = None
    sudo_l = None                # salida de `sudo -l` del usuario del conector (None = pide contraseña)

    def ejecutor_con(self, modo, usuario=None, puerto=None, sudo=True, claves=None):
        def ej(ip, cmd):
            self.vistos.append((ip, usuario, puerto, cmd) if sudo and not claves else (ip, usuario, puerto, cmd, sudo, tuple(claves or ())))
            if not sudo:
                if cmd == "sudo -S -l":
                    return (0, self.sudo_l) if self.sudo_l else (1, "sudo: a password is required")
                return 0, ""
            if claves:
                return 0, "ok"
            cola = self.ssh.setdefault(ip, [(0, "ok"), (1, "denegado")])
            return cola.pop(0) if len(cola) > 1 else cola[0]
        return ej


class _Base(unittest.TestCase):
    def _srv(self, operadores=None, modo="clave"):
        d = tempfile.mkdtemp()
        self.ruta, self.au = os.path.join(d, "conectividad.yml"), os.path.join(d, "conectividad-auditoria.jsonl")
        self.f = _Falso()
        self.f.ficheros = []
        srv = tablero.crear_servidor(tablero.EstadoTablero(), os.path.join(d, "t.jsonl"), puerto=0,
                                     estaticos=tempfile.mkdtemp(), perfil=json.loads(json.dumps(PERFIL)),
                                     operadores=operadores, ruta_conectividad=self.ruta,
                                     ruta_auditoria_conectividad=self.au)
        srv.conectividad_modo = lambda: modo
        srv.conectividad_correr = lambda m: self.f.correr
        srv.conectividad_ejecutor = self.f.ejecutor_con
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv

    def _req(self, srv, metodo, ruta, obj=None, token=None):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        c.request(metodo, ruta, json.dumps(obj) if obj is not None else None, h)
        r = c.getresponse(); cuerpo = r.read(); c.close()
        return r.status, json.loads(cuerpo)

    def _eq(self, est, nombre):
        return next(e for e in est["equipos"] if e["nombre"] == nombre)

class TestConectividadWeb(_Base):
    def test_resumen(self):
        srv = self._srv({"tok": "ana"})
        st, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual(st, 200)
        self.assertEqual(est["modo"], "clave")
        self.assertEqual(est["clave"], {"huella": F1, "tipo": "ED25519", "publica": PUB})
        self.assertNotIn("PRIVATE", json.dumps(est))
        fw = self._eq(est, "fw-core")
        self.assertEqual((fw["ip"], fw["puerto"], fw["usuario"], fw["huella_fijada"], fw["protegido"]), ("10.0.0.1", 22, "triaje", F2, False))
        self.assertTrue(self._eq(est, "monitor")["protegido"])                  # canal de gestión del MDR
        self.assertTrue(est["editable"])

    def test_sin_operador_es_solo_lectura_y_no_guarda(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRIAJE_CONECTIVIDAD_ABIERTA", None)
            srv = self._srv()
            self.assertFalse(self._req(srv, "GET", "/api/conectividad")[1]["editable"])
            self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222})[0], 403)
            self.assertEqual(self._req(srv, "POST", "/api/conectividad/clave-host", {"equipo": "db-core", "huella": F1})[0], 403)
        self.assertFalse(os.path.exists(self.ruta))

    def test_probar_no_guarda_y_recuerda_el_resultado(self):
        srv = self._srv({"tok": "ana"})
        st, r = self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "fw-core", "puerto": 2222}, token="tok")
        self.assertEqual((st, r["estado"], r["ok"]), (200, "verificada", True))
        self.assertEqual(self.f.vistos[0][:3], ("10.0.0.1", "triaje", 2222))    # probó con el candidato
        self.assertFalse(os.path.exists(self.ruta))
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual(self._eq(est, "fw-core")["ultima_prueba"]["estado"], "verificada")

    def test_guardar_solo_si_la_prueba_pasa(self):
        srv = self._srv({"tok": "ana"})
        self.f.ssh["10.0.0.1"] = [(255, "Permission denied (publickey).")]
        st, r = self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222, "usuario": "ops"}, token="tok")
        self.assertEqual((st, r["guardado"], r["prueba"]["estado"]), (409, False, "sin_aprovisionar"))
        self.assertFalse(os.path.exists(self.ruta))
        self.f.ssh["10.0.0.1"] = [(0, "ok"), (1, "denegado")]
        st, r = self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222, "usuario": "ops"}, token="tok")
        self.assertEqual((st, r["guardado"]), (200, True))
        self.assertEqual(cx.cargar(self.ruta)["equipos"], {"10.0.0.1": {"nombre": "fw-core", "puerto": 2222, "usuario": "ops"}})
        with open(self.au) as f:
            aud = [json.loads(l) for l in f]
        self.assertEqual((aud[-1]["operador"], aud[-1]["clave"]), ("ana", "fw-core"))
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        fw = self._eq(est, "fw-core")
        self.assertEqual((fw["puerto"], fw["usuario"], fw["ajustado"]), (2222, "ops", True))
        self.assertEqual(est["cambios"][0]["clave"], "fw-core")

    def test_validacion(self):
        srv = self._srv({"tok": "ana"})
        for cuerpo in ({"equipo": "no-existe", "puerto": 22}, {"equipo": "fw-core", "puerto": 99999},
                       {"equipo": "fw-core", "usuario": "root;id"}, {"equipo": "monitor", "puerto": 2222}):
            self.assertEqual(self._req(srv, "POST", "/api/conectividad", cuerpo, token="tok")[0], 400, cuerpo)
        self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"usuario_defecto": "a b"}, token="tok")[0], 400)

    def test_usuario_por_defecto(self):
        srv = self._srv({"tok": "ana"})
        self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"usuario_defecto": "mdr"}, token="tok")[0], 200)
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual((est["usuario_defecto"], self._eq(est, "fw-core")["usuario"]), ("mdr", "mdr"))

    def test_modo_laboratorio_no_admite_edicion(self):
        srv = self._srv({"tok": "ana"}, modo="password")
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertFalse(est["editable"])
        self.assertIsNone(est["clave"])
        self.assertEqual(self._req(srv, "POST", "/api/conectividad", {"equipo": "fw-core", "puerto": 2222}, token="tok")[0], 409)

    def test_clave_del_host(self):
        srv = self._srv({"tok": "ana"})
        st, r = self._req(srv, "POST", "/api/conectividad/leer-clave-host", {"equipo": "db-core"}, token="tok")
        self.assertEqual((st, r["fijada"], r["presentada"], r["coincide"]), (200, F3, F1, False))
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/clave-host", {"equipo": "db-core", "huella": F2}, token="tok")[0], 409)
        self.assertIsNone(self.f.escrito)
        st, r = self._req(srv, "POST", "/api/conectividad/clave-host", {"equipo": "db-core", "huella": F1}, token="tok")
        self.assertEqual((st, r["huella"]), (200, F1))
        self.assertEqual(self.f.escrito, f"10.0.0.1 {K2}\n10.0.20.10 {NUEVA_DB}\n")
        with open(self.au) as f:
            self.assertEqual(json.loads(f.read().splitlines()[-1])["dimension"], "clave_host")


class TestPermisosAltaYRotacion(_Base):
    """Probar exige operador; freno por equipo; auditoría; pruebas en disco; alta en dos tiempos; rotación."""
    CAT = None

    def _srv_cat(self, **kw):
        from prototipo.accion import catalogo
        srv = self._srv(**kw)
        srv.catalogo = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
        return srv

    def test_probar_y_leer_exigen_operador(self):
        srv = self._srv()                                   # sin mapa de operadores ni opt-in
        _, est = self._req(srv, "GET", "/api/conectividad")
        self.assertEqual(est["permisos"], {"probar": False, "editar": False, "generar_clave": False,
                                           "motivo": "probar y cambiar exigen un operador identificado por su token"})
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core", "operador": "x"})[0], 403)
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/leer-clave-host", {"equipo": "db-core"})[0], 403)
        self.assertEqual(self.f.vistos, [])                 # no se abrió ninguna conexión

    def test_freno_por_equipo_auditoria_y_prueba_en_disco(self):
        srv = self._srv({"tok": "ana"})
        st, r = self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        self.assertEqual((st, r["estado"], r["por"]), (200, "verificada", "ana"))
        st, r = self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        self.assertEqual(st, 429)
        self.assertTrue(1 <= r["reintentar_en"] <= 10)
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "fw-core"}, token="tok")[0], 200)
        with open(self.au) as f:
            ult = json.loads(f.read().splitlines()[-1])
        self.assertEqual((ult["dimension"], ult["clave"], ult["operador"]), ("prueba", "fw-core", "ana"))
        self.assertIn("10.0.20.10", cx.cargar_pruebas(srv.ruta_pruebas))          # sobrevive al reinicio

    def test_deriva_del_sudoers(self):
        srv = self._srv_cat(operadores={"tok": "ana"})
        self.f.sudo_l = "    (root) NOPASSWD: /sbin/iptables -L -n, /bin/cat *"
        st, r = self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        self.assertEqual((r["estado"], r["reglas"]["estado"]), ("privilegio_de_mas", "sobran"))
        self.assertIn("cat *", r["reglas"]["sobran"])

    def test_alta_de_un_equipo_nuevo(self):
        srv = self._srv_cat(operadores={"tok": "ana"})
        datos = {"nombre": "pagos-qr", "ip": "10.0.20.20", "zona": "Servidores", "funcion": "Pagos QR", "criticidad": "alta",
                 "depende_de": ["db-core"], "papel": "servidor", "servicios": ["nginx"], "cuentas": ["appqr"]}
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/inventario", {**datos, "cuentas": ["root"]}, token="tok")[0], 400)
        st, r = self._req(srv, "POST", "/api/conectividad/inventario", datos, token="tok")
        self.assertEqual((st, r["alta"]), (200, "pendiente"))
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual((self._eq(est, "pagos-qr")["alta"], self._eq(est, "pagos-qr")["papel"]), ("pendiente", "servidor"))
        self.assertNotIn("pagos-qr", srv.perfil.get("activos") or {})            # pendiente: el motor aún no lo ve
        st, p = self._req(srv, "GET", "/api/conectividad/paquete?equipo=pagos-qr&formato=script", token="tok")
        self.assertEqual((st, p["nombre"]), (200, "alta-pagos-qr.sh"))
        self.assertIn("regla 'service' 'nginx stop'", p["contenido"])
        self.assertIn(PUB, p["contenido"])
        # sin clave del host fijada no hay alta
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/alta", {"equipo": "pagos-qr", "huella": F1}, token="tok")[0], 409)
        global KNOWN
        antes, KNOWN = KNOWN, KNOWN + f"10.0.20.20 {K1}\n"
        try:
            self.f.sudo_l = None
            st, r = self._req(srv, "POST", "/api/conectividad/alta", {"equipo": "pagos-qr", "huella": F1}, token="tok")
        finally:
            KNOWN = antes
        self.assertEqual((st, r["alta"]), (200, "activo"))
        self.assertEqual(srv.perfil["activos"]["pagos-qr"]["criticidad"], "alta")    # ya en el motor
        self.assertIn("pagos-qr", srv.perfil["red"]["zonas"]["Servidores"])
        self.assertEqual(srv.perfil["papeles_equipo"]["pagos-qr"]["servicios"], ["nginx"])

    def test_papel_de_un_equipo_existente_y_quitarlo(self):
        srv = self._srv_cat(operadores={"tok": "ana"})
        self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        self.assertIn("10.0.20.10", srv.conectividad_pruebas)
        st, _ = self._req(srv, "POST", "/api/conectividad/inventario", {"nombre": "db-core", "papel": "puesto"}, token="tok")
        self.assertEqual(st, 200)
        self.assertNotIn("10.0.20.10", srv.conectividad_pruebas)          # comparaba con otras reglas: se olvida
        self.assertEqual(srv.perfil["papeles_equipo"]["db-core"]["papel"], "puesto")
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/inventario", {"nombre": "monitor", "papel": "puesto"}, token="tok")[0], 400)
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/inventario/quitar", {"nombre": "db-core"}, token="tok")[0], 200)
        self.assertNotIn("papeles_equipo", srv.perfil)

    def test_rotacion_en_tres_fases(self):
        srv = self._srv_cat(operadores={"tok": "ana"})
        pub_nueva = K3 + " mdr-conector"
        original = self.f.correr
        def correr(args, entrada=None):
            if args[:1] == ["cat"] and args[1].endswith(".nueva.pub"):
                return 0, pub_nueva + "\n"
            return original(args, entrada)
        srv.conectividad_correr = lambda m: correr
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "preparar"}, token="tok")[0], 409)
        st, r = self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "iniciar"}, token="tok")
        self.assertEqual((st, r["rotacion"]["huella_nueva"]), (200, F3))
        self.assertTrue(any(a[0] == "ssh-keygen" for a in self.f.ficheros))
        st, r = self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "finalizar"}, token="tok")
        self.assertEqual(st, 409)                                        # aún no se retiró la vieja en ningún equipo
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "preparar"}, token="tok")[0], 200)
        anadir = [v for v in self.f.vistos if len(v) > 4 and v[4] is False and "authorized_keys" in v[3]]
        self.assertTrue(anadir and all(K3.split()[1] in v[3] for v in anadir))
        st, r = self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "retirar"}, token="tok")
        self.assertTrue(all(f.get("retirada") for f in r["rotacion"]["equipos"].values()))
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "cancelar"}, token="tok")[0], 409)
        st, r = self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "finalizar"}, token="tok")
        self.assertEqual((st, r["rotacion"]), (200, None))
        movidos = [a for a in self.f.ficheros if a[0] == "mv"]
        self.assertEqual(movidos[-2][2:], [movidos[-2][2], movidos[-2][3]])
        self.assertTrue(movidos[-2][2].endswith(".nueva") and not movidos[-2][3].endswith(".nueva"))

    def test_cancelar_quita_la_nueva(self):
        srv = self._srv_cat(operadores={"tok": "ana"})
        original = self.f.correr
        srv.conectividad_correr = lambda m: (lambda a, e=None: (0, K3 + " mdr-conector\n") if a[:1] == ["cat"] and a[1].endswith(".nueva.pub") else original(a, e))
        self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "iniciar"}, token="tok")
        self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "preparar"}, token="tok")
        st, r = self._req(srv, "POST", "/api/conectividad/rotacion", {"accion": "cancelar"}, token="tok")
        self.assertEqual((st, r["rotacion"]), (200, None))
        quitar = [v for v in self.f.vistos if len(v) > 4 and v[3].startswith("grep -qF")]
        self.assertTrue(quitar)


class TestClaveDesdeCeroYEstadoViejo(_Base):
    """G1/G7: generar la clave del conector desde la vista; G8: lo viejo no se presenta como vigente; G4."""

    def _sin_clave(self, srv):
        estado = {"clave": None}
        original = self.f.correr
        def correr(args, entrada=None):
            if args[:1] == ["cat"] and args[1].endswith("triaje.pub"):
                return (0, estado["clave"] + "\n") if estado["clave"] else (1, "cat: no such file")
            if args[0] == "ssh-keygen":
                estado["clave"] = K2 + " mdr-conector"
                self.f.ficheros.append(args)
                return 0, ""
            if args[0] in ("mkdir", "chmod", "true", "test"):
                self.f.ficheros.append(args)
                return 0, ""
            return original(args, entrada)
        srv.conectividad_correr = lambda m: correr
        return estado

    def test_sin_clave_la_vista_lo_dice_y_se_genera_una_vez(self):
        srv = self._srv({"tok": "ana"}, modo="sin_configurar")
        self._sin_clave(srv)
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertTrue(est["falta_clave"])
        self.assertTrue(est["permisos"]["generar_clave"])
        self.assertFalse(est["permisos"]["probar"])
        self.assertIn("falta la clave del conector", est["permisos"]["motivo"])
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/clave-conector", {"tipo": "dsa"}, token="tok")[0], 400)
        st, r = self._req(srv, "POST", "/api/conectividad/clave-conector", {"tipo": "ed25519"}, token="tok")
        self.assertEqual((st, r["clave"]["huella"]), (200, F2))
        keygen = next(a for a in self.f.ficheros if a[0] == "ssh-keygen")
        self.assertEqual(keygen[keygen.index("-t") + 1], "ed25519")
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/clave-conector", {}, token="tok")[0], 409)   # ya hay: rotación
        with open(self.au) as f:
            self.assertEqual(json.loads(f.read().splitlines()[-1])["dimension"], "clave_conector")

    def test_generar_la_clave_exige_operador(self):
        srv = self._srv(modo="sin_configurar")
        self._sin_clave(srv)
        self.assertEqual(self._req(srv, "POST", "/api/conectividad/clave-conector", {"operador": "x"})[0], 403)
        self.assertFalse(any(a[0] == "ssh-keygen" for a in self.f.ficheros))

    def test_una_prueba_con_otra_clave_del_conector_deja_de_valer(self):
        srv = self._srv({"tok": "ana"})
        self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual(self._eq(est, "db-core")["ultima_prueba"]["estado"], "verificada")
        srv.conectividad_pruebas["10.0.20.10"]["clave_conector"] = "SHA256:otra-clave"   # laboratorio recreado
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertIsNone(self._eq(est, "db-core")["ultima_prueba"])

    def test_una_rotacion_sin_par_nuevo_se_descarta(self):
        srv = self._srv({"tok": "ana"})
        cx.guardar_rotacion(srv.ruta_rotacion, {"estado": "en_curso", "equipos": {}, "publica_actual": PUB, "publica_nueva": PUB})
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")      # el doble responde «no existe» a test -f
        self.assertIsNone(est["rotacion"])
        self.assertIsNone(cx.cargar_rotacion(srv.ruta_rotacion))

    def test_contexto_para_clasificar_un_fallo(self):
        # lo que la consola le dice al clasificador de fallos (accion/fallos): solo lectura, sin ssh
        from prototipo.servicio import conectividad_web as cw
        srv = TestPermisosAltaYRotacion._srv_cat(self, operadores={"tok": "ana"})
        self.assertEqual(cw.contexto_equipo(srv, "10.0.20.10"), {"aprovisionado": True, "verificado": False, "prueba_en": None})
        self.assertFalse(cw.contexto_equipo(srv, "10.0.20.99")["aprovisionado"])      # sin huella fijada
        self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        vistos = len(self.f.vistos)
        ctx = cw.contexto_equipo(srv, "10.0.20.10", "BLOQUEAR_IP")
        self.assertTrue(ctx["verificado"] and ctx["prueba_en"])
        self.assertNotIn("regla_falta", ctx)
        self.assertEqual(len(self.f.vistos), vistos)                    # no abre ninguna conexión al equipo
        self.f.sudo_l = "    (root) NOPASSWD: /sbin/iptables -L -n"     # el sudoers no tiene la regla de bloquear
        srv.conectividad_ultimo.clear()
        self.f.ssh["10.0.20.10"] = [(0, "ok"), (1, "denegado")]
        self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        ctx = cw.contexto_equipo(srv, "10.0.20.10", "BLOQUEAR_IP")
        self.assertTrue(ctx["regla_falta"].startswith("iptables "))
        self.assertEqual(cw.contexto_equipo(srv, "10.0.20.10", "NO_EXISTE").get("regla_falta"), None)
        self.assertEqual(cw.contexto_equipo(self._srv(modo="laboratorio"), "10.0.20.10"), {})   # sin claves que mirar

    def test_estado_operativo_de_las_contenciones_reales(self):
        # fase 3: un fallo de contención deja un aviso encima de la prueba; nunca la pone en verde
        from prototipo.accion import fallos
        from prototipo.servicio import conectividad_web as cw
        srv = self._srv({"tok": "ana"})
        self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")
        f5 = fallos.clasificar_fallo({"exito": False, "codigo_salida": 255, "salida": "ssh: connect to host x port 22: Connection refused"},
                                     contexto={"verificado": True})
        cw.registrar_operativo(srv, "10.0.20.10", f5)
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        db = self._eq(est, "db-core")
        self.assertEqual(db["ultima_prueba"]["estado"], "verificada")            # la prueba sigue ahí
        self.assertEqual((db["operativo"]["clase"], db["operativo"]["regresion"]), ("F5", True))
        self.assertNotIn("evidencia", db["operativo"])                           # la salida en bruto no viaja
        self.assertIsNone(self._eq(est, "fw-core")["operativo"])
        cw.registrar_operativo(srv, "10.0.20.10", None)                          # una contención correcta lo quita
        self.assertNotIn("10.0.20.10", srv.conectividad_operativo)
        cw.registrar_operativo(srv, "10.0.20.10", f5)
        srv.conectividad_ultimo.clear()
        self.f.ssh["10.0.20.10"] = [(0, "ok"), (1, "denegado")]
        self._req(srv, "POST", "/api/conectividad/probar", {"equipo": "db-core"}, token="tok")   # y una prueba correcta
        self.assertNotIn("10.0.20.10", srv.conectividad_operativo)

    def test_memoria_de_fallos_en_la_vista_y_sondeo_sin_sudo(self):
        from prototipo.accion import memoria_fallos as mem
        from prototipo.servicio import conectividad_web as cw
        mem.reiniciar()
        self.addCleanup(mem.reiniciar)
        srv = self._srv({"tok": "ana"})
        for t in range(3):
            mem.registrar("10.0.20.10", {"clase": "F5"}, ahora=t)
        with mock.patch.dict(os.environ, {"TRIAJE_MEMORIA_FALLOS": "1"}):
            _, est = self._req(srv, "GET", "/api/conectividad", token="tok")
        self.assertEqual(self._eq(est, "db-core")["sin_acceso"]["clase"], "F5")
        self.assertIsNone(self._eq(est, "fw-core")["sin_acceso"])
        _, est = self._req(srv, "GET", "/api/conectividad", token="tok")          # interruptor apagado: nada
        self.assertIsNone(self._eq(est, "db-core")["sin_acceso"])
        self.assertEqual(cw.sondear_acceso(srv, "10.0.20.10"), (0, ""))
        self.assertEqual(self.f.vistos[-1][3:5], ("true", False))                 # sin sudo, comando inocuo
        self.assertIsNone(cw.sondear_acceso(self._srv(modo="password"), "10.0.20.10"))

    def test_cualquier_cuenta_salvo_las_del_sistema(self):
        from prototipo.accion import catalogo
        srv = self._srv({"tok": "ana"})
        srv.catalogo = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
        st, _ = self._req(srv, "POST", "/api/conectividad/inventario",
                          {"nombre": "db-core", "papel": "servidor", "cuentas_cualquiera": True, "cuentas": ["ignorada"]}, token="tok")
        self.assertEqual(st, 200)
        pe = srv.perfil["papeles_equipo"]["db-core"]
        self.assertEqual((pe["cuentas_cualquiera"], pe["cuentas"]), (True, []))
        self.assertIn("FORZAR_CAMBIO_PASS", pe["acciones"])
        from prototipo.motor import perfil as perfilm
        self.assertIsNone(perfilm.papel_deniega(srv.perfil, "FORZAR_CAMBIO_PASS", "db-core", {"usuario": "backdoor"}))
        self.assertIn("cuenta del sistema", perfilm.papel_deniega(srv.perfil, "FORZAR_CAMBIO_PASS", "db-core", {"usuario": "root"}))
        _, p = self._req(srv, "GET", "/api/conectividad/paquete?equipo=db-core&formato=sudoers", token="tok")
        self.assertIn("passwd -l *", p["contenido"])                                   # comodín, como el clásico
        self.assertIn("cuentas: cualquiera salvo las del sistema", p["contenido"])


if __name__ == "__main__":
    unittest.main()
