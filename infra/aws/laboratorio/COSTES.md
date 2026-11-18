# Costes de la variante laboratorio en AWS

Estimación de lo que cuesta el laboratorio (el [inventario](inventario/)), con los **precios oficiales bajo
demanda consultados el 17/11/2026** (USD, sin impuestos, sin capa gratuita ni créditos, sin descuentos por
compromiso). Los precios cambian: vuelve a consultarlos antes de presupuestar.

## Precios usados

| Concepto | `eu-west-1` (por defecto) | `us-east-1` | Unidad |
|---|---|---|---|
| Laboratorio `t3.xlarge` (Linux) | 0,1824 | 0,1664 | $/hora |
| Disco EBS `gp3` | 0,088 | 0,080 | $/GB-mes |
| Instantánea EBS | 0,05 | 0,05 | $/GB-mes |
| NAT Gateway | 0,048 | 0,045 | $/hora |
| Datos procesados por el NAT | 0,048 | 0,045 | $/GB |
| IP pública IPv4 (la del NAT) | 0,005 | 0,005 | $/hora |
| Endpoint de interfaz (por endpoint y zona) | 0,011 | 0,010 | $/hora |
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

## Qué se cobra

Una máquina `t3.xlarge` (4 vCPU, 16 GB); discos de 40 GB (raíz: las imágenes de Docker) y 20 GB (traza);
el NAT del primer arranque y su IP, que quedan mientras exista el laboratorio; y tres endpoints de
interfaz de SSM (una sola zona). Sin secretos salvo que los crees (0,40 $/mes cada uno).

| | Por hora | Prueba de 8 h | Prueba de 24 h | Mes 24/7 | Mes con la máquina parada |
|---|---|---|---|---|---|
| `eu-west-1` | 0,276 $ | 2,21 $ | 6,62 $ | 201 $ | 68 $ |
| `us-east-1` | 0,253 $ | 2,02 $ | 6,07 $ | 185 $ | 63 $ |

«Prueba de 8 h / 24 h» = crear, usar y hacer `destroy` al acabar. «Mes» = 730 h.

## Según cómo se use (`eu-west-1` / `us-east-1`)

| Uso | Coste | Cómo |
|---|---|---|
| Encendido 24/7 | ≈ 201 $ / 185 $ al mes | — |
| Parar y encender (8 h × 22 días laborables) | ≈ 100 $ / 92 $ al mes | `aws ec2 stop-instances` / `start-instances`; al encender, el laboratorio se rehace solo en unos minutos |
| `destroy` al terminar | 2,21 $ / 2,02 $ por prueba de 8 h | cada vez, arranque completo (descargas e instalación) y se pierde la traza |

Parado sigue costando unos 68 $ / 63 $ al mes, casi todo el NAT y los endpoints de SSM.

## Dónde se va el dinero

- **La máquina** (0,18 $/h en `eu-west-1`) es dos tercios del coste encendido.
- **El NAT** (0,048 $/h + 0,005 $/h de IP ≈ 39 $/mes) y **los tres endpoints de SSM** (≈ 8 $/mes cada
  uno) se cobran aunque la máquina esté parada: son lo que queda en «parado». Para no pagarlos, `destroy`.
- **Créditos de CPU:** las `t3` arrancan en modo *unlimited* y cobran aparte los créditos que gasten por
  encima de su línea base si mantienen la CPU alta durante horas (por ejemplo, con `atacar continuo`). No
  está incluido arriba: consulta el precio en la página de instancias T3 si vas a hacer pruebas largas.
