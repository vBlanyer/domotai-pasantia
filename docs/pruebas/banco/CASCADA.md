# CASCADA · Tumbar core-db (sin el prototipo): cascada real del laboratorio

- nivel: vivo

## Preparar
```bash
docker exec clab-banco-core-db sh -c "pkill -f 'servicio.py --nombre core-db'"
```

## Esperado
```json
{
 "caen": [
  "api-movil",
  "atm",
  "core-db",
  "middleware",
  "web-banking"
 ]
}
```

## Deshacer
```bash
docker exec clab-banco-core-db REARRANCAR
```
