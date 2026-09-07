"""Traducción de una alerta cruda de Wazuh al esquema normalizado del proyecto.

El mapeo se movió al módulo de producto `prototipo/adaptador_wazuh.py` (RF-01 a nivel de producto).
Este fichero re-exporta esas funciones para no romper el pipeline del dataset ni sus consumidores.
"""
from prototipo.adaptador_wazuh import (  # noqa: F401  (re-exportación intencional)
    FUENTE, resolver_activo, servicio_de, familia_de, normalizar_alerta,
)
