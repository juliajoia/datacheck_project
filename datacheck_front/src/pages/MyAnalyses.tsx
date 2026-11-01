import { ArrowRight, FilePlus2, FolderOpen, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/api";
import { analysisService } from "@/services";
import type { AnalysisListItem } from "@/types";
import { fmtDateTime, fmtInt, scoreColor, WORKFLOW } from "@/utils/format";

/** Bases em trabalho: abrir uma base leva à área com diagnóstico, tratamento, dados tratados e alterações. */
export default function MyAnalyses() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi(() => analysisService.list(page, 15), [page]);
  const [target, setTarget] = useState<AnalysisListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const remove = async () => {
    if (!target) return;
    setDeleting(true);
    try { await analysisService.remove(target.id); toast.success("Análise excluída."); setTarget(null); await reload(); }
    catch (e) { toast.error(errorMessage(e)); }
    finally { setDeleting(false); }
  };

  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (loading && !data) return <Skeleton className="h-96" />;
  if (!data || data.total === 0)
    return <EmptyState icon={FolderOpen} title="Você ainda não tem análises" description="Envie uma base para ver o diagnóstico e tratá-la em um só lugar."
      action={<Button asChild variant="brand"><Link to="/nova-analise"><FilePlus2 />Nova análise</Link></Button>} />;

  const pages = Math.ceil(data.total / data.page_size);
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Abra uma base para acompanhar o diagnóstico, tratar os dados, consultar a base tratada e ver as alterações, sem sair da análise.</p>
      <Card className="overflow-hidden">
        <Table>
          <TableHeader><TableRow className="hover:bg-transparent">{["Arquivo", "Data e hora", "Registros", "Ocorrências", "Score", "Situação", ""].map((h, i) => <TableHead key={i}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {data.items.map((a) => {
              const done = a.status === "completed";
              const wf = WORKFLOW[a.workflow_status];
              return (
                <TableRow key={a.id}>
                  <TableCell className="max-w-[16rem] truncate font-medium">{done ? <Link to={`/minhas-analises/${a.id}`} className="hover:text-primary">{a.filename}</Link> : a.filename}</TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(a.created_at)}</TableCell>
                  <TableCell>{fmtInt(a.total_rows)}</TableCell><TableCell>{fmtInt(a.total_issues)}</TableCell>
                  <TableCell>{a.quality_score != null ? <span className="font-semibold" style={{ color: scoreColor(a.quality_score) }}>{a.quality_score.toLocaleString("pt-BR")}</span> : "—"}</TableCell>
                  <TableCell>{done ? <Badge variant={wf?.variant ?? "muted"}>{wf?.label ?? a.workflow_status}</Badge>
                    : <Badge variant={a.status === "failed" ? "destructive" : "muted"}>{a.status === "failed" ? "Falhou" : a.status === "processing" ? "Processando" : "Enviada"}</Badge>}</TableCell>
                  <TableCell className="whitespace-nowrap text-right">
                    {done && <Button asChild size="sm" variant="outline"><Link to={`/minhas-analises/${a.id}`}>Abrir<ArrowRight /></Link></Button>}
                    <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" aria-label={`Excluir ${a.filename}`} onClick={() => setTarget(a)}><Trash2 /></Button>
                  </TableCell>
                </TableRow>);
            })}
          </TableBody>
        </Table>
      </Card>
      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
          <span>Página {page} de {pages}</span>
          <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Próxima</Button>
        </div>)}
      <ConfirmDialog open={!!target} onOpenChange={(o) => !o && setTarget(null)} loading={deleting} title="Excluir análise?" confirmLabel="Excluir"
        description={<>Remover <strong>{target?.filename}</strong> e todas as suas ocorrências? Esta ação não pode ser desfeita.</>} onConfirm={remove} />
    </div>
  );
}
