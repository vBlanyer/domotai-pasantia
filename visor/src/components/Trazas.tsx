import { useEffect, useState, type ReactNode } from "react"
import { RefreshCw } from "lucide-react"
import { useSondeo, getTrazas, getVerificacion, type Decision } from "@/api"
import { Button } from "@/components/ui/button"
import { Cargando, SinConexion, Vacio, Punto, BarraFiltros, DatosCongelados } from "./bits"
import { OrigenBadges } from "./OrigenBadges"
import { filtrarDecisiones, clasesDe, claveDe, ventanaDe, paginar, etiquetaClase, campanasDe, TAM_PAGINA, type Filtro, quienDecidio } from "@/datos"
import {
  CHIPS, tipoDe, filtrarTipo, hashCorto, horaLocal, claveDia, etiquetaDia, describirSistema, marcaDe, pruebaDe, campanaDe,
  type Chip, type TipoFila, type Marca,
} from "@/trazas"
import { edadTexto } from "@/alertas"
import { Paginador } from "./Paginador"
import { cn } from "@/lib/utils"

// Resultado de la última verificación de la cadena (recorre el fichero entero en el servidor).
type Cadena = { ok: boolean; roto: number | null; motivo?: string; en: number; conexion: boolean } | null
const CADA_MS = 30000   // A5: verificar recorre TODO el fichero; cada 30 s basta (como en el Panel)

const NODO: Record<TipoFila, string> = {
  decision: "border-primary bg-primary", humano: "border-aviso bg-aviso", sistema: "border-enrutado bg-card", error: "border-critico bg-critico",
}
const MARCA: Record<Marca, { s: string; cls: string; titulo: string }> = {
  ok: { s: "✓", cls: "text-ok", titulo: "encadenado y verificado" },
  roto: { s: "✗", cls: "font-semibold text-critico", titulo: "alterado: el contenido no produce el hash guardado" },
  tras: { s: "⚠", cls: "text-aviso", titulo: "posterior a la rotura: cuelga de un eslabón alterado" },
}

function Pildora({ tono, children }: { tono: "auto" | "hum" | "sys" | "rev" | "err"; children: ReactNode }) {
  const cls = { auto: "bg-ok/15 text-ok", hum: "bg-aviso/15 text-aviso", sys: "bg-enrutado/15 text-enrutado",
                rev: "bg-violeta/15 text-violeta", err: "bg-critico/15 text-critico" }[tono]
  return <span className={cn("whitespace-nowrap rounded px-1.5 py-px text-[11px] font-medium", cls)}>{children}</span>
}

// Quién decidió: automática, o el veredicto del analista (no repudio) o la espera.
function PildoraDecision({ r, tipo }: { r: Decision; tipo: TipoFila }) {
  if (tipo === "error") return <Pildora tono="err">error</Pildora>
  if (tipo === "sistema") return r.tipo === "reversion" ? <Pildora tono="rev">{r.exito ? "aplicada" : "falló"}</Pildora> : <Pildora tono="sys">sistema</Pildora>
  if (tipo === "humano") return <Pildora tono="hum">{quienDecidio(r) ?? "pendiente de humano"}</Pildora>
  return <Pildora tono="auto">automática</Pildora>
}

function Seccion({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3 last:border-b-0">
      <h4 className="mb-2 text-[11px] font-medium text-muted-foreground">{titulo}</h4>
      {children}
    </div>
  )
}
function KV({ k, children }: { k: string; children: ReactNode }) {
  return <><span className="text-muted-foreground">{k}</span><span className="min-w-0 [overflow-wrap:anywhere]">{children}</span></>
}

// Una línea de la prueba de la cadena: etiqueta, valor (hash completo) y su marca.
function FilaPrueba({ k, v, estado }: { k: string; v: string | null; estado?: "ok" | "bad" | "nulo" }) {
  return (
    <div className={cn("grid grid-cols-[96px_1fr_auto] items-center gap-2 rounded-md bg-muted px-2 py-1.5", estado === "bad" && "bg-critico/10")}>
      <span className="font-sans text-[11px] text-muted-foreground">{k}</span>
      <span className={cn("[overflow-wrap:anywhere]", estado === "bad" && "text-critico", v == null && "text-muted-foreground")}>{v ?? "fuera de la ventana mostrada"}</span>
      <span className={cn("text-xs", estado === "ok" ? "text-ok" : estado === "bad" ? "font-semibold text-critico" : "text-muted-foreground")}>
        {estado === "ok" ? "✓" : estado === "bad" ? "✗" : estado === "nulo" ? "?" : ""}
      </span>
    </div>
  )
}

// El inspector: todo lo de UN registro, incluida la prueba de la cadena, sin desplegar nada.
function Inspector({ r, i, anterior, cadena, revertidaPor, revierte, enCampana, onVerDecision, onVerIncidente }: {
  r: Decision; i: number; anterior?: Decision; cadena: Cadena; revertidaPor?: { i: number; r: Decision }; revierte?: Decision
  enCampana: boolean; onVerDecision?: (id: string) => void; onVerIncidente?: (clave: string, cidr: string) => void
}) {
  const [copiado, setCopiado] = useState(false)
  const tipo = tipoDe(r)
  const marca = marcaDe(i, cadena)
  const prueba = pruebaDe(r, anterior)
  const sistema = tipo === "sistema" || tipo === "error" ? describirSistema(r) : null
  const camp = campanaDe(r.origen_ip)
  const copiar = () => {
    try {
      navigator.clipboard?.writeText(JSON.stringify(r, null, 2)).then(() => { setCopiado(true); setTimeout(() => setCopiado(false), 2000) }).catch(() => {})
    } catch { /* sin portapapeles */ }
  }
  const veredicto = marca === null ? <span className="text-muted-foreground">Verificando la cadena…</span>
    : marca === "ok" ? <span className="text-ok">Encadenado y verificado: el contenido produce el hash guardado y enlaza con el anterior.</span>
    : marca === "roto" ? <span className="text-critico">{cadena?.motivo ?? "El contenido no produce el hash guardado"}: fue modificado después de escribirse. Todo lo posterior cuelga de un eslabón alterado.</span>
    : <span className="text-aviso">Posterior a la rotura en #{(cadena?.roto ?? 0) + 1}: enlaza con su anterior, pero cuelga de un eslabón alterado.</span>
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card text-sm lg:sticky lg:top-3">
      <div className="border-b border-border bg-muted px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground">
          <span>Registro <span className="font-mono text-foreground">#{i + 1}</span></span><span>·</span>
          <span className="font-mono">{r.timestamp ?? "—"}</span>
          {r.id_decision && <><span>·</span><span>id <span className="font-mono text-foreground">{r.id_decision}</span></span></>}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-2 font-semibold">
          {sistema ? sistema.titulo : <>{r.activo ?? "—"} · {r.clase ? etiquetaClase(r.clase) : "—"} → {r.accion_final ?? "—"}</>}
          <PildoraDecision r={r} tipo={tipo} />
          {marca === "roto" && <Pildora tono="err">alterado</Pildora>}
        </div>
      </div>

      {sistema ? (
        <Seccion titulo="Registro">
          <div className="grid grid-cols-[96px_1fr] gap-x-3 gap-y-1">
            <KV k="Qué pasó">{sistema.detalle || "—"}</KV>
            {revierte && <KV k="Revierte">#{(revierte.indice ?? 0) + 1} · {revierte.activo ?? "—"} · {revierte.accion_final ?? "—"}</KV>}
            {r.tipo === "error" && r.error && <KV k="Error"><span className="font-mono text-xs text-critico">{r.error}</span></KV>}
          </div>
        </Seccion>
      ) : (
        <Seccion titulo="Decisión">
          <div className="grid grid-cols-[96px_1fr] gap-x-3 gap-y-1">
            <KV k="Clase"><span className="font-mono text-xs">{r.clase ?? "—"}</span>{r.confianza != null && <> · confianza <b className="font-semibold">{r.confianza}</b></>}{r.prioridad != null && <> · prioridad P{r.prioridad}</>}</KV>
            <KV k="Acción"><b className="font-semibold">{r.accion_final ?? "—"}</b>{r.dispositivo && <> en {r.dispositivo}</>}{r.impacto && <> · impacto {r.impacto}</>}
              {r.accion_propuesta && r.accion_propuesta !== r.accion_final && <span className="text-muted-foreground"> · propuesta: {r.accion_propuesta}</span>}</KV>
            <KV k="Decidió">{tipo === "humano" ? (quienDecidio(r) ?? "pendiente de humano") : "automática"}
              {tipo === "humano" && r.decidido_en && <span className="text-muted-foreground"> · {new Date(r.decidido_en).toLocaleTimeString("es")}</span>}
              {r.resultado_filtro && <span className="text-muted-foreground"> · filtro del perfil: {r.resultado_filtro}</span>}</KV>
            {r.tecnica_mitre?.length ? <KV k="ATT&CK"><span className="inline-flex flex-wrap gap-1">{r.tecnica_mitre.map((t) => <span key={t} className="rounded bg-muted px-1.5 font-mono text-[10px]">{t}</span>)}</span></KV> : null}
            {r.motivo && <KV k="Motivo">{r.motivo}</KV>}
          </div>
        </Seccion>
      )}

      {r.origen_ip && (
        <Seccion titulo="Origen">
          <div className="flex flex-wrap items-center gap-2"><b className="font-semibold">{r.origen_ip}</b>{r.enriquecimiento_origen && <OrigenBadges e={r.enriquecimiento_origen} />}</div>
        </Seccion>
      )}

      <Seccion titulo="Integridad de la cadena">
        <div className="flex flex-col gap-1.5 font-mono text-[11.5px]">
          <FilaPrueba k="hash_previo" v={prueba.previo === "0".repeat(64) ? "génesis" : prueba.previo} />
          <FilaPrueba k={`hash de #${i}`} v={i === 0 ? "no hay: es el primer registro" : prueba.hashAnterior} estado={prueba.enlaza === true ? "ok" : prueba.enlaza === false ? "bad" : "nulo"} />
          <FilaPrueba k="hash guardado" v={prueba.guardado} estado={marca === "roto" ? "bad" : marca === "ok" ? "ok" : undefined} />
          {prueba.enlaza === false && <div className="font-sans text-xs text-critico">El hash previo no coincide con el hash del registro anterior.</div>}
          <div className="mt-1 font-sans text-xs">{veredicto}</div>
        </div>
      </Seccion>

      <Seccion titulo="Relacionado">
        {revertidaPor && (
          <div className="mb-2 grid grid-cols-[96px_1fr] gap-x-3"><KV k="Revertida por">#{revertidaPor.i + 1} · {revertidaPor.r.exito ? "aplicada" : "falló"} a las {horaLocal(revertidaPor.r.timestamp)}{revertidaPor.r.nodo && <> en {revertidaPor.r.nodo}</>}</KV></div>
        )}
        <div className="flex flex-wrap gap-3 text-xs font-medium">
          {r.id_decision && onVerDecision && <button onClick={() => onVerDecision(r.id_decision!)} className="text-info hover:underline">Ver en Decisiones</button>}
          {camp && enCampana && onVerIncidente && <button onClick={() => onVerIncidente(camp.clave, camp.cidr)} className="text-info hover:underline">Ver el incidente</button>}
          <button onClick={copiar} className="text-info hover:underline">{copiado ? "Copiado" : "Copiar el registro (JSON)"}</button>
        </div>
      </Seccion>
    </div>
  )
}

export function Trazas({ onVerDecision, onVerIncidente }: { onVerDecision?: (id: string) => void; onVerIncidente?: (clave: string, cidr: string) => void }) {
  const t = useSondeo(getTrazas)
  const [cadena, setCadena] = useState<Cadena>(null)
  const [filtro, setFiltro] = useState<Filtro>({ texto: "", clase: "" })
  const [chip, setChip] = useState<Chip>("todo")
  const [pagina, setPagina] = useState(1)
  const [tam, setTam] = useState(TAM_PAGINA)
  const [sel, setSel] = useState<number | null>(null)      // registro seleccionado, por posición en la cadena
  const [ahora, setAhora] = useState(() => Date.now())     // «hace X» y «hoy» sin leer el reloj en el render
  // Al cambiar el filtro la lista cambia de tamaño: se vuelve a la primera página.
  useEffect(() => setPagina(1), [filtro.texto, filtro.clase, chip])
  const elegirTam = (t: number) => { setTam(t); setPagina(1) }

  const aplicar = (r: Awaited<ReturnType<typeof getVerificacion>>) => {
    const en = Date.now()
    if ("error" in r) return setCadena((c) => ({ ok: c?.ok ?? true, roto: c?.roto ?? null, motivo: c?.motivo, en, conexion: false }))
    if (typeof r.ok !== "boolean") return
    setCadena({ ok: r.ok, roto: r.ok ? null : (r.roto_en ?? 0), motivo: r.motivo, en, conexion: true })
    // Si hay rotura y nadie ha elegido registro, el inspector abre el eslabón alterado.
    if (!r.ok && r.roto_en != null) setSel((s) => s ?? r.roto_en!)
  }
  const verificarAhora = () => { getVerificacion().then(aplicar) }
  // La cadena se verifica sola al entrar y cada 30 s; el botón es «ahora». El reloj avanza cada 5 s
  // para «verificada hace X». No usa useSondeo: el resultado lleva su propia hora y el test lo mockea.
  useEffect(() => {
    let vivo = true
    const tick = () => { getVerificacion().then((r) => { if (vivo) aplicar(r) }) }
    tick()
    const id = setInterval(tick, CADA_MS)
    const reloj = setInterval(() => setAhora(Date.now()), 5000)
    return () => { vivo = false; clearInterval(id); clearInterval(reloj) }
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps -- aplicar solo envuelve setCadena/setSel

  if (!t) return <Cargando />
  // C2: con la conexión perdida pero datos previos, la cadena se muestra congelada con aviso.
  const fallo = "error" in t ? t : null
  if (fallo && !fallo.datos) return <SinConexion causa={fallo.causa} />
  const regs: Decision[] = fallo ? fallo.datos! : t as Decision[]
  // Se filtra preservando el índice real de la cadena (para el # y la marca de integridad):
  // filtrarDecisiones conserva las referencias, así que basta un Set por identidad.
  const enFiltro = new Set(filtrarTipo(filtrarDecisiones(regs, filtro), chip))
  // `i` es la posición en la cadena completa (el backend la anota): la ventana puede empezar a mitad.
  const todas = regs.map((r, k) => ({ r, k, i: r.indice ?? k }))
  const filas = todas.filter(({ r }) => enFiltro.has(r))
  const pag = paginar(filas, pagina, tam)
  const ventana = ventanaDe(regs)
  const rotoFuera = !!ventana && cadena?.roto != null && cadena.roto < ventana.desde
  const hoy = claveDia(new Date(ahora).toISOString())
  const porIndice = new Map(todas.map((f) => [f.i, f]))
  const seleccionada = sel != null ? porIndice.get(sel) : undefined
  const prefijos = new Set(campanasDe(regs).map((c) => c.prefijo))

  return (
    <div className="space-y-3">
      {fallo && <DatosCongelados fallo={fallo} />}

      {/* Franja de estado: siempre a la vista, no detrás de un botón. */}
      <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border px-4 py-3 text-sm",
        cadena && !cadena.ok ? "border-critico/40 bg-critico/10" : "border-border bg-card")}>
        <span className="inline-flex items-center gap-2 font-medium">
          {!cadena
            ? <><Punto estado="pendiente" /><span className="text-muted-foreground">Verificando la cadena…</span></>
            : cadena.ok
              ? <><Punto estado="ok" /><span className="text-ok">Cadena íntegra</span></>
              : <><Punto estado="caido" /><span className="text-critico">Cadena rota en el registro #{(cadena.roto ?? 0) + 1}</span></>}
        </span>
        <span className="text-xs text-muted-foreground">
          {cadena && !cadena.ok && cadena.motivo && <>{cadena.motivo} · </>}
          {ventana && <>{`mostrando los últimos ${ventana.mostrados} de ${ventana.total} registros`} · </>}
          {cadena && <>verificada {edadTexto(ahora - cadena.en)}, cada 30 s{!cadena.conexion && " · sin conexión en el último intento"}</>}
        </span>
        <Button size="sm" variant="secondary" className="ml-auto" onClick={verificarAhora}>
          <RefreshCw className="size-3.5" /> Verificar ahora
        </Button>
      </div>
      {rotoFuera && cadena?.roto != null && (
        <p className="text-xs font-medium text-critico">
          El registro alterado (#{cadena.roto + 1}) queda fuera de los mostrados: la lista solo incluye los últimos {ventana?.mostrados}.
        </p>
      )}

      {regs.length === 0 ? (
        <Vacio>La traza está vacía. Cada decisión aparecerá aquí, encadenada por hash.</Vacio>
      ) : (
        <>
        <div className="flex flex-wrap items-center gap-2">
          <BarraFiltros f={filtro} set={setFiltro} clases={clasesDe(regs)} cuenta={filas.length} />
          <div role="group" aria-label="Tipo de registro" className="flex gap-1">
            {CHIPS.map((c) => (
              <button key={c.id} onClick={() => setChip(c.id)} aria-pressed={chip === c.id}
                className={cn("rounded-full border px-2.5 py-0.5 text-xs transition-colors",
                  chip === c.id ? "border-primary/45 bg-primary/12 font-medium text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
                {c.nombre}
              </button>
            ))}
          </div>
        </div>

        <div className="grid items-start gap-3.5 lg:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
          {/* lista densa: una línea por registro, con su marca de integridad */}
          <div>
            <div className="overflow-hidden rounded-lg border border-border bg-card">
              {pag.filas.map(({ r, k, i }, n) => {
                const tipo = tipoDe(r)
                const marca = marcaDe(i, cadena)
                const dia = claveDia(r.timestamp)
                const nuevoDia = n === 0 || dia !== claveDia(pag.filas[n - 1].r.timestamp)
                const sistema = tipo === "sistema" || tipo === "error" ? describirSistema(r) : null
                const activa = sel === i
                return (
                  <div key={claveDe(r, k)}>
                    {nuevoDia && dia && <div className="border-b border-border bg-muted px-3.5 py-1 text-[11px] text-muted-foreground">{etiquetaDia(dia, hoy)}</div>}
                    <button data-fila={i + 1} aria-pressed={activa} onClick={() => setSel(i)}
                      className={cn("grid h-[38px] w-full grid-cols-[18px_64px_16px_minmax(0,1fr)_auto_84px] items-center gap-2.5 border-b border-l-[3px] border-border border-l-transparent px-3 text-left text-sm transition-colors last:border-b-0 hover:bg-muted/50",
                        marca === "roto" && "bg-critico/10", activa && "bg-primary/10 border-l-primary", activa && marca === "roto" && "border-l-critico")}>
                      <span className={cn("text-center text-xs", marca && MARCA[marca].cls)} title={marca ? MARCA[marca].titulo : "sin verificar"}>{marca ? MARCA[marca].s : ""}</span>
                      <span className="font-mono text-xs tabular-nums text-muted-foreground" title={r.timestamp ?? undefined}>{horaLocal(r.timestamp)}</span>
                      <span aria-hidden className={cn("size-2.5 justify-self-center rounded-full border-2", marca === "roto" ? NODO.error : NODO[tipo])} />
                      <span className="min-w-0 truncate">
                        {sistema
                          ? <span className="text-muted-foreground">{sistema.titulo}{sistema.detalle && <> · {sistema.detalle}</>}</span>
                          : <><b className="font-semibold">{r.activo ?? "—"}</b><span className="mx-1 text-muted-foreground">·</span>{r.clase ? etiquetaClase(r.clase) : "—"}<span className="mx-1 text-muted-foreground">→</span><b className="font-semibold">{r.accion_final ?? "—"}</b></>}
                      </span>
                      {marca === "roto" ? <Pildora tono="err">alterado</Pildora> : <PildoraDecision r={r} tipo={tipo} />}
                      <span className="text-right font-mono text-xs text-muted-foreground" title={r.hash ?? undefined}>
                        <span className="text-muted-foreground/60">#{i + 1}</span> <span className={cn(marca === "roto" && "text-critico")}>{hashCorto(r.hash) ?? "—"}</span>
                      </span>
                    </button>
                  </div>
                )
              })}
            </div>
            <Paginador pagina={pag.pagina} paginas={pag.paginas} total={pag.total} tam={tam} onPagina={setPagina} onTam={elegirTam} />
          </div>

          {/* inspector */}
          {seleccionada ? (
            <Inspector r={seleccionada.r} i={seleccionada.i} anterior={porIndice.get(seleccionada.i - 1)?.r} cadena={cadena}
              revertidaPor={seleccionada.r.id_decision ? todas.find((f) => f.r.tipo === "reversion" && f.r.id_decision_revertida === seleccionada.r.id_decision) : undefined}
              revierte={seleccionada.r.tipo === "reversion" && seleccionada.r.indice_revertido != null ? porIndice.get(seleccionada.r.indice_revertido)?.r : undefined}
              enCampana={!!campanaDe(seleccionada.r.origen_ip) && prefijos.has(campanaDe(seleccionada.r.origen_ip)!.prefijo)}
              onVerDecision={onVerDecision} onVerIncidente={onVerIncidente} />
          ) : (
            <div className="rounded-lg border border-dashed border-border bg-card px-4 py-5 text-sm text-muted-foreground lg:sticky lg:top-3">
              {sel != null ? `El registro #${sel + 1} no está en la ventana mostrada.` : "Selecciona un registro para ver su detalle y la prueba de la cadena."}
            </div>
          )}
        </div>
        </>
      )}
    </div>
  )
}
