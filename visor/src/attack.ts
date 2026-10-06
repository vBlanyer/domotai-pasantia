// Referencia MITRE ATT&CK: dato ESTÁTICO (no de runtime). La API ya agrega el conteo por técnica
// (`metricas.mitre = [{tecnica, n}]`); aquí vive el único dato que falta para pintar la matriz: a qué
// TÁCTICA pertenece cada técnica y su nombre legible. Solo cubrimos las técnicas que el sistema
// reconoce de verdad (dataset + banco + reglas), no las ~200 de enterprise. Una técnica multitáctica
// se coloca en su táctica PRIMARIA según cómo la usa el prototipo (anotado donde aplica).

export type Tactica = { id: string; nombre: string }

// Columnas en el orden de la cadena de ataque ATT&CK enterprise (solo nuestras tácticas).
export const TACTICAS: Tactica[] = [
  { id: "reconnaissance", nombre: "Reconocimiento" },
  { id: "initial-access", nombre: "Acceso inicial" },
  { id: "execution", nombre: "Ejecución" },
  { id: "privilege-escalation", nombre: "Escalada de privilegios" },
  { id: "defense-evasion", nombre: "Evasión de defensas" },
  { id: "credential-access", nombre: "Acceso a credenciales" },
  { id: "discovery", nombre: "Descubrimiento" },
  { id: "lateral-movement", nombre: "Movimiento lateral" },
]

export const TECNICAS: Record<string, { nombre: string; tactica: string }> = {
  T1595: { nombre: "Escaneo activo", tactica: "reconnaissance" },
  "T1595.001": { nombre: "Escaneo de bloques IP", tactica: "reconnaissance" },
  "T1595.002": { nombre: "Escaneo de vulnerabilidades", tactica: "reconnaissance" },
  "T1595.003": { nombre: "Escaneo con diccionario", tactica: "reconnaissance" },
  T1190: { nombre: "Explotación de aplicación pública", tactica: "initial-access" },
  T1133: { nombre: "Servicios remotos externos", tactica: "initial-access" },
  // T1078 es multitáctica (también persistencia/evasión/escalada); como la usa el prototipo
  // —entrar con credenciales válidas— su táctica primaria es el acceso inicial.
  T1078: { nombre: "Cuentas válidas", tactica: "initial-access" },
  "T1078.001": { nombre: "Cuentas por defecto", tactica: "initial-access" },
  "T1078.003": { nombre: "Cuentas locales", tactica: "initial-access" },
  T1203: { nombre: "Explotación para ejecución en cliente", tactica: "execution" },
  T1211: { nombre: "Explotación para escalada de privilegios", tactica: "privilege-escalation" },
  // T1055 es multitáctica (evasión de defensas / escalada); su táctica primaria en ATT&CK es la
  // evasión de defensas. Aparece en trazas reales del banco, así que la cubrimos explícitamente.
  T1055: { nombre: "Inyección de procesos", tactica: "defense-evasion" },
  T1110: { nombre: "Fuerza bruta", tactica: "credential-access" },
  "T1110.001": { nombre: "Adivinación de contraseña", tactica: "credential-access" },
  "T1110.002": { nombre: "Descifrado de contraseña", tactica: "credential-access" },
  "T1110.003": { nombre: "Password spraying", tactica: "credential-access" },
  "T1110.004": { nombre: "Relleno de credenciales", tactica: "credential-access" },
  T1212: { nombre: "Explotación para acceso a credenciales", tactica: "credential-access" },
  T1046: { nombre: "Descubrimiento de servicios de red", tactica: "discovery" },
  T1021: { nombre: "Servicios remotos", tactica: "lateral-movement" },
  "T1021.001": { nombre: "Escritorio remoto (RDP)", tactica: "lateral-movement" },
  "T1021.002": { nombre: "SMB / recursos admin", tactica: "lateral-movement" },
  "T1021.004": { nombre: "SSH", tactica: "lateral-movement" },
  T1210: { nombre: "Explotación de servicios remotos", tactica: "lateral-movement" },
}

// Técnicas de una táctica, ordenadas por id (padre antes que subtécnicas por el orden lexicográfico).
export function tecnicasDe(tactica: string): string[] {
  return Object.keys(TECNICAS)
    .filter((t) => TECNICAS[t].tactica === tactica)
    .sort()
}
