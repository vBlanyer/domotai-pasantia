# Nivel 0 · Sanidad (sin dependencias, segundos)

**Sinopsis**
```
python3 -m unittest discover -s <directorio_de_tests>
```

**Ejemplo**
```bash
python3 -m unittest discover -s prototipo/tests      # el motor
python3 -m unittest discover -s lab/dataset/tests     # el pipeline del dataset
python3 -m unittest discover -s evaluacion/tests      # el marco de evaluación
```

**Esperado:** `OK` en las tres (≈169 + 33 + 28 tests). Si las tres dan verde, el prototipo está sano.

---

# Nivel 1 · El motor sobre datos reales (sin dependencias)

## 1.1 · Triaje sobre el dataset

Corre el lazo completo: clasifica → política → perfil → traza.

**Sinopsis**
```
python3 -m prototipo.triaje <alertas.jsonl> <perfil.yml> <hallazgos.json> <salida.jsonl>
```

**Ejemplo**
```bash
python3 -m prototipo.triaje lab/dataset/etiquetado.jsonl prototipo/perfiles/empresarial.yml \
    lab/campañas/2026-08-31-evaluacion/hallazgos.json salida.jsonl
```

**Esperado:** `410 decisiones -> salida.jsonl`. Cada línea es una traza auditable (`clase`, `prioridad`,
`confianza`, `justificacion`, `accion_propuesta`, `resultado_filtro`, `accion_final`, `requiere_humano`,
`version_justificador`…). Inspecciona una:
```bash
grep vp_intento_acceso salida.jsonl | head -1 | python3 -m json.tool
```
Prueba `prototipo/perfiles/residencial.yml` para ver cómo cambia el filtro de continuidad.

## 1.2 · Ingesta desde Wazuh crudo (RF-01)

Normaliza alertas crudas de Wazuh al esquema del motor (agnóstico de fuente).

**Sinopsis**
```
python3 -m prototipo.ingesta <cruda.json> <salida.jsonl> [fuente=wazuh] [campaña]
```

**Ejemplo**
```bash
python3 -m prototipo.ingesta lab/campañas/2026-08-31-evaluacion/alerts.json normalizado.jsonl wazuh
```

**Esperado:** `N alertas normalizadas -> normalizado.jsonl`. Avisa de las alertas con campos críticos
ausentes sin inventarlos (RNF-07).

## 1.3 · Agrupación por incidente (RF-11)

Colapsa las ráfagas casi idénticas en incidentes.

**Sinopsis**
```
python3 -m prototipo.agrupacion <normalizado.jsonl> <salida.jsonl> [ventana_seg=300]
```

**Ejemplo**
```bash
python3 -m prototipo.agrupacion normalizado.jsonl incidentes.jsonl 300
```

**Esperado:** `N alertas -> M incidentes (ventana 300s)`. Sobre las 205 de evaluación da **4 incidentes**;
sobre las 18 soportadas, **2** (el ataque y el admin legítimo).
