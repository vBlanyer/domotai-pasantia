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
