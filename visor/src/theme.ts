// Paleta de los gráficos (Recharts / SVG). Los hex viven aquí y no como var(--x) porque Recharts
// los escribe en atributos SVG, donde var() no resuelve. Son LOS MISMOS valores que los tokens de
// index.css: theme.test.ts lo comprueba, así que un cambio en un sitio sin el otro rompe en test.

// Categórica en orden fijo, pasos propios por modo (el oscuro NO es un flip del claro). No ciclar
// hues. 13 valores = las 13 clases canónicas del motor (colorClase asigna por identidad): sin
// colisiones dentro del canon. Es identidad de serie, no estado: por eso no sale de los 6 tokens.
export const CATEGORICO_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
                                 "#4a3aa7", "#e34948", "#0e7f86", "#8a6d3b", "#6e6e6e", "#b0399f", "#7c8a00"]
export const CATEGORICO_DARK  = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300",
                                 "#9085e9", "#e66767", "#1c99a2", "#a3854e", "#8f8f8f", "#c955b8", "#93a31a"]

// Estados = --ok / --aviso / --grave / --critico / --enrutado / --violeta de index.css.
const SEMANTICO = {
  claro:  { ok: "#1a7f37", aviso: "#8a6300", grave: "#b04e12", critico: "#bc3d28", enrutado: "#46566a", violeta: "#6f42c1" },
  oscuro: { ok: "#3fb950", aviso: "#e3a93c", grave: "#ee8c4b", critico: "#f0785f", enrutado: "#9fb0c3", violeta: "#a98bfa" },
}
export type Semantico = typeof SEMANTICO.claro
export function semantico(oscuro: boolean): Semantico {
  return oscuro ? SEMANTICO.oscuro : SEMANTICO.claro
}

// Superficies del tema para ejes, rejilla, relleno de fondo, serie única y tooltip
// (= --border / --muted-foreground / --accent / --primary / --card de index.css).
const EJES = {
  claro:  { grid: "#d6dde7", texto: "#5a6776", relleno: "#e5eaf1", serie: "#0b7a8c", superficie: "#ffffff" },
  oscuro: { grid: "#2a3340", texto: "#8b98a9", relleno: "#212a37", serie: "#3cc6da", superficie: "#161b22" },
}
export function ejes(oscuro: boolean) {
  return oscuro ? EJES.oscuro : EJES.claro
}

// Estilos del tooltip de Recharts por modo (C7): el popup por defecto es blanco con texto oscuro y
// en la consola oscura quedaba ilegible en cada hover de cada gráfico.
export function tooltipEstilos(oscuro: boolean) {
  const e = ejes(oscuro)
  return {
    contentStyle: {
      backgroundColor: e.superficie,
      border: `1px solid ${e.grid}`, borderRadius: 6, fontSize: 12,
    },
    labelStyle: { color: e.texto },
    itemStyle: { color: e.texto },
  }
}
