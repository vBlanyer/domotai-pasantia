"""Base de geolocalización mínima para los tests que necesitan un país (TRIAJE_GEOIP)."""
import os
from unittest import mock
from prototipo.motor import geoip

RUTA = os.path.join(os.path.dirname(__file__), "fixtures", "geoip-prueba.csv")
RUTA_ASN = os.path.join(os.path.dirname(__file__), "fixtures", "asn-prueba.csv")


def con_base_geo(test):
    """Activa las bases de prueba durante `test`: países (8.8.8.0/24 = US, 193.0.0.0/21 = NL) y ASN
    (8.8.8.0/24 = AS15169 Google LLC, 1.1.1.0/24 = AS13335 Cloudflare)."""
    parche = mock.patch.dict(os.environ, {"TRIAJE_GEOIP": RUTA, "TRIAJE_ASN": RUTA_ASN})
    parche.start()
    geoip.reiniciar()
    test.addCleanup(geoip.reiniciar)
    test.addCleanup(parche.stop)
