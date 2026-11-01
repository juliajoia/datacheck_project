import { Download, FileBarChart, FilePlus2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/api";
import { analysisService } from "@/services";
import { fmtDateTime, fmtInt } from "@/utils/format";

export default function Reports() {
  const { data, error, loading, reload } = useApi(() => analysisService.list(1, 100));
  const [busy, setBusy] = useState<string | null>(null);
  const done = data?.items.filter((a) => a.status === "completed") ?? [];

  const download = async (id: string, filename: string, fmt: "csv" | "xlsx") => {
    setBusy(id + fmt);
    try { await analysisService.download(id, fmt, filename); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };

  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>O que o relatório contém</CardTitle></CardHeader>
        <CardContent className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
          <p>• Identificação e data de execução</p><p>• Resumo da base de dados</p><p>• Indicadores e DataCheck Score</p>
          <p>• Resumo das inconsistências por categoria</p><p>• Lista detalhada das ocorrências</p><p>• Sugestões de revisão</p>
          <p className="sm:col-span-2">O <strong className="text-foreground">XLSX</strong> traz múltiplas abas e gráficos; o <strong className="text-foreground">CSV</strong> reúne as seções em um único arquivo. Textos que parecem fórmulas são neutralizados na exportação. PDF fica para uma próxima versão.</p>
        </CardContent>
      </Card>

      {loading ? <Skeleton className="h-48" /> : done.length === 0 ? (
        <EmptyState icon={FileBarChart} title="Nenhum relatório disponível" description="Conclua uma análise para exportar seu relatório."
          action={<Button asChild variant="brand"><Link to="/nova-analise"><FilePlus2 />Nova análise</Link></Button>} />
      ) : (
        <div className="grid gap-3">
          {done.map((a) => (
            <Card key={a.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <Link to={`/minhas-analises/${a.id}`} className="block truncate font-semibold hover:text-primary">{a.filename}</Link>
                <CardDescription>{fmtDateTime(a.completed_at)} · {fmtInt(a.total_rows)} registros · {fmtInt(a.total_issues)} ocorrências · Score {a.quality_score ?? "—"}</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={!!busy} onClick={() => download(a.id, a.filename, "csv")}><Download />{busy === a.id + "csv" ? "Gerando…" : "CSV"}</Button>
                <Button size="sm" disabled={!!busy} onClick={() => download(a.id, a.filename, "xlsx")}><Download />{busy === a.id + "xlsx" ? "Gerando…" : "XLSX"}</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
