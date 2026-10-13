# Requisitos del cliente y gobernanza

> Complemento organizativo de [`integracion-en-produccion.md`](integracion-en-produccion.md) (la parte
> técnica) y de la [hoja de ruta a producción](hoja-de-ruta-a-produccion.md). Aquélla cubre **cómo** se
> configura el MDR; ésta recoge lo que **no es código** y que debe aportar o decidir la **empresa/cliente**
> antes de un despliegue real: autorización para actuar, el auditor, el hardware del modelo, la custodia de
> secretos y el control de cambios. Para cada uno: qué decide/provee el cliente y una plantilla o lista de
> verificación.

Escrito para el equipo de despliegue/seguridad del cliente y la coordinación de la empresa.

---

## 1. Autorización para actuar — reglas de enganche (#8)

El MDR puede **contener** (bloquear IPs, cerrar servicios, bloquear cuentas) sobre la red del cliente. El
motor ya respeta los límites que se le configuran (perfil + vetos + *kill switch*), pero **la autorización de
qué puede hacer y cuándo es una decisión del cliente, por escrito**, no del software. Sin ella, el MDR no debe
operar en modo automático.

**Qué provee el cliente:** un documento de *reglas de enganche* firmado, que el perfil del MDR traduce a
configuración. Plantilla mínima:

- **Alcance de actuación.** Qué activos/subredes puede contener el MDR y cuáles quedan excluidos
  (p. ej. nunca el plano de gestión — ya es un veto duro del motor).
- **Qué se automatiza y qué exige humano.** Por nivel de impacto: ¿bloquear una IP en un host se auto-ejecuta?
  ¿y en el cortafuegos perimetral? Las joyas de la corona van siempre a validación humana.
- **Terceros intocables.** Pasarelas de pago, proveedores: se detectan como amenaza pero **no se auto-bloquean**
  (cortarlos tira negocio) → se retienen a humano.
- **Ventanas.** ¿Hay franjas (p. ej. cierre contable) en las que toda contención exige humano?
- **Quién autoriza y quién opera.** Quién firma estas reglas; quién puede **pausar la automatización** y hacer
  **des-bloqueo en masa** (el *kill switch* del visor); cómo se registra quién lo hizo.

**Enganche técnico:** el alcance, la política por impacto y los terceros se declaran en el **perfil** del
cliente (`activos`, `continuidad`, `terceros_confiables`, `excepciones`, `ip_gestion`); el *kill switch* vive
en el visor (`/api/pausa`, `/api/revertir-todo`). Pendiente menor del prototipo: anotar en la traza **quién**
activa/suelta la pausa (no-repudio).

---

## 2. Despliegue del auditor de postura (#3)

El auditor aparece **dos veces** en el flujo: antes de decidir aporta la **postura** del activo (qué puertos
tiene expuestos) como contexto, y después de actuar **reescanea** para verificar que la contención cerró la
exposición. En el laboratorio es un contenedor con Nmap; en producción hay que desplegarlo.

**Qué decide/provee el cliente:**

- **Dónde corre.** Un host en el plano de gestión con alcance de red para escanear los activos vigilados
  (out-of-band, como el nodo del MDR).
- **Alcance de escaneo autorizado.** Qué subredes/activos puede escanear el auditor — **escaneo autorizado por
  escrito**; un escaneo no autorizado es en sí un incidente.
- **Nmap o Greenbone.** Nmap responde «expuesto sí/no» (lo que el motor usa hoy); Greenbone añade CVE por
  activo, a cambio de desplegar y mantener un escáner de vulnerabilidades. El prototipo se evaluó con Nmap;
  Greenbone queda como opción del cliente.
- **Credenciales y cadencia** del escaneo (periódico + bajo demanda tras una contención).

**Nota de alcance:** la postura entra por el mismo contrato que ya consume el motor (`hallazgos`), así que
integrar un auditor real no cambia la lógica de decisión.

---

## 3. Modelo de análisis y hardware (#11)

El análisis se resuelve en **dos perfiles de modelo**, y el cliente elige según su hardware:

- **Perfil A (híbrido).** Ejecutable **sin GPU**: un encoder para clasificar, un modelo pequeño en línea para la
  justificación breve que la validación humana necesita y uno mayor en lote para la extensa. Es con el que se
  evaluó el prototipo; corre en un equipo modesto (CPU + RAM).
- **Perfil B (un solo modelo).** Un único modelo de ~8B que requiere **GPU** con VRAM suficiente. Da mejor
  justificación a cambio del hardware.

Los resultados de ambos perfiles **no son comparables entre sí**: una campaña fija su perfil y no lo cambia a
mitad.

**Qué decide/provee el cliente:** el perfil y, si es el B, la **GPU**. Mientras tanto, el prototipo corre en
**modo determinista** por defecto (sin LLM), que es plenamente funcional para la demo y la decisión; el
justificador con modelo es `--con-llm`. El **clasificador con ajuste fino** —que resolvería de raíz el límite
de la señal de origen— sigue bloqueado por falta de un conjunto de datos variado, no por hardware (es un ítem
de datos, no de despliegue; ver las recomendaciones del informe).

---

## 4. Custodia de secretos — vault (#9)

El MDR usa dos secretos: la **clave SSH** del conector (para actuar sobre los dispositivos) y, opcionalmente,
`TRIAJE_TRAZA_CLAVE` (el HMAC que firma la cadena de la traza). Hoy se pasan por variable de entorno / ruta en
disco; en producción deben vivir en un **gestor de secretos (vault)**.

**Qué decide/provee el cliente:**

- **Dónde viven.** Un vault (HashiCorp Vault, el secreto de Kubernetes, el *keyring* del SO…) que inyecte los
  valores en el entorno del servicio en el arranque (p. ej. el `EnvironmentFile` de systemd lo rellena un
  agente del vault), en lugar de dejarlos en claro en `/etc/mdr/triaje.env`.
- **Rotación.** El conector ya trae `lab/scripts/rotar-clave-conector.sh` (rotación todo-o-nada sobre todos los
  nodos, verificada antes de retirar la anterior y anotada en Wazuh); el cliente define la **cadencia** y quién
  la ejecuta. Si la traza va firmada, el **cron de retención** debe llevar la misma `TRIAJE_TRAZA_CLAVE`.
- **Acceso auditado.** Quién puede leer los secretos y queda registro de ello.

**Enganche técnico:** el conector lee `TRIAJE_SSH_CLAVE`/`TRIAJE_SSH_USUARIO`/`TRIAJE_SSH_KNOWN_HOSTS` del
entorno y falla-cerrado sin credencial; el MDR no necesita cambiar para que un vault los provea.

---

## 5. Control de cambios del catálogo y el perfil (#10)

Dos ficheros gobiernan lo que el MDR puede hacer en el cliente, y **cambiarlos cambia el radio de impacto**:

- El **catálogo de acciones** (`prototipo/catalogo.yml`): es la frontera cerrada de lo que el sistema puede
  ejecutar **y** de su privilegio en los nodos (el sudoers se genera de él). Añadir una acción amplía lo que el
  sistema puede ejecutar.
- El **perfil del cliente** (`perfiles/<cliente>.yml`): aflojar su política de continuidad convierte en
  automático lo que antes pedía humano.

**Qué decide/provee el cliente/empresa:** un proceso de revisión ligero pero registrado.

- Todo cambio en el catálogo o el perfil va por **revisión de un segundo** (seguridad/coordinación) antes de
  aplicarse, versionado en git (ya lo están).
- **Quién aprueba** añadir una acción al catálogo (y regenerar el sudoers) o subir la automatización de un
  perfil.
- Tras cada cambio del catálogo, **regenerar el sudoers** (`python3 -m prototipo.catalogo --sudoers …`) y
  redesplegarlo a los nodos.

---

## Resumen

| # | Qué falta | Quién | Qué aporta el prototipo |
|---|---|---|---|
| 8 | Reglas de enganche por escrito | Cliente/empresa | El perfil y el *kill switch* las aplican |
| 3 | Desplegar el auditor | Cliente | Mismo contrato de postura; no cambia la decisión |
| 11 | Hardware del modelo | Cliente | Dos perfiles; modo determinista entre tanto |
| 9 | Vault de secretos | Empresa | Lee del entorno (fail-closed); rotación incluida |
| 10 | Control de cambios | Empresa | Catálogo/perfil versionados; sudoers regenerable |

Ninguno exige tocar la lógica de decisión: son configuración, infraestructura y gobernanza que el cliente y la
empresa aportan sobre la arquitectura ya construida.
