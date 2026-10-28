import { useSondeo, getPolitica, type PoliticaFamilia } from "@/api"
import { Cargando, SinConexion, Vacio } from "@/components/bits"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { etiquetaClase, pasosRunbook } from "@/datos"

// Etiqueta + color del nivel de automatización (transparencia del playbook).
const AUTO: Record<string, { txt: string; cls: string }> = {
  automatica: { txt: "automática", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  automatica_si_confianza: { txt: "auto si confianza ≥ umbral", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  requiere_humano: { txt: "requiere humano", cls: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
  nunca_automatica: { txt: "nunca automática", cls: "bg-rose-500/15 text-rose-700 dark:text-rose-300" },
}

// Vista «Políticas»: el playbook del MDR, de solo lectura. Para cada familia muestra qué clase de
// amenaza representa, qué acción del catálogo cerrado se propone, con qué nivel de automatización la
// trata el perfil del cliente, y las condiciones/vetos. Derivado del catálogo + el perfil (GET
// /api/politica); los matices por actor/IP se refinan en tiempo de ejecución (nota honesta).
export function Politicas() {
  const t = useSondeo(getPolitica)
  if (!t) return <Cargando />
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const filas: PoliticaFamilia[] = fallo ? (fallo.datos ?? []) : (t as PoliticaFamilia[])
  if (filas.length === 0) return <Vacio>Sin políticas que mostrar.</Vacio>
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        El <strong>playbook</strong> del MDR, de solo lectura: por familia de amenaza, la clase que representa,
        la acción del <strong>catálogo cerrado</strong> que se propone, cómo la trata el perfil del cliente
        (automática / humana) y sus vetos. Los matices por <strong>actor/IP</strong> (terceros de confianza,
        externo desconocido, excepciones por activo) se refinan en tiempo de ejecución.
      </p>
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Familia</TableHead><TableHead>Clase</TableHead><TableHead>Acción</TableHead>
              <TableHead>Automatización</TableHead><TableHead>Condiciones / vetos</TableHead>
              <TableHead>Playbook</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filas.map((f) => {
              const a = AUTO[f.automatizacion] ?? { txt: f.automatizacion, cls: "bg-muted" }
              const pasos = pasosRunbook(f.clase_tipica)
              return (
                <TableRow key={f.familia} className="hover:bg-transparent align-top">
                  <TableCell>
                    <span className="font-medium">{f.familia}</span>
                    {f.mitre.length > 0 && (
                      <span className="ml-1 text-xs text-muted-foreground" title="Técnicas MITRE ATT&CK">{f.mitre.join(", ")}</span>
                    )}
                    {f.nivel === "triar_y_enrutar" && (
                      <span className="block text-xs text-muted-foreground">enruta a {f.ruta ?? "—"} (no contiene)</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs">{etiquetaClase(f.clase_tipica)}</TableCell>
                  <TableCell className="text-xs font-mono">
                    {f.accion ?? "—"}
                    {f.impacto && <span className="block text-muted-foreground">impacto: {f.impacto}</span>}
                  </TableCell>
                  <TableCell>
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${a.cls}`}>{a.txt}</span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {f.vetos.length === 0 ? "—" : (
                      <ul className="list-disc space-y-0.5 pl-4">{f.vetos.map((v, i) => <li key={i}>{v}</li>)}</ul>
                    )}
                  </TableCell>
                  <TableCell className="text-xs">
                    {pasos.length === 0 && !f.recomendacion ? "—" : (
                      <details>
                        <summary className="cursor-pointer text-muted-foreground hover:underline">ver</summary>
                        {f.recomendacion?.respuesta && (
                          <div className="mt-1">Respuesta recomendada: <span className="font-medium">{f.recomendacion.respuesta}</span>
                            {f.recomendacion.nota ? ` — ${f.recomendacion.nota}` : ""}</div>
                        )}
                        {pasos.length > 0 && (
                          <ol className="mt-1 list-decimal space-y-0.5 pl-4">{pasos.map((p, i) => <li key={i}>{p}</li>)}</ol>
                        )}
                      </details>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
