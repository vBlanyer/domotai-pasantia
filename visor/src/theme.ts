// Paletas de referencia validadas (dataviz): categórica en orden fijo, pasos propios por modo
// (el oscuro NO es un flip del claro), más estados. No ciclar hues.
export const CATEGORICO_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
export const CATEGORICO_DARK  = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
export const ESTADO = { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" }

// Colores de ejes/rejilla/relleno de fondo por modo (contra la superficie de cada tema).
export function ejes(oscuro: boolean) {
  return oscuro
    ? { grid: "#2c2c2a", texto: "#c3c2b7", relleno: "#2c2c2a", serie: "#3987e5" }
    : { grid: "#ececea", texto: "#52514e", relleno: "#e9e9e6", serie: "#2a78d6" }
}

// Estilos del tooltip de Recharts por modo (C7): el popup por defecto es blanco con texto oscuro y
// en la consola oscura quedaba ilegible en cada hover de cada gráfico.
export function tooltipEstilos(oscuro: boolean) {
  const e = ejes(oscuro)
  return {
    contentStyle: {
      backgroundColor: oscuro ? "#1b1b1a" : "#ffffff",
      border: `1px solid ${e.grid}`, borderRadius: 6, fontSize: 12,
    },
    labelStyle: { color: e.texto },
    itemStyle: { color: e.texto },
  }
}
