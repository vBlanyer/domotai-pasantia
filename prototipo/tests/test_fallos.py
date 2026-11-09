"""Clasificación de los fallos de contención (fase 1 de PLAN-MANEJO-FALLOS-CONTENCION.md).

Dos garantías: (1) cada salida REAL capturada en el laboratorio cae en su clase, y (2) clasificar no
cambia NADA de lo que el lazo hace: los registros con y sin clasificador son idénticos salvo los campos
de la causa."""
import copy
import json
import os
import unittest
from unittest import mock

from prototipo.accion import conector, fallos
from prototipo.servicio import lazo
from prototipo.tests import test_lazo as tl
from prototipo.tests.test_lazo import CAT, j

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "fallos_conector.json")


def _ej(rc, salida, exito=None):
    return {"exito": rc == 0 if exito is None else exito, "codigo_salida": rc, "salida": salida}


class TestClasificadorSobreSalidasReales(unittest.TestCase):
    def setUp(self):
        with open(FIX, encoding="utf-8") as f:
            self.casos = json.load(f)["casos"]

    def test_cada_salida_capturada_cae_en_su_clase(self):
        for c in self.casos:
            with self.subTest(c["caso"]):
                if c["clase"] == "ok":
                    self.assertIsNone(fallos.clasificar_fallo(_ej(c["rc"], c["salida"]), {"verificado": True}))
                elif c["clase"] == "no_esta":
                    # es la salida de una VERIFICACIÓN (grep sin coincidencias), no de la ejecución: la orden
                    # se ejecutó (rc 0) y la verificación no la encuentra -> F8, nunca configuración
                    r = fallos.clasificar_fallo(_ej(0, ""), {"verificado": False})
                    self.assertEqual(r["clase"], "F8")
                    self.assertTrue(r["posible_ataque"])
                else:
                    self.assertEqual(fallos.clasificar_fallo(_ej(c["rc"], c["salida"]))["clase"], c["clase"])

    def test_la_prueba_de_conectividad_diagnostica_con_los_mismos_patrones(self):
        from prototipo.accion import conectividad as cx
        esperado = {"F2": "sin_fijar", "F3": "host_cambiada", "F4": "sin_clave", "F5": "sin_acceso", "F6": "fallo", "F7": "fallo"}
        for c in self.casos:
            if c["clase"] in esperado:
                with self.subTest(c["caso"]):
                    self.assertEqual(cx.diagnosticar(c["rc"], c["salida"]), esperado[c["clase"]])

    def test_la_evidencia_es_la_linea_que_decide(self):
        r = fallos.clasificar_fallo(_ej(255, "aviso\n\nPermission denied (publickey,password).\n"))
        self.assertEqual(r["evidencia"], "Permission denied (publickey,password).")
        caso = {c["caso"]: c for c in self.casos}
        f3 = fallos.clasificar_fallo(_ej(255, caso["F3_clave_host_cambiada"]["salida"]))
        self.assertIn("REMOTE HOST IDENTIFICATION HAS CHANGED", f3["evidencia"])
        f2 = fallos.clasificar_fallo(_ej(255, caso["F2_sin_aprovisionar"]["salida"]))
        self.assertIn("host key is known", f2["evidencia"])
        self.assertEqual(fallos.clasificar_fallo(_ej(2, "uno\ndos\n"))["evidencia"], "dos")   # sin patrón: la última


class TestReglasDeGravedad(unittest.TestCase):
    NO_CONOCIDA = "No ED25519 host key is known for 10.0.0.9 and you have requested strict checking.\nHost key verification failed."

    def test_un_equipo_con_huella_fijada_que_dice_no_conocida_es_F3(self):
        self.assertEqual(fallos.clasificar_fallo(_ej(255, self.NO_CONOCIDA))["clase"], "F2")
        r = fallos.clasificar_fallo(_ej(255, self.NO_CONOCIDA), contexto={"aprovisionado": True})
        self.assertEqual((r["clase"], r["posible_ataque"]), ("F3", True))

    def test_F4_F5_F6_en_un_equipo_verificado_son_regresion(self):
        for clase, salida, rc in (("F4", "Permission denied (publickey).", 255),
                                  ("F5", "ssh: connect to host x port 22: Connection refused", 255),
                                  ("F6", "sudo: a password is required", 1)):
            with self.subTest(clase):
                normal = fallos.clasificar_fallo(_ej(rc, salida))
                self.assertFalse(normal["regresion"] or normal["posible_ataque"])
                r = fallos.clasificar_fallo(_ej(rc, salida), contexto={"verificado": True})
                self.assertEqual(r["clase"], clase)
                self.assertTrue(r["regresion"] and r["posible_ataque"])
                self.assertIn("posible ataque", r["accion"])

    def test_F6_con_la_regla_que_falta_es_accion_no_ejecutable(self):
        r = fallos.clasificar_fallo(_ej(1, "sudo: a password is required"), contexto={"regla_falta": "ss -K dst 1.2.3.4"})
        self.assertEqual((r["clase"], r["descripcion"]), ("F6", "acción no ejecutable en este equipo"))
        self.assertIn("ss -K dst 1.2.3.4", r["accion"])
        # aun con el equipo verificado: la prueba ya sabía que faltaba, no es una regresión
        r = fallos.clasificar_fallo(_ej(1, "sudo: a password is required"), contexto={"regla_falta": "ss -K dst *", "verificado": True})
        self.assertFalse(r["regresion"] or r["posible_ataque"])

    def test_lo_que_no_se_reconoce_es_F10_o_F7_nunca_configuracion(self):
        self.assertEqual(fallos.clasificar_fallo(_ej(255, "kex_exchange_identification: algo raro"))["clase"], "F10")
        self.assertEqual(fallos.clasificar_fallo(_ej(124, ""))["clase"], "F10")
        self.assertEqual(fallos.clasificar_fallo(_ej(2, "iptables v1.8: unknown option"))["clase"], "F7")

    def test_un_exito_verificado_o_sin_verificar_no_tiene_causa(self):
        self.assertIsNone(fallos.clasificar_fallo(_ej(0, ""), {"verificado": True}))
        self.assertIsNone(fallos.clasificar_fallo(_ej(0, "")))

    def test_rechazo_previo_y_conector_sin_clave(self):
        self.assertEqual(fallos.clasificar_fallo(_ej(-1, "rechazado: ip no válida", False))["clase"], "F1")
        self.assertEqual(fallos.clasificar_fallo(_ej(126, "conector sin configurar: ..."))["clase"], "F9")


class TestContexto(unittest.TestCase):
    def tearDown(self):
        fallos.configurar_contexto(None)
        fallos.configurar_observador(None)

    def test_sin_proveedor_o_si_falla_el_contexto_es_vacio(self):
        self.assertEqual(fallos.contexto("10.0.0.1"), {})
        fallos.configurar_contexto(lambda ip, acc: 1 / 0)
        self.assertEqual(fallos.contexto("10.0.0.1"), {})       # un fallo al consultar nunca rompe la contención


def _sin_causa(r):
    """El registro sin los campos que añade la clasificación."""
    r = copy.deepcopy(r)
    r.pop("causa_fallo", None)
    for p in ((r.get("escalada") or {}).get("pasos") or []):
        p.pop("causa", None)
    return r


class TestNoInterferencia(unittest.TestCase):
    """Con y sin clasificador, el lazo hace exactamente lo mismo: mismas órdenes, misma escalada, mismo
    resultado. Solo cambian los campos de la causa."""
    perfil = tl.TestEscaladaPorDefecto._perfil_con_topologia(None)

    def tearDown(self):
        fallos.configurar_contexto(None)
        fallos.configurar_observador(None)

    def setUp(self):
        reloj = mock.patch.object(conector, "ahora_iso", return_value="2026-11-09T00:00:00.000+00:00")
        reloj.start()
        self.addCleanup(reloj.stop)

    def _ambos(self, ejecutor_fab, alerta=None, ctx=None):
        fallos.configurar_contexto(ctx)
        kw = dict(leer=lambda *_: "s")
        con = lazo.procesar_lazo(alerta or j("alerta_vp.json"), j("hallazgos.json"), self.perfil, "prueba", CAT,
                                 ejecutor_fab(), "d1", "t", **kw)
        with mock.patch.object(fallos, "clasificar_fallo", return_value=None):
            sin = lazo.procesar_lazo(alerta or j("alerta_vp.json"), j("hallazgos.json"), self.perfil, "prueba", CAT,
                                     ejecutor_fab(), "d1", "t", **kw)
        self.assertEqual(_sin_causa(con), _sin_causa(sin))
        self.assertNotIn("causa_fallo", sin)
        return con

    def test_host_caido_que_escala_y_contiene(self):
        r = self._ambos(tl.TestEscaladaPorDefecto.HostCaido)
        self.assertEqual(r["causa_fallo"]["clase"], "F5")
        self.assertEqual(r["escalada"]["resultado"], "mitigado")
        self.assertNotIn("causa", r["escalada"]["pasos"][-1])           # el salto que contuvo no tiene causa

    def test_todo_caido_la_escalada_falla_igual(self):
        r = self._ambos(lambda: (lambda ip, c: (255, "ssh: connect to host x port 22: No route to host")))
        self.assertEqual(r["escalada"]["resultado"], "fallido")
        acciones = [p for p in r["escalada"]["pasos"] if p["tipo"] == "accion"]
        self.assertTrue(acciones and all(p["causa"]["clase"] == "F5" for p in acciones))

    def test_contramedida_aplicada_pero_no_verificada_es_F8(self):
        # se ejecuta sin error pero la verificación nunca la encuentra (alguien la deshace en el acto)
        r = self._ambos(lambda: (lambda ip, c: (1, "") if "grep" in c else (0, "")))
        self.assertEqual((r["causa_fallo"]["clase"], r["causa_fallo"]["posible_ataque"]), ("F8", True))
        # el conector re-verifica tras ejecutar: el salto ya sale como fallido con rc 0 -> F8 en la acción
        acciones = [p for p in r["escalada"]["pasos"] if p["tipo"] == "accion"]
        self.assertTrue(acciones and all(p["causa"]["clase"] == "F8" for p in acciones))
        self.assertEqual(r["escalada"]["resultado"], "fallido")

    def test_regresion_con_el_contexto_de_la_consola(self):
        r = self._ambos(tl.TestEscaladaPorDefecto.HostCaido, ctx=lambda ip, acc: {"verificado": ip == "192.168.1.30"})
        self.assertTrue(r["causa_fallo"]["regresion"])

    def test_el_observador_recibe_cada_resultado_y_si_falla_no_cambia_nada(self):
        vistos = []
        fallos.configurar_observador(lambda ip, causa: vistos.append((ip, causa and causa["clase"])))
        self._ambos(tl.TestEscaladaPorDefecto.HostCaido)
        self.assertIn(("192.168.1.30", "F5"), vistos)        # el activo cayó
        self.assertIn(("192.168.1.1", None), vistos)         # el cortafuegos contuvo: limpia su aviso
        fallos.configurar_observador(lambda ip, causa: 1 / 0)
        r = self._ambos(tl.TestEscaladaPorDefecto.HostCaido)
        self.assertEqual(r["escalada"]["resultado"], "mitigado")

    def test_una_contencion_correcta_no_cambia_su_registro(self):
        r = self._ambos(_EjecutorBien)
        self.assertNotIn("causa_fallo", r)


class _EjecutorBien:
    def __init__(self): self.aplicado = set()
    def __call__(self, ip, c):
        if "grep" in c:
            return (0, "DROP") if ip in self.aplicado else (1, "")
        self.aplicado.add(ip); return (0, "")


if __name__ == "__main__":
    unittest.main()


class TestPresentacion(unittest.TestCase):
    """Fase 2: un mensaje por clase en la consola; F3 y F8 nunca con texto de configuración."""
    CONFIGURACION = ("Conectividad", "dalo de alta", "paquete de alta", "genera la clave", "revisa el papel")
    SALIDAS = {"F1": (-1, "nodo_ip rechazado: no es una IP valida"), "F2": (255, TestReglasDeGravedad.NO_CONOCIDA),
               "F3": (255, "@@@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! @@@\nHost key verification failed."),
               "F4": (255, "triaje@x: Permission denied (publickey)."), "F5": (255, "ssh: connect to host x port 22: Connection refused"),
               "F6": (1, "sudo: a password is required"), "F7": (1, "iptables: Bad rule"), "F8": (0, ""),
               "F9": (126, "conector sin configurar: ..."), "F10": (255, "kex_exchange_identification: raro")}

    def _reg(self, clase):
        from prototipo.servicio import stream
        rc, salida = self.SALIDAS[clase]
        causa = fallos.clasificar_fallo(_ej(rc, salida, exito=False), {"verificado": False})
        self.assertEqual(causa["clase"], clase)
        d = {"id_decision": "s1", "orden": {"accion_id": "BLOQUEAR_IP", "nodo_objetivo": "atm", "nodo_ip": "10.0.0.9"},
             "ejecucion": {"exito": False, "codigo_salida": rc, "salida": salida, "comando_ejecutado": "iptables -A INPUT -s 1.2.3.4 -j DROP"},
             "verificacion": {"verificado": False}, "causa_fallo": causa}
        return d, stream._lineas_ejecucion(d)

    def test_un_mensaje_por_clase(self):
        for clase in fallos.CLASES:
            with self.subTest(clase):
                _, lineas = self._reg(clase)
                texto = "\n".join(lineas)
                self.assertIn(fallos.CLASES[clase][0], texto)
                self.assertNotIn("None", texto)
                if clase in ("F7", "F8"):
                    self.assertIn("✗ s1 NO verificada en atm", texto)
                else:
                    self.assertIn("✗ s1 no se ejecutó en atm", texto)
                    self.assertNotIn("NO verificada", texto)

    def test_F3_y_F8_son_posible_ataque_y_nunca_configuracion(self):
        for clase in ("F3", "F8"):
            with self.subTest(clase):
                _, lineas = self._reg(clase)
                texto = "\n".join(lineas)
                self.assertIn("POSIBLE ATAQUE", texto)
                for palabra in self.CONFIGURACION:
                    self.assertNotIn(palabra, texto)

    def test_la_regresion_tampoco_lleva_texto_de_configuracion(self):
        for salida, rc in (("Permission denied (publickey).", 255), ("Connection refused", 255), ("sudo: a password is required", 1)):
            c = fallos.clasificar_fallo(_ej(rc, salida), contexto={"verificado": True})
            t = fallos.texto(c, "web-banking")
            self.assertTrue(t.startswith("POSIBLE ATAQUE · web-banking: "))
            for palabra in self.CONFIGURACION:
                self.assertNotIn(palabra, t)

    def test_escalada_fallida_dice_donde_y_por_que(self):
        from prototipo.servicio import stream
        f2 = fallos.clasificar_fallo(_ej(255, TestReglasDeGravedad.NO_CONOCIDA))
        f3 = fallos.clasificar_fallo(_ej(255, self.SALIDAS["F3"][1]))
        esc = {"resultado": "fallido", "dispositivo_ejecutor": None, "orden_efectiva": None,
               "pasos": [{"tipo": "accion", "dispositivo": "fw-core", "observacion": "Error", "causa": f2},
                         {"tipo": "accion", "dispositivo": "fw-edge", "observacion": "Error", "causa": f3}]}
        lineas = stream._lineas_escalada("s1", esc)
        self.assertEqual(lineas[0], "⇪ s1 escalada fallida: fw-core (equipo sin aprovisionar); fw-edge (la clave del host cambió)")
        self.assertTrue(lineas[1].startswith("⇪ s1 POSIBLE ATAQUE · fw-edge: la clave del host cambió"))
        self.assertEqual(stream._lineas_escalada("s1", {"resultado": "fallido", "pasos": []}),
                         ["⇪ s1 escalada fallida: no había más equipos a los que subir"])
        self.assertFalse(any("None" in l for l in lineas))

    def test_el_resumen_de_la_decision_lleva_primero_lo_que_puede_ser_ataque(self):
        from prototipo.servicio import tablero
        f2 = fallos.clasificar_fallo(_ej(255, TestReglasDeGravedad.NO_CONOCIDA))
        f8 = fallos.clasificar_fallo(_ej(0, ""), {"verificado": False})
        reg = {"orden": {"nodo_objetivo": "atm"}, "causa_fallo": f2,
               "escalada": {"pasos": [{"tipo": "verificacion", "dispositivo": "fw-core", "causa": f8}]}}
        c = tablero.causa_de(reg)
        self.assertEqual((c["clase"], c["dispositivo"]), ("F8", "fw-core"))
        self.assertEqual(tablero.causa_de({**reg, "escalada": None})["dispositivo"], "atm")
        self.assertIsNone(tablero.causa_de({"orden": {"nodo_objetivo": "atm"}}))


class _Contador:
    """Ejecutor de prueba: el activo (192.168.1.30) responde según `activo(cmd)`; el resto contiene bien.
    Anota cada llamada para comparar la secuencia con y sin interruptores."""
    def __init__(self, activo):
        self.activo, self.llamadas, self.aplicado = activo, [], set()

    def __call__(self, ip, cmd):
        self.llamadas.append((ip, cmd))
        if ip == "192.168.1.30":
            return self.activo(cmd)
        if "grep" in cmd:
            return (0, "DROP") if ip in self.aplicado else (1, "")
        self.aplicado.add(ip)
        return (0, "")


_F3 = "@@@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! @@@\nHost key verification failed."
ACTIVOS = {
    "F3": lambda c: (255, _F3),
    "F5": lambda c: (255, "ssh: connect to host 192.168.1.30 port 22: Connection refused"),
    "F6": lambda c: (1, "sudo: a password is required"),
    "F7": lambda c: (1, "") if "grep" in c else (1, "iptables: Bad rule (does a matching rule exist in that chain?)."),
    "F8": lambda c: (1, "") if "grep" in c else (0, ""),
}
INTERRUPTORES = {"TRIAJE_FALLO_RAPIDO": "1", "TRIAJE_PRECHECK_APROVISIONADO": "1", "TRIAJE_ESCALADA_SOLO_APROVISIONADOS": "1"}


class TestInterruptores(unittest.TestCase):
    """Fase 4: los recortes no cambian qué se contiene; solo ahorran conexiones que no podían servir."""
    perfil = tl.TestEscaladaPorDefecto._perfil_con_topologia(None)

    def setUp(self):
        reloj = mock.patch.object(conector, "ahora_iso", return_value="2026-11-09T00:00:00.000+00:00")
        reloj.start()
        self.addCleanup(reloj.stop)
        self.addCleanup(fallos.configurar_contexto, None)

    def _correr(self, activo, entorno, ctx=lambda ip, acc: {"aprovisionado": True}):
        from prototipo.servicio import tablero
        fallos.configurar_contexto(ctx)
        ej = _Contador(activo)
        with mock.patch.dict(os.environ, entorno):
            r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), self.perfil, "prueba", CAT, ej, "d1", "t",
                                   leer=lambda *_: "s")
        return r, ej.llamadas, tablero.contencion_de(r)

    def test_apagados_por_defecto(self):
        for k in INTERRUPTORES:
            self.assertFalse(fallos.interruptor(k))

    def test_las_mismas_contenciones_con_y_sin_interruptores(self):
        for clase, activo in ACTIVOS.items():
            with self.subTest(clase):
                r0, ll0, c0 = self._correr(activo, {})
                r1, ll1, c1 = self._correr(activo, INTERRUPTORES)
                self.assertEqual(c0, c1)                                    # mismo desenlace y dónde
                self.assertEqual(r0["causa_fallo"]["clase"], r1["causa_fallo"]["clase"])
                self.assertEqual(r0["causa_fallo"]["posible_ataque"], r1["causa_fallo"]["posible_ataque"])
                self.assertEqual(r0["escalada"]["resultado"], r1["escalada"]["resultado"])
                self.assertLessEqual(len(ll1), len(ll0))

    def test_F6_F7_F8_exactamente_igual_llamada_a_llamada(self):
        for clase in ("F6", "F7", "F8"):
            with self.subTest(clase):
                r0, ll0, _ = self._correr(ACTIVOS[clase], {})
                r1, ll1, _ = self._correr(ACTIVOS[clase], INTERRUPTORES)
                self.assertEqual(ll0, ll1)
                self.assertEqual(_sin_causa(r0), _sin_causa(r1))

    def test_fallo_rapido_ahorra_las_conexiones_que_no_entran(self):
        for clase in ("F3", "F5"):
            with self.subTest(clase):
                _, ll0, _ = self._correr(ACTIVOS[clase], {})
                r1, ll1, _ = self._correr(ACTIVOS[clase], {"TRIAJE_FALLO_RAPIDO": "1"})
                al_activo = lambda ll: [c for ip, c in ll if ip == "192.168.1.30"]
                self.assertEqual(len(al_activo(ll0)), 4)                     # pre-check, ejecutar, re-verificar, confirmar...
                self.assertEqual(len(al_activo(ll1)), 1)                     # ...frente a una sola
                self.assertTrue(r1["ejecucion"]["sin_entrar"])
                self.assertEqual(r1["escalada"]["resultado"], "mitigado")    # la escalada sigue igual

    def test_precheck_no_intenta_lo_que_la_consola_sabe_sin_aprovisionar(self):
        sin = lambda ip, acc: {"aprovisionado": ip != "192.168.1.30"}
        r, ll, c = self._correr(ACTIVOS["F5"], {"TRIAJE_PRECHECK_APROVISIONADO": "1"}, ctx=sin)
        self.assertFalse([1 for ip, _ in ll if ip == "192.168.1.30"])        # ni una conexión al activo
        self.assertEqual((r["causa_fallo"]["clase"], r["ejecucion"]["omitido"]), ("F2", "sin_aprovisionar"))
        self.assertEqual(c, ("contenida", "gateway"))                        # escaló y contuvo
        # sin saberlo (consola sin datos) se intenta como siempre: solo F2 sabido de antemano
        _, ll, _ = self._correr(ACTIVOS["F5"], {"TRIAJE_PRECHECK_APROVISIONADO": "1"}, ctx=lambda ip, acc: {})
        self.assertTrue([1 for ip, _ in ll if ip == "192.168.1.30"])

    def test_escalada_salta_destinos_sin_aprovisionar_y_no_cierra_en_silencio(self):
        from prototipo.servicio import stream
        sin_gw = lambda ip, acc: {"aprovisionado": ip != "192.168.1.1"}
        r, ll, c = self._correr(ACTIVOS["F5"], {"TRIAJE_ESCALADA_SOLO_APROVISIONADOS": "1"}, ctx=sin_gw)
        self.assertFalse([1 for ip, _ in ll if ip == "192.168.1.1"])         # no se intentó el cortafuegos
        self.assertEqual(c, ("fallida", None))                               # sin destinos: fallida, al analista
        paso = r["escalada"]["pasos"][0]
        self.assertEqual((paso["tipo"], paso["causa"]["clase"]), ("omitido", "F2"))
        self.assertIn("salto omitido: gateway sin aprovisionar", paso["observacion"])
        self.assertIn("gateway (equipo sin aprovisionar)", stream._lineas_escalada("d1", r["escalada"])[0])

    def test_fallo_rapido_en_una_accion_transitoria(self):
        # MATAR_CONEXION no tiene pre-check: la primera llamada ya es la acción; si no entra, no se re-verifica
        orden = {"decision_id": "d", "accion_id": "MATAR_CONEXION", "nodo_objetivo": "x", "nodo_ip": "192.168.1.30",
                 "params": {"ip": "203.0.113.9"}}
        for entorno, n in (({}, 2), ({"TRIAJE_FALLO_RAPIDO": "1"}, 1)):
            ej = _Contador(ACTIVOS["F5"])
            with mock.patch.dict(os.environ, entorno):
                r = conector.ejecutar_orden(orden, CAT, ej, "t")
            self.assertEqual((len(ej.llamadas), r["exito"]), (n, False))
        ej = _Contador(ACTIVOS["F6"])                     # sudo deniega: SÍ entró, sigue la secuencia completa
        with mock.patch.dict(os.environ, {"TRIAJE_FALLO_RAPIDO": "1"}):
            conector.ejecutar_orden(orden, CAT, ej, "t")
        self.assertEqual(len(ej.llamadas), 2)

    def test_la_consola_no_imprime_None_sin_comando(self):
        from prototipo.servicio import stream
        r, _, _ = self._correr(ACTIVOS["F5"], {"TRIAJE_FALLO_RAPIDO": "1"})
        lineas = stream._lineas_ejecucion(r)
        self.assertTrue(lineas[0].endswith(": no se llegó a entrar en el equipo"), lineas[0])
        self.assertFalse(any("None" in l for l in lineas), lineas)


class TestAccionNoEjecutable(unittest.TestCase):
    """Fase 6: con una prueba vigente de < 24 h que dice que falta la regla de la acción, no se intenta;
    se escala (sobre el origen) o queda fallida con el motivo. El motor no cambia."""
    perfil = tl.TestEscaladaPorDefecto._perfil_con_topologia(None)

    def setUp(self):
        reloj = mock.patch.object(conector, "ahora_iso", return_value="2026-11-09T00:00:00.000+00:00")
        reloj.start()
        self.addCleanup(reloj.stop)
        self.addCleanup(fallos.configurar_contexto, None)

    @staticmethod
    def _hace(h):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat(timespec="milliseconds")

    def test_solo_con_una_prueba_reciente(self):
        self.assertEqual(fallos.regla_que_falta({"regla_falta": "ss -K dst *", "prueba_en": self._hace(1)}), "ss -K dst *")
        self.assertIsNone(fallos.regla_que_falta({"regla_falta": "ss -K dst *", "prueba_en": self._hace(25)}))
        self.assertIsNone(fallos.regla_que_falta({"regla_falta": "ss -K dst *"}))
        self.assertIsNone(fallos.regla_que_falta({"prueba_en": self._hace(1)}))

    def _cortar(self, prueba_en, entorno):
        fallos.configurar_contexto(lambda ip, acc: {"aprovisionado": True, "verificado": True, "prueba_en": prueba_en,
                                                    **({"regla_falta": "ss -K dst *"} if ip == "192.168.1.30" else {})})
        a = {**j("alerta_vp.json"), "familia": "acceso_consumado"}
        ej = _Contador(ACTIVOS["F6"])          # en el equipo, sudo deniega `ss` (binario ausente)
        with mock.patch.dict(os.environ, entorno):
            r = lazo.procesar_lazo(a, j("hallazgos.json"), self.perfil, "prueba", CAT, ej, "d1", "t", leer=lambda *_: "s")
        return r, [ip for ip, _ in ej.llamadas]

    def test_cortar_conexion_sin_ss_escala_directo(self):
        from prototipo.servicio import tablero
        r0, ips0 = self._cortar(self._hace(1), {})
        r1, ips1 = self._cortar(self._hace(1), {"TRIAJE_ACCION_NO_EJECUTABLE": "1"})
        self.assertIn("192.168.1.30", ips0)                     # hoy: se intenta y sudo pide contraseña
        self.assertNotIn("192.168.1.30", ips1)                  # ahora: ni se intenta
        self.assertEqual(r1["orden"]["accion_id"], "MATAR_CONEXION")
        self.assertEqual(r1["ejecucion"]["omitido"], "no_ejecutable")
        c = r1["causa_fallo"]
        self.assertEqual((c["clase"], c["descripcion"]), ("F6", "acción no ejecutable en este equipo"))
        self.assertIn("ss -K dst *", c["accion"])
        self.assertFalse(c["regresion"] or c["posible_ataque"])  # la prueba ya lo sabía: deriva, no regresión
        self.assertEqual(tablero.contencion_de(r1), ("contenida", "gateway"))
        self.assertEqual(tablero.contencion_de(r0), tablero.contencion_de(r1))   # se contiene igual (escalada)
        motor = ("clase", "accion_propuesta", "accion_final", "resultado_filtro", "requiere_humano", "confianza", "prioridad")
        self.assertEqual({k: r0.get(k) for k in motor}, {k: r1.get(k) for k in motor})   # el motor no cambia

    def test_con_una_prueba_vieja_se_intenta_como_siempre(self):
        _, ips = self._cortar(self._hace(30), {"TRIAJE_ACCION_NO_EJECUTABLE": "1"})
        self.assertIn("192.168.1.30", ips)
