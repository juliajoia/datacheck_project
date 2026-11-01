import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { SEVERITY_COLOR } from "@/components/SeverityBadge";
import { fmtDay } from "@/utils/format";
import type { Severity } from "@/types";

const tooltipStyle = {
  contentStyle: { background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 10, fontSize: 12 },
  itemStyle: { color: "hsl(var(--foreground))" }, labelStyle: { color: "hsl(var(--foreground))", fontWeight: 600 },
  cursor: { fill: "hsl(var(--muted) / 0.6)" },
};
const axis = { stroke: "hsl(var(--muted-foreground))", fontSize: 12, tickLine: false, axisLine: false } as const;
const truncate = (s: string, n = 22) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

export function HorizontalBars({ data, color = "hsl(var(--primary))", unit = "ocorrências" }: {
  data: { name: string; value: number }[]; color?: string; unit?: string;
}) {
  const height = Math.max(180, data.length * 38 + 20);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
        <CartesianGrid horizontal={false} stroke="hsl(var(--border))" />
        <XAxis type="number" allowDecimals={false} {...axis} />
        <YAxis type="category" dataKey="name" width={150} tickFormatter={(v: string) => truncate(v)} {...axis} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toLocaleString("pt-BR")} ${unit}`, ""]} />
        <Bar dataKey="value" fill={color} radius={[0, 6, 6, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SeverityDonut({ data }: { data: { severity: Severity; label: string; count: number }[] }) {
  const items = data.filter((d) => d.count > 0);
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={items} dataKey="count" nameKey="label" innerRadius={55} outerRadius={85} paddingAngle={3} stroke="none">
          {items.map((d) => <Cell key={d.severity} fill={SEVERITY_COLOR[d.severity]} />)}
        </Pie>
        <Tooltip {...tooltipStyle} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function AffectedDonut({ affected, clean }: { affected: number; clean: number }) {
  const data = [{ name: "Com inconsistências", value: affected, color: "hsl(var(--destructive))" },
    { name: "Sem inconsistências", value: clean, color: "hsl(var(--success))" }];
  const total = affected + clean;
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius={55} outerRadius={85} paddingAngle={3} stroke="none">
            {data.map((d) => <Cell key={d.name} fill={d.color} />)}
          </Pie>
          <Tooltip {...tooltipStyle} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-x-0 top-[88px] text-center">
        <p className="text-xl font-bold">{total ? Math.round((affected / total) * 1000) / 10 : 0}%</p>
        <p className="text-[11px] text-muted-foreground">afetados</p>
      </div>
    </div>
  );
}

export function TimeSeries({ data }: { data: { date: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ left: -16, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
        <XAxis dataKey="date" tickFormatter={fmtDay} interval="preserveStartEnd" minTickGap={24} {...axis} />
        <YAxis allowDecimals={false} {...axis} />
        <Tooltip {...tooltipStyle} labelFormatter={(d: string) => fmtDay(d)} formatter={(v: number) => [v, "Análises"]} />
        <Line type="monotone" dataKey="count" stroke="hsl(var(--primary))" strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function QualityBars({ data }: { data: { name: string; score: number | null }[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: -16, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
        <XAxis dataKey="name" tickFormatter={(v: string) => truncate(v, 10)} {...axis} />
        <YAxis domain={[0, 100]} {...axis} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v}/100`, "Score"]} />
        <Bar dataKey="score" radius={[6, 6, 0, 0]} maxBarSize={36}>
          {data.map((d, i) => (
            <Cell key={i} fill={(d.score ?? 0) >= 90 ? "hsl(var(--success))" : (d.score ?? 0) >= 75 ? "hsl(var(--primary))" : (d.score ?? 0) >= 50 ? "hsl(var(--warning))" : "hsl(var(--destructive))"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
