# Generar los PDF de los manuales

Convierte `manual-de-usuario.md` y `manual-de-produccion.md` en sus PDF con diseño de guía funcional:

- una portada con banda;
- cabecera y pie en cada página;
- un índice con números de página;
- tablas con cabecera azul;
- cajas «Quién puede», «Nota» y «Ejemplo»;
- marcadores.

No necesita dependencias de Python ni de npm: usa un conversor del subconjunto de Markdown del manual
y Chromium en modo headless.

```
cd documentacion/07-fase7-documentacion-e-informe-final
CHROME=/ruta/a/chrome sh generar-pdf/generar.sh               # los dos
CHROME=/ruta/a/chrome sh generar-pdf/generar.sh produccion    # o solo uno: usuario | produccion
```

El tipo de documento de la portada y la línea bajo el título los pasa `generar.sh` a `convertir.py`
con `--titulo` y `--sub`.

`CHROME` es el ejecutable de Chrome o Chromium. Por defecto se usa `chromium` del PATH; también vale
el de Playwright. Hace falta una versión reciente, con soporte de cajas de margen `@page`, que es lo
que pone la cabecera y el pie y deja la portada sin ellos.

El PDF se genera en dos pasadas:

1. Se imprime una vez.
2. `paginas.py` lee de los marcadores del PDF en qué página cae cada sección.
3. Se vuelve a imprimir con esos números en el índice.

## Cajas en el Markdown

Una cita que empieza por «Quién puede:», «Nota:» o «Ejemplo:» en negrita sale como su caja:

```
> **Quién puede:** cualquier analista.
```

## La portada

La banda azul de la portada lleva «MDR · CONSOLA DE TRIAJE» en texto. Para poner un logo, sustituye
`<div class="marca">…</div>` en `convertir.py` por un `<img>` con el SVG o PNG en blanco.
