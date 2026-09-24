import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from "recharts"
import { ejes } from "@/theme"
import { useTema } from "@/tema"

export type Segmento = { name: string; value: number; fill: string }

// Ranking de magnitud: barras horizontales, UNA serie (un solo hue, no categórico). El título la
// nombra, así que no lleva leyenda; la etiqueta va en el eje y el valor a la derecha de cada barra.
export function Barras({ data }: { data: { nombre: string; n: number }[] }) {
  const { grid, texto, serie } = ejes(useTema().oscuro)
  const alto = Math.max(120, data.length * 34 + 16)
  return (
    <ResponsiveContainer width="100%" height={alto}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 28, top: 4, bottom: 4 }}>
        <CartesianGrid stroke={grid} horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: texto }} tickLine={false} axisLine={false} allowDecimals={false} />
        <YAxis type="category" dataKey="nombre" width={112} tick={{ fontSize: 11, fill: texto }} tickLine={false} axisLine={false} />
        <Tooltip formatter={(v) => [String(v), "incidentes"]} cursor={{ fill: grid }} />
        <Bar dataKey="n" fill={serie} radius={[0, 3, 3, 0]} barSize={16} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

// Donut de magnitud: total al centro, leyenda con cuentas (identidad nunca por color solo).
export function Donut({ data, total, unidad }: { data: Segmento[]; total: number; unidad: string }) {
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:flex-wrap sm:justify-center">
      <div className="relative aspect-square w-full max-w-[190px] min-w-[120px] shrink">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius="66%" outerRadius="94%" paddingAngle={2} strokeWidth={0} isAnimationActive={false}>
              {data.map((s, i) => <Cell key={i} fill={s.fill} />)}
            </Pie>
            <Tooltip formatter={(v, n) => [String(v), String(n)]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-heading text-3xl font-semibold tabular-nums">{total}</span>
          <span className="text-xs text-muted-foreground">{unidad}</span>
        </div>
      </div>
      <ul className="w-full min-w-0 max-w-[180px] space-y-2 text-sm">
        {data.map((s) => (
          <li key={s.name} className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: s.fill }} />
            <span className="flex-1 truncate text-muted-foreground">{s.name}</span>
            <span className="font-medium tabular-nums">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// Medidor semicircular: un porcentaje (p. ej. servicios operativos), estilo comercial.
export function Gauge({ pct, color, etiqueta }: { pct: number; color: string; etiqueta: string }) {
  const { oscuro } = useTema()
  const data = [{ value: pct, fill: color }, { value: 100 - pct, fill: ejes(oscuro).relleno }]
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={170}>
        <PieChart>
          <Pie data={data} dataKey="value" startAngle={180} endAngle={0} cx="50%" cy="90%" innerRadius={72} outerRadius={98} strokeWidth={0} isAnimationActive={false}>
            {data.map((s, i) => <Cell key={i} fill={s.fill} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-x-0 bottom-3 flex flex-col items-center">
        <span className="font-heading text-4xl font-semibold tabular-nums">{pct}%</span>
        <span className="text-xs text-muted-foreground">{etiqueta}</span>
      </div>
    </div>
  )
}

// Tendencia: una serie, sin leyenda (el título la nombra). Un eje.
export function Tendencia({ data }: { data: { dia: string; n: number }[] }) {
  const { grid, texto, serie } = ejes(useTema().oscuro)
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ left: -18, right: 10, top: 8, bottom: 0 }}>
        <CartesianGrid stroke={grid} vertical={false} />
        <XAxis dataKey="dia" tick={{ fontSize: 11, fill: texto }} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tick={{ fontSize: 11, fill: texto }} tickLine={false} axisLine={false} allowDecimals={false} width={28} />
        <Tooltip formatter={(v) => [String(v), "decisiones"]} />
        <Area type="monotone" dataKey="n" stroke={serie} fill={serie} fillOpacity={0.14} strokeWidth={2} dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
