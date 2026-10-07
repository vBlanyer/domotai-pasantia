import unittest

from prototipo import contenciones

# Catálogo mínimo: contenciones con estado (reversibles) y una transitoria (no deja estado).
CAT = {
    "BLOQUEAR_IP": {"reversion": "definida", "reversion_cmd": "iptables -D INPUT -s {ip} -j DROP"},
    "BLOQUEAR_IP_FIREWALL": {"reversion": "definida", "reversion_cmd": "iptables -D FORWARD -s {ip} -j DROP"},
    "FORZAR_CAMBIO_PASS": {"reversion": "definida", "reversion_cmd": "passwd -u {usuario}"},
    "CERRAR_SERVICIO": {"reversion": "definida", "reversion_cmd": "service {servicio} start"},
    "MATAR_CONEXION": {"reversion": "transitoria", "reversion_cmd": "x"},
    "OBS_CONEXIONES": {"reversion": "no_aplica"},
}


def _accion(id_decision, accion, params, activo="api-movil", exito=True, verificado=True):
    return {
        "tipo": "decision", "id_decision": id_decision, "activo": activo, "accion_final": accion,
        "orden": {"accion_id": accion, "nodo_objetivo": activo, "params": params},
        "ejecucion": {"accion_id": accion, "nodo": activo, "exito": exito},
        "verificacion": {"verificado": verificado},
        "contexto": {"origen_ip": params.get("ip"), "familia": "x"}, "timestamp": "2026-10-07T10:00:00Z",
    }


def _bloqueo(id_decision, ip, activo, nodo="api-movil", accion="BLOQUEAR_IP", exito=True, verificado=True):
    return {
        "tipo": "decision", "id_decision": id_decision, "activo": activo,
        "accion_final": accion, "veredicto_humano": None,
        "orden": {"accion_id": accion, "nodo_objetivo": nodo, "params": {"ip": ip}},
        "ejecucion": {"accion_id": accion, "nodo": nodo, "exito": exito},
        "verificacion": {"verificado": verificado},
        "contexto": {"origen_ip": ip, "familia": "acceso_credenciales"},
        "timestamp": "2026-10-07T10:00:00Z",
    }


class TestContencionesActivas(unittest.TestCase):
    def test_bloqueo_verificado_sale_como_activa(self):
        act = contenciones.activas([_bloqueo("s1", "198.51.100.10", "api-movil")], CAT)
        self.assertEqual(len(act), 1)
        self.assertEqual(act[0]["ip"], "198.51.100.10")
        self.assertEqual(act[0]["activo"], "api-movil")
        self.assertEqual(act[0]["accion_id"], "BLOQUEAR_IP")
        self.assertEqual(act[0]["nodo"], "api-movil")
        self.assertEqual(act[0]["id_decision"], "s1")

    def test_revertida_no_sale(self):
        regs = [
            _bloqueo("s1", "198.51.100.10", "api-movil"),
            {"tipo": "reversion", "id_decision_revertida": "s1", "exito": True},
        ]
        self.assertEqual(contenciones.activas(regs, CAT), [])

    def test_ejecucion_fallida_o_no_verificada_no_sale(self):
        regs = [
            _bloqueo("s1", "198.51.100.10", "a", exito=False),
            _bloqueo("s2", "198.51.100.11", "b", verificado=False),
        ]
        self.assertEqual(contenciones.activas(regs, CAT), [])

    def test_accion_transitoria_no_deja_estado(self):
        # MATAR_CONEXION no es reversible-con-estado: no se lista como contención activa.
        regs = [_bloqueo("s1", "198.51.100.10", "a", accion="MATAR_CONEXION")]
        self.assertEqual(contenciones.activas(regs, CAT), [])

    def test_escalada_perimetral_cuenta_en_el_firewall(self):
        # El paso en el activo falló y la escalada contuvo en el cortafuegos (orden_efectiva).
        reg = _bloqueo("s1", "198.51.100.10", "core-db", exito=False, verificado=False)
        reg["escalada"] = {
            "resultado": "mitigado", "dispositivo_ejecutor": "fw-core",
            "orden_efectiva": {"accion_id": "BLOQUEAR_IP_FIREWALL", "nodo_objetivo": "fw-core",
                               "params": {"ip": "198.51.100.10"}},
        }
        act = contenciones.activas([reg], CAT)
        self.assertEqual(len(act), 1)
        self.assertEqual(act[0]["accion_id"], "BLOQUEAR_IP_FIREWALL")
        self.assertEqual(act[0]["nodo"], "fw-core")

    def test_dedup_por_ip_nodo_accion_conserva_la_ultima(self):
        regs = [
            _bloqueo("s1", "198.51.100.10", "api-movil"),
            _bloqueo("s7", "198.51.100.10", "api-movil"),   # mismo (ip,nodo,accion): un re-bloqueo
        ]
        act = contenciones.activas(regs, CAT)
        self.assertEqual(len(act), 1)
        self.assertEqual(act[0]["id_decision"], "s7")

    def test_revertida_por_indice_en_traza_multisesion(self):
        # Dos sesiones reutilizan el mismo fichero (--salida estable): el id "s1" se repite. La
        # reversión apunta por indice_revertido al s1 de la 2ª sesión; el de la 1ª sigue activo.
        regs = [
            _bloqueo("s1", "198.51.100.10", "api-movil"),                         # índice 0: vive
            _bloqueo("s1", "203.0.113.9", "core-db", nodo="core-db"),             # índice 1: revertido
            {"tipo": "reversion", "id_decision_revertida": "s1", "indice_revertido": 1, "exito": True},
        ]
        act = contenciones.activas(regs, CAT)
        self.assertEqual([a["ip"] for a in act], ["198.51.100.10"])

    def test_contencion_sobre_cuenta_no_se_colapsa_y_expone_el_usuario(self):
        # Familia abuso_de_cuenta: FORZAR_CAMBIO_PASS sobre dos usuarios en el mismo nodo (ip None).
        act = contenciones.activas([
            _accion("s1", "FORZAR_CAMBIO_PASS", {"usuario": "admin"}),
            _accion("s2", "FORZAR_CAMBIO_PASS", {"usuario": "operador"}),
        ], CAT)
        self.assertEqual(len(act), 2)                                  # no se colapsan por (None,nodo,accion)
        self.assertEqual(sorted(a["objetivo"] for a in act), ["admin", "operador"])
        self.assertEqual(sorted(a["usuario"] for a in act), ["admin", "operador"])

    def test_contencion_sobre_servicio_usa_el_servicio_como_objetivo(self):
        act = contenciones.activas([
            _accion("s1", "CERRAR_SERVICIO", {"servicio": "telnet"}),
            _accion("s2", "CERRAR_SERVICIO", {"servicio": "ftp"}),
        ], CAT)
        self.assertEqual(sorted(a["objetivo"] for a in act), ["ftp", "telnet"])

    def test_registros_no_decision_se_ignoran(self):
        regs = [
            {"tipo": "actividad_propia", "id_decision": "x"},
            {"tipo": "actividad_suprimida", "id_decision": "y"},
            _bloqueo("s1", "198.51.100.10", "a"),
        ]
        self.assertEqual(len(contenciones.activas(regs, CAT)), 1)


if __name__ == "__main__":
    unittest.main()
