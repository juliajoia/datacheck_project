import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { CorrelationBlock, DistributionRow, FrequencyRow } from "@/types/eda";

const axis = { stroke: "hsl(var(--muted-foreground))", fontSize: 11, tickLine: false, axisLine: false } as const;
const tip = {
  contentStyle: { background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 10, fontSize: 12 },
  itemStyle: { color: "hsl(var(--foreground))" }, labelStyle: { color: "hsl(var(--foreground))", fontWeight: 600 }, cursor: { fill: "hsl(var(--muted) / 0.6)" },
};
const nf = (x: number) => x.toLocaleString("pt-BR", { maximumFractionDigits: 2 });

export function Histogram({ d }: { d: DistributionRow }) {
  if (!d.histogram) return null;
  const data = d.histogram.bins.map((b) => ({ label: d.histogram!.discrete ? nf(b.x0) : `${nf(b.x0)}–${nf(b.x1)}`, count: b.count }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: -12, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
        <XAxis dataKey="label" {...axis} interval="preserveStartEnd" minTickGap={18} />
        <YAxis allowDecimals={false} {...axis} />
        <Tooltip {...tip} formatter={(v: number) => [v, "Registros"]} />
        <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Boxplot horizontal em SVG: caixa Q1–Q3, mediana, bigodes (1,5×IQR) e valores atípicos. */
export function BoxPlot({ d }: { d: DistributionRow }) {
  const b = d.boxplot;
  if (!b) return null;
  const lo = Math.min(b.min, b.whisker_low), hi = Math.max(b.max, b.whisker_high);
  const span = hi - lo || 1;
  const x = (v: number) => 12 + ((v - lo) / span) * 276;
  return (
    <svg viewBox="0 0 300 74" className="w-full" role="img" aria-label={`Boxplot de ${d.column}: mediana ${nf(b.median)}`}>
      <line x1={x(b.whisker_low)} x2={x(b.whisker_high)} y1="30" y2="30" stroke="hsl(var(--muted-foreground))" />
      {[b.whisker_low, b.whisker_high].map((v, i) => <line key={i} x1={x(v)} x2={x(v)} y1="22" y2="38" stroke="hsl(var(--muted-foreground))" />)}
      <rect x={x(b.q1)} y="16" width={Math.max(2, x(b.q3) - x(b.q1))} height="28" rx="4" fill="hsl(var(--primary) / 0.18)" stroke="hsl(var(--primary))" />
      <line x1={x(b.median)} x2={x(b.median)} y1="16" y2="44" stroke="hsl(var(--brand))" strokeWidth="2.5" />
      {b.outliers.map((v, i) => <circle key={i} cx={x(v)} cy="30" r="2.6" fill="hsl(var(--destructive))" opacity="0.75" />)}
      {[lo, b.median, hi].map((v, i) => <text key={i} x={x(v)} y="64" fontSize="9" textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"} fill="hsl(var(--muted-foreground))">{nf(v)}</text>)}
    </svg>
  );
}

export function CategoryBars({ f }: { f: FrequencyRow }) {
  const data = f.top.slice(0, 12).map((t) => ({ name: t.value.length > 24 ? `${t.value.slice(0, 23)}…` : t.value, pct: t.pct, count: t.count }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(150, data.length * 34 + 30)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 36 }}>
        <CartesianGrid horizontal={false} stroke="hsl(var(--border))" />
        <XAxis type="number" unit="%" {...axis} />
        <YAxis type="category" dataKey="name" width={120} {...axis} />
        <Tooltip {...tip} formatter={(v: number, _n, p) => [`${nf(v)}% (${(p.payload as { count: number }).count} registros)`, ""]} />
        <Bar dataKey="pct" fill="hsl(var(--brand))" radius={[0, 4, 4, 0]} maxBarSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Heatmap({ c }: { c: CorrelationBlock }) {
  const color = (r: number | null) => {
    if (r == null) return "transparent";
    const a = Math.min(1, Math.abs(r));
    return r >= 0 ? `hsl(221 83% 53% / ${0.12 + a * 0.75})` : `hsl(0 72% 51% / ${0.12 + a * 0.75})`;
  };
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-px rounded-lg bg-border p-px text-xs" style={{ gridTemplateColumns: `minmax(6rem,auto) repeat(${c.columns.length}, minmax(4.5rem, 1fr))` }}>
        <div className="bg-card" />
        {c.columns.map((col) => <div key={col} className="truncate bg-card px-2 py-1.5 text-center font-semibold" title={col}>{col}</div>)}
        {c.columns.map((row, i) => (
          <div key={row} className="contents">
            <div className="truncate bg-card px-2 py-2 font-semibold" title={row}>{row}</div>
            {c.matrix[i].map((r, j) => (
              <div key={j} className="bg-card px-2 py-2 text-center font-medium tabular-nums" style={{ background: color(r) }} title={`${row} × ${c.columns[j]}: r = ${r ?? "—"} (n = ${c.n_matrix[i][j]})`}>
                {r == null ? "—" : r.toFixed(2).replace(".", ",")}
              </div>))}
          </div>))}
      </div>
    </div>
  );
}

export function Scatter2D({ s }: { s: { x: string; y: string; points: [number, number][] } }) {
  const data = s.points.map(([x, y]) => ({ x, y }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <ScatterChart margin={{ left: -8, right: 12, top: 8, bottom: 12 }}>
        <CartesianGrid stroke="hsl(var(--border))" />
        <XAxis type="number" dataKey="x" name={s.x} {...axis} label={{ value: s.x, position: "insideBottom", offset: -6, fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
        <YAxis type="number" dataKey="y" name={s.y} {...axis} />
        <Tooltip {...tip} cursor={{ strokeDasharray: "3 3" }} />
        <Scatter data={data} fill="hsl(var(--primary))" fillOpacity={0.55} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export function TimeBars({ data }: { data: { period: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: -12, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
        <XAxis dataKey="period" {...axis} interval="preserveStartEnd" minTickGap={24} />
        <YAxis allowDecimals={false} {...axis} />
        <Tooltip {...tip} formatter={(v: number) => [v, "Registros"]} />
        <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TimeLine({ data }: { data: { period: string; mean: number | null; n: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: -4, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
        <XAxis dataKey="period" {...axis} interval="preserveStartEnd" minTickGap={24} />
        <YAxis {...axis} />
        <Tooltip {...tip} formatter={(v: number, _n, p) => [`${nf(v)} (n = ${(p.payload as { n: number }).n})`, "Média"]} />
        <Line type="monotone" dataKey="mean" stroke="hsl(var(--brand))" strokeWidth={2.2} dot={{ r: 2.5 }} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  );
}

