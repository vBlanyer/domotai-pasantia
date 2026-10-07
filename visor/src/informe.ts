// Rango de fechas (YYYY-MM-DD) de un preset del informe. Se calcula de partes locales (no toISOString,
// que pasa a UTC y puede correr un día). `hasta` incluye el último día del periodo.
export type Preset = "mes" | "año"

const dd = (y: number, m: number, d: number) =>
  `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`

export function rangoDe(preset: Preset, hoy: Date): { desde: string; hasta: string } {
  const y = hoy.getFullYear(), m = hoy.getMonth()
  if (preset === "año") return { desde: dd(y, 0, 1), hasta: dd(y, 11, 31) }
  const ultimo = new Date(y, m + 1, 0).getDate()        // día 0 del mes siguiente = último de este
  return { desde: dd(y, m, 1), hasta: dd(y, m, ultimo) }
}

// Etiqueta legible del periodo para la cabecera del informe.
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
export function etiquetaPeriodo(desde?: string | null, hasta?: string | null): string {
  if (!desde && !hasta) return "Todo el histórico"
  if (desde && hasta) {
    const [ay, am] = desde.split("-"), [by, bm, bd] = hasta.split("-")
    if (ay === by && am === bm && desde.endsWith("-01") && bd === String(new Date(+by, +bm, 0).getDate()))
      return `${MESES[+am - 1]} de ${ay}`                 // mes completo
    if (ay === by && desde === `${ay}-01-01` && hasta === `${by}-12-31`) return `Año ${ay}`
    return `${desde} a ${hasta}`
  }
  return desde ? `desde ${desde}` : `hasta ${hasta}`
}
