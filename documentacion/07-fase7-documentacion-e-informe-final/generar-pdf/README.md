# Generar el PDF del manual de usuario

Convierte `manual-de-usuario.md` en `manual-de-usuario.pdf` (A4, portada, pie con número de página y
marcadores). Sin dependencias de Python ni de npm: un conversor del subconjunto de Markdown que usa el
manual y Chromium en modo headless.

```
cd documentacion/07-fase7-documentacion-e-informe-final
python3 generar-pdf/convertir.py manual-de-usuario.md /tmp/manual.html
CHROME=/ruta/a/chrome node generar-pdf/imprimir.mjs /tmp/manual.html manual-de-usuario.pdf
```

`CHROME` es el ejecutable de Chrome o Chromium (por defecto, `chromium` en el PATH; vale el de
Playwright). Fuentes: Ubuntu Sans y Ubuntu Mono, con DejaVu de respaldo para los símbolos.
