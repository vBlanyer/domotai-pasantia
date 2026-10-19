// Referencia MITRE ATT&CK: dato ESTÁTICO (no de runtime). La matriz es una vista de COBERTURA POR
// FAMILIA: la API agrega `metricas.mitre = [{tecnica, n}]` expandiendo cada decisión a TODAS las
// técnicas que declara su familia (`prototipo/familias.yml`), no la subtécnica concreta que puso
// Wazuh. Por eso aquí vive EXACTAMENTE el conjunto de técnicas de las 8 familias (ni más —no las ~200
// de enterprise ni subtécnicas aspiracionales— ni menos): así un ataque por familia enciende su
// columna entera y la matriz refleja la cobertura real del MDR. DEBE mantenerse en sync con los
// campos `mitre` de familias.yml (hoy 10 familias). Cada técnica se coloca en su táctica ATT&CK.

export type Tactica = { id: string; nombre: string }

// Columnas en el orden de la cadena de ataque ATT&CK enterprise (solo nuestras tácticas).
export const TACTICAS: Tactica[] = [
  { id: "reconnaissance", nombre: "Reconocimiento" },
  { id: "initial-access", nombre: "Acceso inicial" },
  { id: "execution", nombre: "Ejecución" },
  { id: "persistence", nombre: "Persistencia" },
  { id: "privilege-escalation", nombre: "Escalada de privilegios" },
  { id: "defense-evasion", nombre: "Evasión de defensas" },
  { id: "credential-access", nombre: "Acceso a credenciales" },
  { id: "discovery", nombre: "Descubrimiento" },
  { id: "lateral-movement", nombre: "Movimiento lateral" },
  { id: "command-and-control", nombre: "Mando y control" },
  { id: "exfiltration", nombre: "Exfiltración" },
  { id: "impact", nombre: "Impacto" },
]

// Las 19 técnicas de las 10 familias (familias.yml). Multitáctica -> táctica primaria según el uso.
export const TECNICAS: Record<string, { nombre: string; tactica: string }> = {
  // reconocimiento
  T1595: { nombre: "Escaneo activo", tactica: "reconnaissance" },
  T1046: { nombre: "Descubrimiento de servicios de red", tactica: "discovery" },
  // acceso_credenciales (T1078 multitáctica; su uso aquí —entrar con credenciales válidas— es acceso inicial)
  T1110: { nombre: "Fuerza bruta", tactica: "credential-access" },
  T1078: { nombre: "Cuentas válidas", tactica: "initial-access" },
  // servicio_expuesto / explotacion_conocida
  T1190: { nombre: "Explotación de aplicación pública", tactica: "initial-access" },
  T1203: { nombre: "Explotación para ejecución en cliente", tactica: "execution" },
  T1210: { nombre: "Explotación de servicios remotos", tactica: "lateral-movement" },
  // acceso_consumado (intrusión exitosa / sesión activa del atacante): T1078 (arriba) + T1021.
  T1021: { nombre: "Servicios remotos (sesión)", tactica: "lateral-movement" },
  // abuso_de_cuenta (escalada / manipulación de cuentas; T1548/T1098 multitáctica, táctica primaria)
  T1548: { nombre: "Abuso de mecanismo de elevación (sudo)", tactica: "privilege-escalation" },
  T1136: { nombre: "Crear cuenta", tactica: "persistence" },
  T1098: { nombre: "Manipulación de cuentas", tactica: "persistence" },
  // integridad_fichero (FIM)
  T1565: { nombre: "Manipulación de datos", tactica: "impact" },
  T1070: { nombre: "Borrado de indicadores", tactica: "defense-evasion" },
  // denegacion_servicio (DoS)
  T1498: { nombre: "Denegación de servicio de red", tactica: "impact" },
  T1499: { nombre: "Denegación de servicio de endpoint", tactica: "impact" },
  // exfiltracion / C2 (T1041 exfiltración sobre el canal de C2; T1071 protocolo de capa de aplicación)
  T1041: { nombre: "Exfiltración sobre el canal de C2", tactica: "exfiltration" },
  T1071: { nombre: "Protocolo de capa de aplicación (C2)", tactica: "command-and-control" },
  // malware / rootkit (T1014 rootkit; T1486 datos cifrados para impacto / ransomware)
  T1014: { nombre: "Rootkit", tactica: "defense-evasion" },
  T1486: { nombre: "Datos cifrados para impacto", tactica: "impact" },
}

// Técnicas de una táctica, ordenadas por id (padre antes que subtécnicas por el orden lexicográfico).
export function tecnicasDe(tactica: string): string[] {
  return Object.keys(TECNICAS)
    .filter((t) => TECNICAS[t].tactica === tactica)
    .sort()
}
