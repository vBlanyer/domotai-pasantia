"""Memoria de fallos por equipo (fase 5 de documentacion/05-fase5-implementacion-del-prototipo/plan-manejo-fallos-contencion.md): solo acelera y sube la
alerta; nunca calla nada. Solo F4/F5; F3, F6, F7 y F8 jamás la abren."""
import os
import unittest
from unittest import mock

from prototipo.accion import conector, fallos, memoria_fallos as mem
from prototipo.servicio import lazo, stream, tablero
from prototipo.tests import test_lazo as tl
from prototipo.tests.test_fallos import ACTIVOS, _Contador
from prototipo.tests.test_lazo import CAT, j

F5 = {"clase": "F5", "regresion": False}


class TestReglas(unittest.TestCase):
    def setUp(self):
        mem.reiniciar()
        self.avisos = []
        mem.configurar_aviso(self.avisos.append)
        self.addCleanup(mem.configurar_aviso, None)
        self.addCleanup(mem.reiniciar)

    def test_se_abre_con_3_fallos_seguidos_en_5_minutos(self):
        mem.registrar("10.0.0.9", F5, ahora=0)
        mem.registrar("10.0.0.9", F5, ahora=10)
        self.assertIsNone(mem.abierta("10.0.0.9"))
        mem.registrar("10.0.0.9", F5, ahora=20)
        self.assertEqual(mem.abierta("10.0.0.9")["clase"], "F5")
        self.assertEqual(len(self.avisos), 1)
        self.assertIn("el MDR no tiene acceso a 10.0.0.9 desde las", self.avisos[0])
        mem.registrar("10.0.0.9", F5, ahora=30)                       # se actualiza, no se repite
        self.assertEqual((len(self.avisos), mem.abierta("10.0.0.9")["fallos"]), (1, 4))

    def test_fuera_de_la_ventana_o_con_otra_clase_en_medio_no_se_abre(self):
        for t in (0, 200, 400):                                       # el primero ya caducó al tercero
            mem.registrar("a", F5, ahora=t)
        self.assertIsNone(mem.abierta("a"))
        for c in (F5, F5, {"clase": "F6"}, F5):                       # F6 corta la racha
            mem.registrar("b", c, ahora=1)
        self.assertIsNone(mem.abierta("b"))
        mem.registrar("c", F5, ahora=1); mem.registrar("c", F5, ahora=2); mem.registrar("c", None, ahora=3)
        mem.registrar("c", F5, ahora=4)
        self.assertIsNone(mem.abierta("c"))                           # un éxito también

    def test_F3_F6_F7_F8_nunca_la_abren(self):
        for clase in ("F3", "F6", "F7", "F8", "F2", "F10"):
            for t in range(6):
                mem.registrar(clase, {"clase": clase, "posible_ataque": True}, ahora=t)
            self.assertIsNone(mem.abierta(clase), clase)

    def test_se_cierra_con_un_exito_o_con_el_sondeo(self):
        for t in range(3):
            mem.registrar("x", {"clase": "F4"}, ahora=t)
        self.assertEqual(mem.por_sondear(ahora=30), [])
        self.assertEqual(mem.por_sondear(ahora=62), ["x"])
        mem.sondeo("x", False, ahora=62)
        self.assertEqual(mem.por_sondear(ahora=100), [])              # se reprueba cada 60 s
        self.assertIsNotNone(mem.abierta("x")["ultimo_sondeo"])
        mem.sondeo("x", True, ahora=130)
        self.assertIsNone(mem.abierta("x"))
        self.assertIn("recupera el acceso a x", self.avisos[-1])
        for t in range(3):
            mem.registrar("y", F5, ahora=t)
        mem.registrar("y", None, ahora=5)
        self.assertIsNone(mem.abierta("y"))


class TestEnElLazo(unittest.TestCase):
    perfil = tl.TestEscaladaPorDefecto._perfil_con_topologia(None)

    def setUp(self):
        mem.reiniciar()
        self.addCleanup(mem.reiniciar)
        self.addCleanup(fallos.configurar_contexto, None)
        reloj = mock.patch.object(conector, "ahora_iso", return_value="2026-11-09T00:00:00.000+00:00")
        reloj.start()
        self.addCleanup(reloj.stop)

    def _serie(self, activo, n, entorno, ctx=None):
        fallos.configurar_contexto(ctx)
        out = []
        with mock.patch.dict(os.environ, entorno):
            for _ in range(n):
                ej = _Contador(activo)
                r = lazo.procesar_lazo(j("alerta_vp.json"), j("hallazgos.json"), self.perfil, "prueba", CAT, ej, "d1", "t",
                                       leer=lambda *_: "s")
                out.append((r, [ip for ip, _ in ej.llamadas], tablero.contencion_de(r)))
        return out

    def test_caso_E1_tras_3_fallos_escala_directo(self):
        serie = self._serie(ACTIVOS["F5"], 5, {"TRIAJE_MEMORIA_FALLOS": "1"})
        for r, ips, c in serie[:3]:                                   # las tres primeras, como hoy
            self.assertIn("192.168.1.30", ips)
            self.assertEqual(c, ("contenida", "gateway"))
        for r, ips, c in serie[3:]:                                   # luego, ni se intenta en el activo
            self.assertNotIn("192.168.1.30", ips)
            self.assertEqual(c, ("contenida", "gateway"))             # y se contiene igual
            self.assertEqual((r["ejecucion"]["omitido"], r["causa_fallo"]["clase"]), ("sin_acceso", "F5"))
        self.assertEqual(mem.abierta("192.168.1.30")["fallos"], 5)
        apagado = self._serie(ACTIVOS["F5"], 5, {})
        self.assertTrue(all("192.168.1.30" in ips for _, ips, _ in apagado))   # sin el interruptor, como hoy

    def test_en_un_equipo_verificado_sigue_siendo_posible_ataque(self):
        serie = self._serie(ACTIVOS["F5"], 4, {"TRIAJE_MEMORIA_FALLOS": "1"}, ctx=lambda ip, acc: {"verificado": True, "aprovisionado": True})
        c = serie[-1][0]["causa_fallo"]
        self.assertEqual((c["clase"], c["regresion"], c["posible_ataque"]), ("F5", True, True))

    def test_F3_con_la_memoria_activa_se_sigue_intentando_y_avisando(self):
        serie = self._serie(ACTIVOS["F3"], 5, {"TRIAJE_MEMORIA_FALLOS": "1"})
        for r, ips, _ in serie:
            self.assertIn("192.168.1.30", ips)
            self.assertEqual((r["causa_fallo"]["clase"], r["causa_fallo"]["posible_ataque"]), ("F3", True))
        self.assertIsNone(mem.abierta("192.168.1.30"))


class TestSondeo(unittest.TestCase):
    def setUp(self):
        mem.reiniciar()
        self.addCleanup(mem.reiniciar)
        for t in range(3):
            mem.registrar("10.0.0.9", F5, ahora=t)

    def test_cierra_al_primer_acceso_y_si_no_lo_anota(self):
        stream.un_sondeo_memoria(None, lambda ip: (255, "ssh: connect to host x port 22: Connection refused"), ahora=70)
        self.assertIsNotNone(mem.abierta("10.0.0.9"))
        stream.un_sondeo_memoria(None, lambda ip: (0, ""), ahora=140)
        self.assertIsNone(mem.abierta("10.0.0.9"))

    def test_sin_consola_usa_el_listado_de_las_verificaciones(self):
        vistos = []
        stream.un_sondeo_memoria(lambda ip, cmd: (vistos.append((ip, cmd)), (0, "Chain INPUT"))[1], None, ahora=70)
        self.assertEqual(vistos, [("10.0.0.9", "iptables -L -n")])
        self.assertIsNone(mem.abierta("10.0.0.9"))

    def test_un_error_del_sondeo_no_la_cierra_ni_rompe(self):
        stream.un_sondeo_memoria(None, lambda ip: 1 / 0, ahora=70)
        self.assertIsNotNone(mem.abierta("10.0.0.9"))


if __name__ == "__main__":
    unittest.main()
