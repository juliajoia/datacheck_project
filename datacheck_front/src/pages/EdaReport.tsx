import { ArrowLeft, Download, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { BoxPlot, CategoryBars, Heatmap, Histogram, Scatter2D, TimeBars, TimeLine } from "@/components/eda/EdaCharts";
import { ErrorState } from "@/components/ErrorState";
import { EDA_STATUS } from "@/pages/Eda";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { edaService } from "@/services";
import type { EdaDetail, EdaStats } from "@/types/eda";
import { fmtDateTime, fmtInt } from "@/utils/format";

const n = (x: number | null | undefined, d = 2) => (x == null ? "—" : x.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: d }));
const P = (x: number | null | undefined) => (x == null ? "—" : `${n(x, 1)}%`);
const ALL = "__all__";

function Section({ id, title, desc, children }: { id: string; title: string; desc?: string; children: ReactNode }) {
  return (
    <Card id={id} className="scroll-mt-24">
      <CardHeader><CardTitle>{title}</CardTitle>{desc && <CardDescription>{desc}</CardDescription>}</CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

export default function EdaReport() {
  const { id = "" } = useParams();
  const [rep, setRep] = useState<EdaDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [distFilter, setDistFilter] = useState(ALL);

  const load = useCallback(async () => {
    try { setRep(await edaService.get(id)); setError(null); } catch (e) { setError(errorMessage(e)); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);
  const running = rep?.status === "queued" || rep?.status === "processing";
  useEffect(() => { if (!running) return; const t = setInterval(() => void load(), 2000); return () => clearInterval(t); }, [running, load]);

  const sections = useMemo(() => {
    const s = rep?.summary_statistics;
    if (!s) return [];
    return [["resumo", "Resumo"], ["tratamento", "Tratamento"], s.descriptive && ["descritivas", "Estatísticas"], s.frequencies && ["frequencias", "Frequências"],
      s.distributions && ["distribuicoes", "Distribuições"], s.correlation && ["correlacao", "Correlações"], s.outliers && ["extremos", "Valores extremos"],
      s.temporal?.available && ["temporal", "Temporal"], ["ausentes", "Ausentes"], ["observacoes", "Observações"]].filter(Boolean) as [string, string][];
  }, [rep]);

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!rep) return <div className="space-y-4"><Skeleton className="h-12 w-80" /><Skeleton className="h-96" /></div>;
  const st = EDA_STATUS[rep.status];

  const download = async (fmt: "pdf" | "xlsx") => {
    setBusy(fmt);
    try { await edaService.download(rep.id, fmt, rep.report_name); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };
  const regenerate = async () => {
    try { await edaService.regenerate(rep.id); toast.success("Geração reiniciada."); await load(); } catch (e) { toast.error(errorMessage(e)); }
  };

  const head = (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <Link to="/eda" className="mb-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Relatórios EDA</Link>
        <h2 className="truncate text-xl font-bold tracking-tight">{rep.report_name}</h2>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Badge variant={st.variant}>{st.label}</Badge><Badge variant="muted">{rep.version_label}</Badge>
          <span>{rep.analysis_name}</span><span>· {fmtInt(rep.total_rows)} registros · {rep.total_columns} variáveis</span><span>· {fmtDateTime(rep.completed_at ?? rep.created_at)}</span>
        </div>
      </div>
      {rep.status === "completed" && <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={!!busy} onClick={() => download("xlsx")}><Download />Excel</Button>
        <Button disabled={!!busy} onClick={() => download("pdf")}><Download />PDF</Button>
        <Button variant="ghost" onClick={regenerate}><RefreshCw />Gerar novamente</Button></div>}
    </div>
  );

  if (rep.status !== "completed" || !rep.summary_statistics)
    return (
      <div className="space-y-6">{head}
        <Card className="flex items-center gap-3 p-6" role="status" aria-live="polite">
          {running ? <><Loader2 className="size-5 animate-spin text-primary" /><p>O relatório está sendo gerado. Esta página atualiza sozinha.</p></>
            : <div className="space-y-3"><p role="alert" className="text-destructive">{rep.error_message ?? "A geração falhou."}</p><Button variant="outline" onClick={regenerate}><RefreshCw />Tentar novamente</Button></div>}
        </Card>
      </div>);

  const s: EdaStats = rep.summary_statistics;
  const dist = (s.distributions ?? []).filter((d) => distFilter === ALL || d.column === distFilter);
  const go = (sid: string) => document.getElementById(sid)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="space-y-6">
      {head}
      <nav aria-label="Seções do relatório" className="sticky top-16 z-10 -mx-1 overflow-x-auto rounded-xl border bg-background/90 p-1.5 backdrop-blur">
        <ul className="flex gap-1">{sections.map(([sid, label]) => <li key={sid}><button onClick={() => go(sid)} className="whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground">{label}</button></li>)}</ul>
      </nav>

      <Section id="resumo" title="Resumo geral" desc="Visão geral da base tratada.">
        <div className="grid gap-3 sm:grid-cols-3">{[["Registros", fmtInt(s.overview.rows)], ["Variáveis", s.overview.columns], ["Registros completos", fmtInt(s.missing.complete_rows)]].map(([l, v]) => (
          <div key={String(l)} className="rounded-xl bg-muted/60 p-4"><p className="text-xs text-muted-foreground">{l}</p><p className="text-2xl font-bold">{v}</p></div>))}</div>
        <div className="overflow-x-auto rounded-lg border"><Table>
          <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Variável</TableHead><TableHead>Tipo estatístico</TableHead><TableHead>Válidos</TableHead><TableHead>Ausentes</TableHead><TableHead>Distintos</TableHead></TableRow></TableHeader>
          <TableBody>{s.overview.columns_info.map((c) => <TableRow key={c.name}><TableCell className="font-medium">{c.name}</TableCell><TableCell>{c.label}</TableCell><TableCell>{fmtInt(c.n_valid)}</TableCell><TableCell>{c.n_missing ? <Badge variant="warning">{c.n_missing} ({P(c.pct_missing)})</Badge> : 0}</TableCell><TableCell>{fmtInt(c.n_unique)}</TableCell></TableRow>)}</TableBody></Table></div>
      </Section>

      <Section id="tratamento" title="Tratamento realizado" desc="Histórico de preparação associado a esta versão.">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">{[["Versão", s.treatment.version_label], ["Score", `${n(s.treatment.score_before, 1)} → ${n(s.treatment.score_after, 1)}`], ["Imputados", s.treatment.imputed_values],
          ["Removidos", s.treatment.removed_rows], ["Duplicidades", s.treatment.duplicates_resolved], ["Exceções", s.treatment.exceptions_accepted]].map(([l, v]) => (
          <div key={String(l)} className="rounded-xl bg-muted/60 p-3"><p className="text-xs text-muted-foreground">{l}</p><p className="font-semibold">{v}</p></div>))}</div>
        <p className="text-xs text-muted-foreground">O score cobre apenas as regras executadas e não garante que os dados estejam totalmente corretos.</p>
        {s.treatment.operations.length > 0 && <div className="overflow-x-auto rounded-lg border"><Table>
          <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Operação</TableHead><TableHead>Coluna</TableHead><TableHead>Método</TableHead><TableHead>Registros</TableHead><TableHead>Justificativa</TableHead></TableRow></TableHeader>
          <TableBody>{s.treatment.operations.map((o, i) => <TableRow key={i}><TableCell>{o.label}</TableCell><TableCell>{o.column ?? "—"}</TableCell><TableCell>{o.method ?? "—"}</TableCell><TableCell>{o.affected_rows}</TableCell><TableCell className="text-muted-foreground">{o.justification ?? "—"}</TableCell></TableRow>)}</TableBody></Table></div>}
      </Section>

      {s.descriptive && <Section id="descritivas" title="Estatísticas descritivas" desc="Variáveis quantitativas, calculadas com os valores válidos.">
        <div className="overflow-x-auto rounded-lg border"><Table>
          <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Medida</TableHead>{s.descriptive.map((d) => <TableHead key={d.column}>{d.column}</TableHead>)}</TableRow></TableHeader>
          <TableBody>{([["Observações válidas", "n_valid", 0], ["Ausentes", "n_missing", 0], ["Média", "mean", 2], ["Mediana", "median", 2], ["Moda", "mode", 2], ["Mínimo", "min", 2], ["Máximo", "max", 2], ["Amplitude", "range", 2],
            ["Variância", "variance", 2], ["Desvio padrão", "std", 2], ["Coef. de variação", "cv", 3], ["Q1", "q1", 2], ["Q3", "q3", 2], ["Intervalo interquartil", "iqr", 2], ["Assimetria", "skewness", 3], ["Curtose", "kurtosis", 3]] as const).map(([label, key, d]) => (
            <TableRow key={key}><TableCell className="font-medium">{label}</TableCell>{s.descriptive!.map((r) => <TableCell key={r.column} className="tabular-nums">{n(r[key] as number | null, d)}</TableCell>)}</TableRow>))}
            {Object.keys(s.descriptive[0].percentiles ?? {}).map((pk) => <TableRow key={pk}><TableCell className="font-medium">Percentil {pk.slice(1)}</TableCell>{s.descriptive!.map((r) => <TableCell key={r.column} className="tabular-nums">{n(r.percentiles?.[pk])}</TableCell>)}</TableRow>)}</TableBody></Table></div>
        {s.descriptive.flatMap((d) => d.warnings.map((w) => <p key={d.column + w} className="text-xs text-muted-foreground">• <b>{d.column}</b>: {w}</p>))}
      </Section>}

      {s.frequencies && <Section id="frequencias" title="Frequências" desc="Variáveis qualitativas. Em variáveis ordinais, a ordem definida por você é respeitada.">
        <div className="grid gap-4 lg:grid-cols-2">{s.frequencies.map((f) => (
          <div key={f.column} className="rounded-xl border p-3"><p className="font-semibold">{f.column}</p>
            <p className="mb-2 text-xs text-muted-foreground">{f.n_unique} categoria(s) · {f.n_missing} ausente(s) · moda: {f.mode ?? "—"}{f.ordered && " · ordem definida pelo usuário"}</p>
            <Table><TableHeader><TableRow className="hover:bg-transparent"><TableHead>Categoria</TableHead><TableHead>Freq.</TableHead><TableHead>%</TableHead></TableRow></TableHeader>
              <TableBody>{f.top.map((t) => <TableRow key={t.value}><TableCell>{t.value}</TableCell><TableCell>{fmtInt(t.count)}</TableCell><TableCell>{P(t.pct)}</TableCell></TableRow>)}
                {f.other && <TableRow><TableCell className="text-muted-foreground">Outras {f.other.n_categories} categorias</TableCell><TableCell>{fmtInt(f.other.count)}</TableCell><TableCell /></TableRow>}</TableBody></Table></div>))}</div>
      </Section>}

      {s.distributions && <Section id="distribuicoes" title="Distribuições" desc="Histograma (com densidade no PDF), boxplot e barras por variável.">
        <div className="max-w-xs"><Select value={distFilter} onValueChange={setDistFilter}><SelectTrigger aria-label="Filtrar variável"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>Todas as variáveis</SelectItem>{s.distributions.map((d) => <SelectItem key={d.column} value={d.column}>{d.column}</SelectItem>)}</SelectContent></Select></div>
        <div className="grid gap-4 lg:grid-cols-2">{dist.map((d) => (
          <div key={d.column} className="rounded-xl border p-3"><p className="mb-1 font-semibold">{d.column}</p>
            {d.kind === "quantitative" ? <><Histogram d={d} /><BoxPlot d={d} />{d.boxplot && d.boxplot.n_outliers > 0 && <p className="text-xs text-muted-foreground">{d.boxplot.n_outliers} valor(es) além de 1,5×IQR (pontos vermelhos). Atípico não significa errado.</p>}</>
              : d.frequencies && <CategoryBars f={d.frequencies} />}</div>))}</div>
      </Section>}

      {s.correlation && <Section id="correlacao" title="Correlações" desc={`Método: ${s.correlation.method === "pearson" ? "Pearson" : "Spearman"}. ${s.correlation.warning}`}>
        {s.correlation.columns.length >= 2 ? <>
          <Heatmap c={s.correlation} />
          <div className="overflow-x-auto rounded-lg border"><Table>
            <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Variável A</TableHead><TableHead>Variável B</TableHead><TableHead>Coeficiente</TableHead><TableHead>n</TableHead><TableHead>Intensidade</TableHead><TableHead>Direção</TableHead></TableRow></TableHeader>
            <TableBody>{s.correlation.pairs.map((p) => <TableRow key={p.a + p.b}><TableCell>{p.a}</TableCell><TableCell>{p.b}</TableCell><TableCell className="tabular-nums">{n(p.r, 3)}</TableCell><TableCell>{p.n}</TableCell><TableCell>{p.strength}</TableCell><TableCell>{p.direction}</TableCell></TableRow>)}</TableBody></Table></div>
          {s.correlation.excluded.length > 0 && <p className="text-xs text-muted-foreground">Excluídas: {s.correlation.excluded.map((e) => `${e.column} (${e.reason})`).join("; ")}.</p>}
          {s.scatter && s.scatter.length > 0 && <div className="grid gap-4 lg:grid-cols-3">{s.scatter.map((sc) => <div key={sc.x + sc.y} className="rounded-xl border p-3"><p className="text-sm font-semibold">{sc.y} × {sc.x}</p><p className="text-xs text-muted-foreground">r = {n(sc.r, 2)} · n = {sc.n}</p><Scatter2D s={sc} /></div>)}</div>}
        </> : <p className="text-sm text-muted-foreground">Não há variáveis suficientes com variação para calcular correlações.</p>}
      </Section>}

      {s.outliers && <Section id="extremos" title="Valores extremos" desc="Critério do intervalo interquartil (1,5×IQR). Valores atípicos não são necessariamente erros.">
        <div className="overflow-x-auto rounded-lg border"><Table>
          <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Variável</TableHead><TableHead>Limite inferior</TableHead><TableHead>Limite superior</TableHead><TableHead>Quantidade</TableHead><TableHead>%</TableHead><TableHead>Exemplos</TableHead></TableRow></TableHeader>
          <TableBody>{s.outliers.map((o) => <TableRow key={o.column}><TableCell className="font-medium">{o.column}</TableCell>
            {o.available ? <><TableCell>{n(o.lower)}</TableCell><TableCell>{n(o.upper)}</TableCell><TableCell>{o.count}</TableCell><TableCell>{P(o.pct)}</TableCell><TableCell className="text-muted-foreground">{o.examples?.slice(0, 5).map((v) => n(v)).join(", ") || "—"}</TableCell></>
              : <TableCell colSpan={5} className="text-muted-foreground">Não aplicável: {o.reason}</TableCell>}</TableRow>)}</TableBody></Table></div>
      </Section>}

      {s.temporal?.available && <Section id="temporal" title="Análise temporal" desc={`Coluna «${s.temporal.date_column}» · ${s.temporal.n_dates} datas válidas de ${s.temporal.start} a ${s.temporal.end} · ${s.temporal.n_gaps} período(s) sem registros.`}>
        <TimeBars data={s.temporal.count_series} />
        {s.temporal.value_series.map((v) => <div key={v.column}><p className="mb-1 text-sm font-semibold">Média de {v.column} por período</p><TimeLine data={v.points} /></div>)}
        {s.temporal.gaps.length > 0 && <p className="text-xs text-muted-foreground">Períodos sem registros: {s.temporal.gaps.slice(0, 30).join(", ")}{s.temporal.n_gaps > 30 ? "…" : ""}</p>}
      </Section>}

      <Section id="ausentes" title="Dados ausentes remanescentes">
        <p className="text-sm">{fmtInt(s.missing.rows_with_missing)} registro(s) com ao menos um valor ausente; {fmtInt(s.missing.complete_rows)} completos.</p>
        {s.missing.columns.some((c) => c.n_missing) ? <div className="overflow-x-auto rounded-lg border"><Table><TableHeader><TableRow className="hover:bg-transparent"><TableHead>Variável</TableHead><TableHead>Ausentes</TableHead><TableHead>%</TableHead></TableRow></TableHeader>
          <TableBody>{s.missing.columns.filter((c) => c.n_missing).map((c) => <TableRow key={c.column}><TableCell>{c.column}</TableCell><TableCell>{c.n_missing}</TableCell><TableCell>{P(c.pct)}</TableCell></TableRow>)}</TableBody></Table></div>
          : <Badge variant="success">Nenhum valor ausente remanescente</Badge>}
      </Section>

      <Section id="observacoes" title="Principais observações e limitações" desc="Texto descritivo gerado a partir dos cálculos, sem conclusões causais.">
        <ul className="list-disc space-y-1.5 pl-5 text-sm">{s.observations.map((o, i) => <li key={i}>{o}</li>)}</ul>
        <p className="pt-2 text-sm font-semibold">Limitações</p>
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">{s.limitations.map((o, i) => <li key={i}>{o}</li>)}</ul>
      </Section>
    </div>
  );
}
