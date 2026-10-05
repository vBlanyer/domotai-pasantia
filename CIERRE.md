# Cierre: robustez y optimización (rama `feat/robustez-y-cierre`)

Trabajo autónomo sobre `main` para dejar el prototipo más robusto y limpio, pensado para probar
antes de fusionar. Sale de las consideraciones que surgieron al revisar los límites del sistema
(seguridad de la contención automática, honestidad de la medición, gobernanza, resiliencia).

**Nada está fusionado en `main`.** Todas las suites quedan en verde: prototipo 640, evaluación 59,
banco 114, dataset 39, visor 117; `tsc` limpio, build OK, 0 errores de lint.

## Qué cambió

### Robustez

1. **Terceros externos de confianza (`terceros_confiables` en el perfil).** Un ataque aparente desde
   un socio crítico externo (pasarela de pago, proveedor) ya **no se auto-bloquea** —cortarlo tiraría
   un servicio de negocio—: se **retiene para aprobación humana** conservando la acción. Admite IP o
   CIDR. Vacío por defecto (no cambia las métricas canónicas). Ejemplo comentado en
   `prototipo/perfiles/bancario.yml`.
   *Por qué:* el sistema auto-bloquea IPs externas; sin esta lista, bloquearía a un tercero legítimo.

2. **Validación del perfil al arrancar (`perfil.validar`).** El daemon revisa el perfil al cargarlo y
   **avisa** de incoherencias (IPs/CIDR no parseables, `ip_gestion` ausente, `depende_de` colgante,
   `umbral_confianza` fuera de [0,1], `rafaga.umbral` no entero) **sin romper**. Un perfil mal escrito
   se ve al inicio, no falla en silencio en la primera alerta.

3. **Latido de la ingesta.** Si la fuente (Wazuh) deja de enviar alertas, el daemon lo **avisa una
   vez** tras 120 s de silencio (`silencio_s`) y se rearma al volver una alerta. Un fallo silencioso
   de la ingesta es peor que uno ruidoso.

4. **Atribución del operador (no repudio).** `/api/aprobar` acepta `operador`, que queda como
   `veredicto_por` en la traza. El visor lo envía (nombre guardado por navegador, input en
   Aprobaciones) y lo muestra en Decisiones («… por X»). Camino de la cola (modo web normal); el
   camino bloqueante del agente queda pendiente.

5. **Métricas de valor.** `tablero.metricas` añade `escalado_humano`/`pct_humano` (cuánto NO resuelve
   solo el MDR) y `override`/`tasa_override` (cuántas veces el analista corrige al motor: rechazar o
   reclasificar). El visor muestra dos KPI nuevos. Es el argumento de valor del MDR: cuánta carga
   quita al humano y cuánta confianza merece su criterio.

### Optimización / buenas prácticas

6. **Caché de la traza por mtime+tamaño.** El visor sondea cada 2 s cinco endpoints que releían y
   re-parseaban la traza entera cada vez; ahora se relee solo si el fichero cambió.

7. **Código muerto retirado.** La vista Red sustituyó a Equipos: se eliminan `estado_equipos`,
   `_categoria_equipo`, la ruta `/api/equipos` y los atributos `srv.activos`/`topologia` (ya no los
   usa el visor), con sus tests. `_resumen_traza` calcula `contencion_de` una sola vez por registro.

8. **Docs al día.** RUNBOOK, `docs/pruebas/09` y `PLAN-TANDAS` (A10 marcado obsoleto) reflejan que la
   vista Red sustituyó a Equipos.

## Cómo probarlo

Reinicia el daemon (hay API nueva) y recompila el visor:

```bash
sh lab/banco/banco.sh aprovisionar && sh lab/banco/banco.sh restaurar
cd visor && npm run build && cd ..
sh reiniciar.sh
```

- **Terceros de confianza:** descomenta `terceros_confiables: ["198.51.100.0/24"]` en
  `prototipo/perfiles/bancario.yml`, reinicia, lanza D1 (atacante externo 198.51.100.10 contra
  web-banking). Antes se auto-bloqueaba; ahora debe **aparecer en Aprobaciones** (retenida), no
  cortarse sola.
- **Validación del perfil:** mete una errata (p. ej. `ip_gestion: nope`) y arranca el daemon: debe
  salir `[aviso] perfil: ip_gestion no es una IP válida…` sin romper.
- **Latido de la ingesta:** deja el daemon sin enviarle alertas 2 min: debe avisar
  `[aviso] ingesta: sin alertas desde hace N s…` una vez.
- **Operador:** en el visor, pon tu nombre en el campo «Operador» de Aprobaciones, aprueba una
  decisión; en Decisiones debe salir «… por <tu nombre>» y quedar en la traza como `veredicto_por`.
- **Métricas de valor:** en la vista Métricas, los KPI «escalado a decisión humana» y «corrección del
  analista (override)».

## Lo que NO se tocó (a propósito)

- La detección y las familias (sigue siendo lo que Wazuh alerta + las 4 familias): ampliar cobertura
  de ataques es trabajo mayor, documentado como alcance/futuro.
- El canal de respuesta (`docker exec` del laboratorio), UEBA, segunda fuente/SIEM, TTL de bloqueos
  con caducado automático: quedan como trabajo futuro.
- El camino bloqueante del agente no registra operador (solo el de la cola).

## Commits de la rama

```
d0f3dd9 feat(perfil): terceros externos de confianza no se auto-bloquean (se retienen a humano)
4d846d9 feat(perfil): validacion de cordura del perfil al arrancar (B11)
caabe14 feat(metricas): metricas de valor (carga al analista y tasa de override)
1870b4f feat(aprobaciones): registra quien aprueba (no repudio) en la traza y el visor
59bdbe2 feat(stream): latido de la ingesta — avisa si la fuente deja de enviar alertas
2a28f94 perf(tablero): cachea la traza por mtime+tamano (sondeo del visor)
bcaa550 refactor(tablero): retira el codigo muerto de «Equipos» y calcula contencion_de una vez
9ba3318 docs: Red sustituye a Equipos en docs; ejemplo de terceros_confiables en el perfil
```
