"""Demo de GEOLOCALIZACIÓN observable (sin contenedores).

Genera una campaña SINTÉTICA de ataques con IPs de origen PÚBLICAS repartidas por varios países
—tomadas de la MISMA tabla de muestra que usa el enriquecimiento (`prototipo/corpus/geoip-muestra.json`)—
y las inyecta por el PIPELINE REAL (normalizador Wazuh → motor → traza → visor), de modo que la vista
«Ubicaciones» del tablero se encienda con marcadores por país y cada decisión muestre país + ASN + rDNS.

Honesto a propósito: en el laboratorio real los ataques vienen de IPs del propio lab (10.x) y de
documentación (198.51.100.x) que —por diseño— NO geolocalizan; esta demo SIMULA el caso de producción
en que sí. Es un escenario claramente etiquetado («[DEMO SINTÉTICA]» en el evento crudo), aparte del
corpus de evaluación, y NO toca el motor ni las cifras canónicas.
"""
