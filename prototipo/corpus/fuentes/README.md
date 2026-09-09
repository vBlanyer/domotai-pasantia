# Fuentes crudas del corpus RAG

Aquí van los **bundles STIX oficiales** de los que se **deriva** el corpus curado del RAG
(`prototipo/corpus/corpus.jsonl`). Son ficheros grandes y descargables, así que **no se versionan**
(gitignored, como `modelos/`); lo que se versiona es el corpus curado que generamos a partir de ellos.

## Ficheros esperados

| Fichero | Qué es | Origen oficial |
|---------|--------|----------------|
| `enterprise-attack.json` | Bundle STIX 2.1 de **MITRE ATT&CK Enterprise** (~35 MB): todas las técnicas, subtécnicas, tácticas y mitigaciones | [mitre-attack/attack-stix-data](https://github.com/mitre-attack/attack-stix-data) → `enterprise-attack/enterprise-attack.json` |

Descarga directa:

```bash
curl -L -o prototipo/corpus/fuentes/enterprise-attack.json \
  https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json
```

(D3FEND se toma de [d3fend.mitre.org](https://d3fend.mitre.org/); su ontología se puede añadir aquí
como segunda fuente cuando la integremos.)

## Cómo alimenta el RAG

El bundle NO se indexa tal cual (es enorme y ruidoso para un 1B). El flujo es:

1. **Extraer** de `enterprise-attack.json` solo las técnicas/subtécnicas relevantes al perímetro
   soportado (acceso a credenciales, reconocimiento, servicio expuesto, explotación conocida).
2. **Redactar** fichas cortas y correctas (técnica → indicadores → contramedida D3FEND → acción del
   catálogo) hacia `prototipo/corpus/corpus.jsonl`.
3. **Reindexar** con `python3 -m prototipo.rag --indexar` (embeddings locales).

Es decir: la fuente cruda es MITRE; el corpus curado es lo que embebe el RAG.
