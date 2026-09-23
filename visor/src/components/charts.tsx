import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
} from "recharts"
import { TINTA } from "@/theme"

export type Segmento = { name: string; value: number; fill: string }

// Donut de magnitud: total al centro, leyenda con cuentas (identidad nunca por color solo).
export function Donut({ data, total, unidad }: { data: Segmento[]; total: number; unidad: string }) {
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
      <div className="relative shrink-0">
        <ResponsiveContainer width={190} height={190}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={64} outerRadius={90} paddingAngle={2} strokeWidth={0}>
              {data.map((s, i) => <Cell key={i} fill={s.fill} />)}
            </Pie>
            <Tooltip formatter={(v, n) => [String(v), String(n)]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-semibold tabular-nums">{total}</span>
          <span className="text-xs text-muted-foreground">{unidad}</span>
        </div>
      </div>
      <ul className="w-full max-w-[180px] space-y-2 text-sm">
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
  const data = [{ value: pct, fill: color }, { value: 100 - pct, fill: "#e9e9e6" }]
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={170}>
        <PieChart>
          <Pie data={data} dataKey="value" startAngle={180} endAngle={0} cx="50%" cy="90%" innerRadius={72} outerRadius={98} strokeWidth={0}>
            {data.map((s, i) => <Cell key={i} fill={s.fill} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-x-0 bottom-3 flex flex-col items-center">
        <span className="text-4xl font-semibold tabular-nums">{pct}%</span>
        <span className="text-xs text-muted-foreground">{etiqueta}</span>
      </div>
    </div>
  )
}

// Tendencia: una serie, sin leyenda (el título la nombra). Un eje.
export function Tendencia({ data }: { data: { dia: string; n: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ left: -18, right: 10, top: 8, bottom: 0 }}>
        <CartesianGrid stroke="#ececea" vertical={false} />
        <XAxis dataKey="dia" tick={{ fontSize: 11, fill: TINTA.secondary }} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tick={{ fontSize: 11, fill: TINTA.secondary }} tickLine={false} axisLine={false} allowDecimals={false} width={28} />
        <Tooltip formatter={(v) => [String(v), "decisiones"]} />
        <Area type="monotone" dataKey="n" stroke="#2a78d6" fill="#2a78d6" fillOpacity={0.12} strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
