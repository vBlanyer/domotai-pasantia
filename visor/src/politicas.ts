// El «Resumen» de la vista Políticas, en tres columnas: lo que el MDR contiene solo, lo que espera a un
// analista y lo que nunca hace solo. Lógica pura sobre /api/politica (sin React): se prueba en seco.
import type { PoliticaEstado } from "@/api"

const FAMILIAS: Record<string, string> = {
  acceso_credenciales: "Fuerza bruta",
  reconocimiento: "Reconocimiento (escaneo)",
  servicio_expuesto: "Servicio expuesto",
  acceso_consumado: "Intrusión consumada",
  explotacion_conocida: "Explotación conocida",
  abuso_de_cuenta: "Abuso de cuenta",
  integridad_fichero: "Cambios en ficheros vigilados",
  denegacion_servicio: "Denegación de servicio",
  exfiltracion: "Exfiltración / C2",
  malware: "Malware",
}

const ACCIONES: Record<string, string> = {
  BLOQUEAR_IP: "bloquea el origen",
  MATAR_CONEXION: "corta la sesión abierta",
  BLOQUEAR_PUERTO: "cierra el puerto",
  AISLAR_NODO: "aísla el equipo",
  LIMITAR_BANDA: "limita la banda",
  FORZAR_CAMBIO_PASS: "bloquea la cuenta",
  BLOQUEAR_DESTINO: "corta el destino",
}

// Una familia nueva sin nombre sale con su identificador: nunca desaparece.
export const nombreFamilia = (f: string): string => FAMILIAS[f] ?? f

export function accionEnPalabras(accion?: string | null, ruta?: string | null): string {
  if (accion) return ACCIONES[accion] ?? accion
  return ruta ? "se tría y se enruta" : "sin acción"
}

export type Item = { titulo: string; detalle?: string }
export type ResumenPolitica = {
  frase: string; solo: Item[]; humano: Item[]; nunca: Item[]
  certeza: number | null; confianza: string | null
}

const SOLO = new Set(["automatica", "automatica_si_confianza"])

export function resumenPolitica(est: PoliticaEstado): ResumenPolitica {
  const item = (f: PoliticaEstado["familias"][number]): Item =>
    ({ titulo: nombreFamilia(f.familia), detalle: accionEnPalabras(f.accion, f.ruta) })
  const solo = est.familias.filter((f) => SOLO.has(f.automatizacion_efectiva))
  const nunca = est.familias.filter((f) => f.automatizacion_efectiva === "nunca_automatica")
  const humano = est.familias.filter((f) => !SOLO.has(f.automatizacion_efectiva) && f.automatizacion_efectiva !== "nunca_automatica")
  const conf = est.confianza

  const esperan: Item[] = humano.map(item)
  // Sin decirlo la política, bloquear lo propio exige analista (el motor lo aplica así por defecto).
  if (conf?.equipos_propios !== "automatica_si_confianza") esperan.push({ titulo: "Bloquear un equipo propio" })
  for (const i of est.intocables ?? []) {
    esperan.push({ titulo: [i.activo ?? "—", i.funcion].filter(Boolean).join(" · "), detalle: `puerto ${i.servicio ?? "—"}` })
  }
  if (conf?.revisar_desde_nivel != null) {
    esperan.push({ titulo: `Alertas que no reconoce, de nivel ${conf.revisar_desde_nivel} o más`, detalle: "a revisión, sin acción" })
  }

  const rafaga = conf?.rafaga ? ` salvo ráfaga de ${conf.rafaga.alertas} alertas en ${conf.rafaga.en_segundos} s` : ""
  return {
    frase: `De ${est.familias.length} tipos de ataque, el MDR contiene ${solo.length} solo (si está seguro), ` +
      `deja ${humano.length} a un analista y ${nunca.length} nunca los toca solo. Todo lo que hace se puede deshacer.`,
    solo: solo.map(item),
    humano: esperan,
    nunca: [...nunca.map((f) => ({ titulo: nombreFamilia(f.familia) })),
      { titulo: "Cortar la conexión del MDR con los equipos", detalle: "el canal de gestión" }],
    certeza: conf?.certeza_minima ?? null,
    confianza: conf?.administradores.length
      ? `Se fía de ${conf.administradores.join(", ")} (administradores)${rafaga}` : null,
  }
}

// Los puertos intocables de un equipo: el candado de su fila en «Por zona y dispositivo».
export function intocablesDe(est: PoliticaEstado, activo: string): (number | string)[] {
  return (est.intocables ?? []).filter((i) => i.activo === activo && i.servicio != null).map((i) => i.servicio as number | string)
}
