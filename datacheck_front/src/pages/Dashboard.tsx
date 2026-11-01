import { Activity, BarChart3, CalendarClock, ClipboardList, FilePlus2, Gauge, Rows3, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { QualityBars, HorizontalBars, TimeSeries } from "@/components/Charts";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StatCard } from "@/components/StatCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/hooks/useApi";
import { analysisService, dashboardService } from "@/services";
import { fmtDateTime, fmtInt, scoreColor } from "@/utils/format";

export default function Dashboard() {
  const summary = useApi(dashboardService.summary);
  const charts = useApi(dashboardService.charts);
  const recent = useApi(() => analysisService.list(1, 5));

  if (summary.error) return <ErrorState message={summary.error} onRetry={() => { void summary.reload(); void charts.reload(); void recent.reload(); }} />;
  const s = summary.data;
  const loading = summary.loading;

  if (!loading && s && s.total_analyses === 0) {
    return (
      <EmptyState icon={ClipboardList} title="Nenhuma análise realizada ainda"
        description="Envie uma planilha CSV ou XLSX para descobrir valores ausentes, duplicidades, tipos incorretos, coordenadas e datas inválidas. Seu dashboard será preenchido com os resultados reais."
        action={<Button asChild variant="brand" size="lg"><Link to="/nova-analise"><FilePlus2 />Iniciar primeira análise</Link></Button>} />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard loading={loading} label="Análises realizadas" value={s && fmtInt(s.total_analyses)} icon={BarChart3} />
        <StatCard loading={loading} label="Registros analisados" value={s && fmtInt(s.total_rows)} icon={Rows3} tone="brand" />
        <StatCard loading={loading} label="Inconsistências encontradas" value={s && fmtInt(s.total_issues)} icon={TriangleAlert} tone="warning" />
        <StatCard loading={loading} label="Análises recentes" value={s && fmtInt(s.recent_analyses)} icon={CalendarClock} tone="success" hint={s ? `Últimos ${s.recent_days} dias` : undefined} />
        <StatCard loading={loading} label="Score médio" value={s?.average_score != null ? `${s.average_score.toLocaleString("pt-BR")}/100` : "—"} icon={Gauge} tone="primary" hint="Média das bases analisadas" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Análises ao longo do tempo</CardTitle><CardDescription>Últimos 30 dias</CardDescription></CardHeader>
          <CardContent>{charts.data ? <TimeSeries data={charts.data.analyses_over_time} /> : <Skeleton className="h-60" />}</CardContent></Card>
        <Card><CardHeader><CardTitle>Inconsistências por categoria</CardTitle><CardDescription>Todas as suas análises</CardDescription></CardHeader>
          <CardContent>{charts.data ? (charts.data.issues_by_category.length
            ? <HorizontalBars data={charts.data.issues_by_category.map((c) => ({ name: c.label, value: c.count }))} />
            : <p className="py-16 text-center text-sm text-muted-foreground">Nenhuma inconsistência registrada.</p>) : <Skeleton className="h-60" />}</CardContent></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1"><CardHeader><CardTitle>Qualidade das últimas bases</CardTitle><CardDescription>DataCheck Score</CardDescription></CardHeader>
          <CardContent>{charts.data ? <QualityBars data={charts.data.recent_quality.map((q) => ({ name: q.filename, score: q.score }))} /> : <Skeleton className="h-60" />}</CardContent></Card>
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between"><div><CardTitle>Análises recentes</CardTitle><CardDescription>As 5 últimas</CardDescription></div>
            <Button asChild variant="outline" size="sm"><Link to="/historico">Ver histórico</Link></Button></CardHeader>
          <CardContent>
            {recent.loading ? <Skeleton className="h-48" /> : (
              <Table>
                <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Arquivo</TableHead><TableHead>Data</TableHead><TableHead>Registros</TableHead><TableHead>Ocorrências</TableHead><TableHead>Score</TableHead></TableRow></TableHeader>
                <TableBody>
                  {recent.data?.items.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell><Link to={`/minhas-analises/${a.id}`} className="inline-flex items-center gap-2 font-medium hover:text-primary"><Activity className="size-4 text-muted-foreground" />{a.filename}</Link></TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(a.created_at)}</TableCell>
                      <TableCell>{fmtInt(a.total_rows)}</TableCell><TableCell>{fmtInt(a.total_issues)}</TableCell>
                      <TableCell>{a.quality_score != null ? <Badge variant="muted" style={{ color: scoreColor(a.quality_score) }}>{a.quality_score.toLocaleString("pt-BR")}</Badge> : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
