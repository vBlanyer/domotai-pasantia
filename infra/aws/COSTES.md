# Costes del despliegue en AWS

Estimación de lo que cuesta cada escenario del [inventario](inventario/), con los **precios oficiales
bajo demanda consultados el 17/11/2026** (USD, sin impuestos, sin capa gratuita ni créditos, sin
descuentos por compromiso). Los precios cambian: vuelve a consultarlos antes de presupuestar.

## Precios usados

| Concepto | `eu-west-1` (por defecto) | `us-east-1` | Unidad |
|---|---|---|---|
| MDR `t3.small` (Linux) | 0,0228 | 0,0208 | $/hora |
| GPU `g4dn.xlarge` (Linux) | 0,587 | 0,526 | $/hora |
| Disco EBS `gp3` | 0,088 | 0,080 | $/GB-mes |
| Instantánea EBS | 0,05 | 0,05 | $/GB-mes |
| NAT Gateway | 0,048 | 0,045 | $/hora |
| Datos procesados por el NAT | 0,048 | 0,045 | $/GB |
| IP pública IPv4 (la del NAT) | 0,005 | 0,005 | $/hora |
| Endpoint de interfaz (por endpoint y zona) | 0,011 | 0,010 | $/hora |
| Datos por endpoint de interfaz | 0,01 | 0,01 | $/GB |
| Endpoint de puerta de enlace de S3 | gratis | gratis | — |
| Secreto en Secrets Manager | 0,40 | 0,40 | $/secreto-mes |
| Llamadas a Secrets Manager | 0,05 | 0,05 | $/10 000 llamadas |
| S3 estándar (paquete, perfil, modelos) | 0,023 | 0,023 | $/GB-mes |

**Fuentes** (API pública de precios de AWS, fichero de oferta por región, campo *Publication Date*):

- Instancias: `https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/<región>/Linux/index.json` (publicado el 14/11/2026).
- EBS y NAT: `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/<región>/index.csv` (14/11/2026).
- Endpoints e IPv4: `…/offers/v1.0/aws/AmazonVPC/current/<región>/index.json` (17/11/2026).
- Secrets Manager: `…/offers/v1.0/aws/AWSSecretsManager/current/<región>/index.json` (11/11/2026).
- S3: `…/offers/v1.0/aws/AmazonS3/current/<región>/index.csv` (16/11/2026).

## Qué se cobra en cada escenario

Una sola zona de disponibilidad (una subred privada), así que cada endpoint de interfaz cuenta una vez.
Discos: raíz del MDR 12 GB + traza 20 GB; raíz de la GPU 100 GB.

| Escenario | Instancias | Discos | Red | Secretos |
|---|---|---|---|---|
| **A** · MDR con egreso | `t3.small` | 32 GB | NAT + su IP + 3 endpoints (SSM) | ninguno (se generan en la instancia) |
| **B** · MDR sin egreso (recomendado) | `t3.small` | 32 GB | 4 endpoints (SSM + Secrets Manager) | 2 |
| **D** · MDR + GPU | `t3.small` + `g4dn.xlarge` | 132 GB | NAT + su IP + 3 endpoints (SSM) | ninguno |

## Coste por escenario

«Prueba de 8 h / 24 h» = crear, usar y hacer `destroy` al acabar. «Mes» = 730 h encendido.
«Apagado» = instancias paradas pero la infraestructura en pie: los discos, el NAT, su IP, los endpoints
y los secretos **se siguen cobrando**.

### `eu-west-1`

| Escenario | Por hora | Prueba de 8 h | Prueba de 24 h | Mes 24/7 | Mes con las instancias paradas |
|---|---|---|---|---|---|
| A · MDR con egreso | 0,113 $ | 0,90 $ | 2,70 $ | 82 $ | 66 $ |
| B · MDR sin egreso | 0,072 $ | 0,57 $ | 1,72 $ | 52 $ | 36 $ |
| D · MDR + GPU | 0,712 $ | 5,69 $ | 17,08 $ | 520 $ | 74 $ |

### `us-east-1`

| Escenario | Por hora | Prueba de 8 h | Prueba de 24 h | Mes 24/7 | Mes con las instancias paradas |
|---|---|---|---|---|---|
| A · MDR con egreso | 0,104 $ | 0,83 $ | 2,50 $ | 76 $ | 61 $ |
| B · MDR sin egreso | 0,065 $ | 0,52 $ | 1,57 $ | 48 $ | 33 $ |
| D · MDR + GPU | 0,641 $ | 5,13 $ | 15,39 $ | 468 $ | 69 $ |

**Uso de oficina con GPU** (D, MDR y red 24/7, la GPU encendida solo 8 h × 22 días laborables):
unos **194 $/mes** en `eu-west-1` y **177 $/mes** en `us-east-1`. La GPU se para y arranca con
`aws ec2 stop-instances` / `start-instances`; parada solo cobra su disco (100 GB ≈ 8,80 $/mes).

### Dónde se va el dinero

- **La GPU** es casi todo el coste de D (0,587 $/h de 0,712 $/h).
- **El NAT** (0,048 $/h + 0,005 $/h de IP ≈ 39 $/mes) es lo que más pesa sin GPU, y no se puede quitar
  después del primer arranque en A (el paquete viene de GitHub) ni en D (la GPU exige
  `egreso_bootstrap`). Por eso B, sin NAT, es el escenario de producción recomendado.
- **Los endpoints de interfaz** (≈ 8 $/mes cada uno) son el resto del coste fijo. Son lo que permite
  entrar por SSM y leer los secretos sin abrir puertos ni salir a Internet.

## Aparte

- **Datos del NAT:** el primer arranque descarga paquetes del sistema y el MDR (y en la GPU, llama.cpp y
  sus dependencias de compilación). Cada GB que pasa por el NAT cuesta 0,048 $. Los modelos llegan por
  el endpoint de S3, que es gratis.
- **S3:** el paquete y el perfil ocupan unos MB; los modelos de la GPU, varios GB (p. ej., 6 GB ≈
  0,14 $/mes). El estado de OpenTofu ocupa unos KB.
- **Instantánea de la traza** antes de `destroy`: como mucho 20 GB × 0,05 $ = 1 $/mes (solo se cobra lo
  ocupado).
- **Llamadas a Secrets Manager:** el arranque lee dos secretos; el coste es despreciable.

## Lo que se sigue cobrando después de `destroy`

Los secretos (0,40 $/mes cada uno), los buckets de S3 (artefactos y estado) y las instantáneas que hagas.
Todo lo demás del inventario desaparece con `destroy`.

## Comparación con el equipo local (orientativa)

Un equipo local de unos 3000 $ equivale a unos **176 días** del escenario D encendido 24 h en
`eu-west-1` (195 en `us-east-1`), o a unos **15 meses** de uso de oficina con la GPU 8 h al día
(17 en `us-east-1`). Esta cuenta no incluye la electricidad, el mantenimiento ni la amortización del
equipo, ni el personal que lo opera; sirve solo para dar una idea del orden de magnitud.
