import os, unittest
from prototipo.accion import verificacion, catalogo

CAT = catalogo.cargar_catalogo(os.path.join(os.path.dirname(__file__), "..", "catalogo.yml"))
ORDEN = {"accion_id": "BLOQUEAR_IP", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}

class TestVerificacion(unittest.TestCase):
    def test_verificado_cuando_la_regla_esta(self):
        r = verificacion.confirmar(ORDEN, CAT, lambda ip, cmd: (0, "DROP ... 192.168.1.10"))
        self.assertTrue(r["verificado"])
        self.assertIn("192.168.1.10", r["evidencia"])

    def test_no_verificado_cuando_no_esta(self):
        r = verificacion.confirmar(ORDEN, CAT, lambda ip, cmd: (1, ""))
        self.assertFalse(r["verificado"])

    def test_transitoria_verificado_cuando_la_conexion_murio(self):
        # MATAR_CONEXION es transitoria: la verificación lista las conexiones (`ss -tunap`) y el match
        # se hace sobre la SALIDA, no sobre el rc del pipe. rc0 (el listado corrió) + la IP AUSENTE del
        # listado = la conexión murió = acción aplicada.
        o = {"accion_id": "MATAR_CONEXION", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}
        r = verificacion.confirmar(o, CAT, lambda ip, cmd: (0, "tcp ESTAB 0 0 10.10.0.10:22 10.0.0.5:4000"))
        self.assertTrue(r["verificado"])   # la IP objetivo no aparece -> cortada

    def test_transitoria_no_verificado_si_la_conexion_sigue_viva(self):
        o = {"accion_id": "MATAR_CONEXION", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}
        r = verificacion.confirmar(o, CAT, lambda ip, cmd: (0, "tcp ESTAB 0 0 10.10.0.10:22 192.168.1.10:51000"))
        self.assertFalse(r["verificado"])   # la IP sigue en el listado -> NO se cortó

    def test_transitoria_fail_closed_si_el_chequeo_no_puede_ejecutarse(self):
        # Un FALLO del chequeo (ss ausente rc127, SSH caído rc255, timeout rc124, error rc2) NO debe
        # leerse como «conexión muerta». Como el match es sobre la salida con rc0, un rc!=0 (el listado
        # ni corrió) falla CERRADO. Antes `rc != 0` lo daba por verificado = FAIL-OPEN.
        o = {"accion_id": "MATAR_CONEXION", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}
        for rc_fallo in (127, 255, 124, 2):
            r = verificacion.confirmar(o, CAT, lambda ip, cmd, rc=rc_fallo: (rc, ""))
            self.assertFalse(r["verificado"], f"rc {rc_fallo} debe fallar cerrado")

    def test_transitoria_no_confunde_una_ip_con_prefijo(self):
        # 192.168.1.10 NO debe casar con 192.168.1.100 presente en el listado (match de palabra completa).
        o = {"accion_id": "MATAR_CONEXION", "nodo_ip": "192.168.1.30", "params": {"ip": "192.168.1.10"}}
        r = verificacion.confirmar(o, CAT, lambda ip, cmd: (0, "tcp ESTAB 0 0 10.10.0.10:22 192.168.1.100:4000"))
        self.assertTrue(r["verificado"])   # solo está la .100, no la .10 -> la .10 se cortó

    def test_params_con_inyeccion_no_ejecuta(self):
        llamado = []
        def ej(ip, cmd): llamado.append(cmd); return (0, "")
        orden_mala = dict(ORDEN); orden_mala["params"] = {"ip": "1.2.3.4; rm -rf /"}
        r = verificacion.confirmar(orden_mala, CAT, ej)
        self.assertFalse(r["verificado"])
        self.assertEqual(llamado, [])   # el ejecutor NUNCA se llamó

    def test_nodo_ip_con_inyeccion_no_ejecuta(self):
        llamado = []
        def ej(ip, cmd): llamado.append(cmd); return (0, "")
        orden_mala = {**ORDEN, "nodo_ip": "192.168.1.30; id"}
        r = verificacion.confirmar(orden_mala, CAT, ej)
        self.assertFalse(r["verificado"])
        self.assertEqual(llamado, [])
