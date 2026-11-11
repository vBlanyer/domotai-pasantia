# Laboratorio «oficina»

Una red pequeña que el MDR **no conoce**, para ensayar la instalación en un cliente nuevo con el asistente
de red: escanear, revisar, exportar el perfil, dar de alta cada equipo en Conectividad y contener un ataque.
Plan: [`plan-asistente-de-red.md`](../../documentacion/05-fase5-implementacion-del-prototipo/plan-asistente-de-red.md).

```
internet ── fw-borde ─┬─ mdr 10.99.0.10 (MDR: escanea y aloja el conector)
                      ├─ sw-dmz ─┬─ srv-web01 172.16.10.10 · srv-correo01 172.16.10.20
                      └─ fw-interno ── sw-interna ─┬─ srv-app01 .10 · srv-db01 .20 · nas01 .30
                                                   └─ impresora .50 · puesto .77   (10.20.0.0/24)
```

La fuente única de IPs y servicios es [`red.py`](red.py); la topología es
[`lab/topologias/oficina.clab.yml`](../topologias/oficina.clab.yml). Los servicios son simulados (HTTP mínimo
en su puerto); la impresora y el puesto no tienen SSH. Los registros de SSH llegan a Wazuh con el nombre de
cada equipo.

## Levantar y bajar

    sh lab/oficina/oficina.sh up       # no convive con el banco ni con la red pequeña
    sh lab/oficina/oficina.sh test     # desde mdr llega a todos; internet solo entra por fw-borde
    sh lab/oficina/oficina.sh atacar   # fuerza bruta SSH desde internet contra srv-web01
    sh lab/oficina/oficina.sh mdr      # el MDR como en un cliente nuevo (perfil mínimo) en :8787
    sh lab/oficina/oficina.sh down

**A propósito, nada está preparado para el MDR:** ningún equipo trae el usuario `triaje` ni su `sudoers`
(no hay `aprovisionar`, a diferencia del banco). El acceso se da con el paquete de alta de la vista
Conectividad. Cada equipo genera sus propias claves SSH del host al levantarse, así que cada uno tiene su
huella.

## Probar el asistente de red

El recorrido completo (escanear, revisar, exportar, instalar, dar de alta cada equipo y contener un ataque)
está en el [manual de usuario, sección 22](../../documentacion/07-fase7-documentacion-e-informe-final/manual-de-usuario.md#22-asistente-de-red-instalar-una-red-nueva).
`oficina.sh mdr` arranca el MDR con `run/oficina/perfil.yml` (si no existe, el perfil mínimo) y detiene
antes cualquier otro daemon del MDR. Para empezar de cero: `down`, `up` y borrar `run/oficina/`.
