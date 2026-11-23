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
// Acciones sobre la IP del atacante: las que `externos_desconocidos: con_analista` retiene (perfil.filtrar).
const SOBRE_EL_ORIGEN = new Set(["BLOQUEAR_IP", "BLOQUEAR_IP_FIREWALL", "MATAR_CONEXION"])
const ORIGEN: Record<string, string> = { fichero: "de politica.yml", perfil: "del perfil", consola: "de la consola", codigo: "del código" }

export function resumenPolitica(est: PoliticaEstado): ResumenPolitica {
  const conf = est.confianza
  const externosConAnalista = conf?.externos_desconocidos === "humano_siempre"
  const solo: Item[] = [], humano: Item[] = [], nunca: Item[] = []
  for (const f of est.familias) {
    const titulo = nombreFamilia(f.familia), accion = accionEnPalabras(f.accion, f.ruta)
    // Un freno del código es freno aunque la política le ponga «con analista».
    if (f.automatizacion === "nunca_automatica" || f.automatizacion_efectiva === "nunca_automatica") nunca.push({ titulo })
    else if (!SOLO.has(f.automatizacion_efectiva)) humano.push({ titulo, detalle: accion })
    else if (externosConAnalista && SOBRE_EL_ORIGEN.has(f.accion ?? "")) {
      humano.push({ titulo, detalle: `${accion} · con un atacante externo, espera a un analista` })
    } else solo.push({ titulo, detalle: accion })
  }

  const esperan: Item[] = [...humano]
  // Sin decirlo la política, bloquear lo propio exige analista (el motor lo aplica así por defecto).
  if (conf?.equipos_propios !== "automatica_si_confianza") esperan.push({ titulo: "Bloquear un equipo propio" })
  // Lo endurecido por zona o por equipo (la zona de gestión, protegida, ya va en «nunca»).
  for (const z of est.zonas) {
    if (!z.protegida && z.automatizacion === "humano_siempre") esperan.push({ titulo: `Zona ${z.zona}: todo espera a un analista` })
    for (const d of z.dispositivos) {
      if (!z.protegida && d.override === "humano_siempre") esperan.push({ titulo: `Equipo ${d.activo}: todo espera a un analista` })
    }
  }
  // Lo exacto de un intocable: no se CIERRA su puerto solo (bloquear al atacante puede seguir siendo automático).
  for (const i of est.intocables ?? []) {
    esperan.push({ titulo: [i.activo ?? "—", i.funcion].filter(Boolean).join(" · "),
      detalle: [`no se cierra el puerto ${i.servicio ?? "—"} en automático`, ORIGEN[i.origen]].filter(Boolean).join(" · ") })
  }
  if (conf?.vigilados === "humano_siempre") {
    esperan.push({ titulo: "Lo que venga de un origen en vigilancia", detalle: "la watchlist («Revertir y vigilar»)" })
  }
  if (conf?.revisar_desde_nivel != null) {
    esperan.push({ titulo: `Alertas que no reconoce, de nivel ${conf.revisar_desde_nivel} o más`, detalle: "a revisión, sin acción" })
  }

  const rafaga = conf?.rafaga ? ` salvo ráfaga de ${conf.rafaga.alertas} alertas en ${conf.rafaga.en_segundos} s` : ""
  return {
    frase: `De ${est.familias.length} tipos de ataque, el MDR contiene ${solo.length} solo (si está seguro), ` +
      `deja ${humano.length} a un analista y ${nunca.length} nunca los toca solo. Todo lo que hace se puede deshacer.`,
    solo,
    humano: esperan,
    nunca: [...nunca, { titulo: "Cortar la conexión del MDR con los equipos", detalle: "el canal de gestión" }],
    certeza: conf?.certeza_minima ?? null,
    confianza: conf?.administradores.length
      ? `Se fía de ${conf.administradores.join(", ")} (administradores)${rafaga}` : null,
  }
}

// Los puertos intocables de un equipo: el candado de su fila en «Por zona y dispositivo».
export function intocablesDe(est: PoliticaEstado, activo: string): (number | string)[] {
  return (est.intocables ?? []).filter((i) => i.activo === activo && i.servicio != null).map((i) => i.servicio as number | string)
}
