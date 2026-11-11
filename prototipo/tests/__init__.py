import os

# Aislamiento de las pruebas. En el producto, los recortes validados del plan de fallos van ENCENDIDOS
# por defecto (`fallos.VALIDADOS`), pero la memoria de fallos guarda estado en el proceso y el fallo
# rápido cambia el número de llamadas al ejecutor: encendidos de fondo, una prueba contaminaría a la
# siguiente. Aquí parten apagados; las pruebas que los ejercitan los encienden con "1" de forma
# explícita, y `test_fallos.TestInterruptores.test_validados_encendidos_por_defecto` cubre el valor
# por defecto real.
for _v in ("TRIAJE_FALLO_RAPIDO", "TRIAJE_PRECHECK_APROVISIONADO", "TRIAJE_ESCALADA_SOLO_APROVISIONADOS",
           "TRIAJE_MEMORIA_FALLOS", "TRIAJE_ACCION_NO_EJECUTABLE"):
    os.environ.setdefault(_v, "0")
