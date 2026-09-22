# Banco de pruebas del laboratorio del banco — 2026-09-22 14:28

**21 OK** de 21 casos. Catálogo: `docs/superpowers/specs/2026-09-21-laboratorio-banco-design.md` §4.

| Caso | Nivel | Resultado | Tiempo | Qué se comprobó / qué falló |
|---|---|---|---|---|
| CASCADA | vivo | OK | 15 s | Tumbar core-db (sin el prototipo): cascada real del laboratorio |
| D1 | vivo | OK | 33 s | Atacante externo contra web-banking: bloqueo automatico |
| A1 | vivo | OK | 32 s | Equipo interno (taquilla) contra web-banking: retenida, el analista rechaza |
| K1 | vivo | OK | 45 s | middleware comprometido contra core-db: aprobado; cascada no avisada (fallo conocido K1) |
| E1 | vivo | OK | 56 s | La victima no responde al MDR: escalada a fw-core, aprobada |
| D2 | decision | OK | 0.0 s | Servicio no expuesto según el auditor -> FP exposición inexistente |
| D3 | decision | OK | 0.0 s | Origen legítimo (gestión) -> FP actividad legítima |
| D4 | decision | OK | 0.0 s | Ráfaga desde origen legítimo -> VP conf 0.6, humano |
| D6 | decision | OK | 0.0 s | Familia no soportada -> no_soportada |
| A2 | decision | OK | 0.0 s | Origen aparente = un cortafuegos -> retenida, alcanza_servicio |
| A3 | decision | OK | 0.0 s | Origen aparente = la gestión -> veto duro |
| A4 | decision | OK | 0.0 s | IP interna no inventariada -> activo interno, humano |
| K5 | decision | OK | 0.0 s | Ataque desde taquilla (nadie depende de ella) -> humano, sin cascada |
| C1 | inyectada | OK | 0.0 s | BLOQUEAR_PUERTO 1521 en core-db (excepción nunca_automatica) -> degrada a BLOQUEAR_IP |
| C2 | inyectada | OK | 0.0 s | BLOQUEAR_PUERTO 8443 en middleware -> degrada a BLOQUEAR_IP |
| C3 | inyectada | OK | 0.0 s | AISLAR_NODO de web-banking (alcanza servicio) -> humano |
| K2 | inyectada | OK | 0.0 s | AISLAR_NODO de core-db -> predice la cascada transitiva |
| K3 | inyectada | OK | 0.0 s | AISLAR_NODO de middleware -> la cascada NO incluye atm (dependencia no declarada) |
| A5 | inyectada | OK | 0.0 s | AISLAR_NODO del nodo de gestión (mdr-siem) -> veto duro |
| C5 | perfil | OK | 0.0 s | Acción sin reversión definida (OBS_PROCESOS) -> se veta como contención |
| K4 | perfil | OK | 0.0 s | afectados_en_cascada termina aunque haya dependencias (guardia de ciclos) |

**Notas:** K1 codifica un fallo conocido del prototipo (predice cascada `[]` aunque middleware, web-banking, api-movil y atm caen de verdad); cuenta OK mientras el fallo persista, y su título lo señala. Los casos de nivel `vivo` requieren `--con-vivo` con el banco levantado; sin esa bandera salen OMITIDO.
