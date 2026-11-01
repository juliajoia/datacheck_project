import { ChartNoAxesCombined, Download, Eye, FilePlus2, FileSpreadsheet, FileText, History as HistoryIcon, MoreHorizontal, Trash2, Wrench } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { GenerateEdaDialog } from "@/components/eda/GenerateEdaDialog";
import { ExportDialog } from "@/components/treatment/ExportDialog";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/hooks/useApi";
import { errorMessage } from "@/lib/api";
import { analysisService } from "@/services";
import type { AnalysisListItem } from "@/types";
import { fmtDateTime, scoreColor, WORKFLOW } from "@/utils/format";

const STATUS = { completed: ["success", "Concluída"], failed: ["destructive", "Falhou"], processing: ["warning", "Processando"], uploaded: ["muted", "Enviada"] } as const;

export default function History() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi(() => analysisService.list(page, 15), [page]);
  const [target, setTarget] = useState<AnalysisListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [exportTarget, setExportTarget] = useState<AnalysisListItem | null>(null);
  const [edaTarget, setEdaTarget] = useState<AnalysisListItem | null>(null);

  const remove = async () => {
    if (!target) return;
    setDeleting(true);
    try { await analysisService.remove(target.id); toast.success("Análise excluída."); setTarget(null); await reload(); }
    catch (e) { toast.error(errorMessage(e)); }
    finally { setDeleting(false); }
  };
  const download = async (a: AnalysisListItem, fmt: "xlsx" | "pdf") => {
    setBusy(a.id + fmt);
    try { await analysisService.downloadIssues(a.id, fmt, a.filename); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };

  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (loading && !data) return <Skeleton className="h-96" />;
  if (!data || data.total === 0)
    return <EmptyState icon={HistoryIcon} title="Seu histórico está vazio" description="As análises concluídas aparecerão aqui para consulta, exportação e exclusão."
      action={<Button asChild variant="brand"><Link to="/nova-analise"><FilePlus2 />Nova análise</Link></Button>} />;

  const pages = Math.ceil(data.total / data.page_size);
  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        <Table>
          <TableHeader><TableRow className="hover:bg-transparent">
            {["Arquivo", "Formato", "Data e hora", "Score", "Regras utilizadas", "Situação", "Ações"].map((h) => <TableHead key={h}>{h}</TableHead>)}
          </TableRow></TableHeader>
          <TableBody>
            {data.items.map((a) => {
              const [variant, label] = STATUS[a.status];
              return (
                <TableRow key={a.id}>
                  <TableCell className="max-w-[14rem] truncate font-medium">{a.status === "completed" ? <Link to={`/minhas-analises/${a.id}`} className="hover:text-primary">{a.filename}</Link> : a.filename}</TableCell>
                  <TableCell><Badge variant="muted">{a.file_type.toUpperCase()}</Badge></TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(a.created_at)}</TableCell>
                  <TableCell>{a.quality_score != null ? <span className="font-semibold" style={{ color: scoreColor(a.quality_score) }}>{a.quality_score.toLocaleString("pt-BR")}</span> : "—"}</TableCell>
                  <TableCell className="min-w-[12rem] text-xs text-muted-foreground">{a.rules_used.join(", ") || "—"}</TableCell>
                  <TableCell>{a.status === "completed" ? <Badge variant={WORKFLOW[a.workflow_status]?.variant ?? "muted"}>{WORKFLOW[a.workflow_status]?.label ?? a.workflow_status}</Badge> : <Badge variant={variant}>{label}</Badge>}</TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label={`Ações para ${a.filename}`} disabled={!!busy}><MoreHorizontal /></Button></DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel className="max-w-[14rem] truncate">{a.filename}</DropdownMenuLabel><DropdownMenuSeparator />
                        {a.status === "completed" && <DropdownMenuItem onSelect={() => navigate(`/minhas-analises/${a.id}`)}><Eye />Abrir em Minhas análises</DropdownMenuItem>}
                        {a.status === "completed" && a.data_available && <DropdownMenuItem onSelect={() => navigate(`/minhas-analises/${a.id}/tratamento`)}><Wrench />Continuar tratamento</DropdownMenuItem>}
                        {a.status === "completed" && a.data_available && <DropdownMenuItem onSelect={() => setExportTarget(a)}><Download />Baixar base tratada…</DropdownMenuItem>}
                        {a.status === "completed" && a.data_available && ["ready_for_eda", "eda_generated"].includes(a.workflow_status) && (
                          <DropdownMenuItem onSelect={() => setEdaTarget(a)}><ChartNoAxesCombined />Gerar EDA</DropdownMenuItem>)}
                        {a.status === "completed" && <DropdownMenuItem onSelect={() => void download(a, "xlsx")}><FileSpreadsheet />Inconsistências em XLSX</DropdownMenuItem>}
                        {a.status === "completed" && <DropdownMenuItem onSelect={() => void download(a, "pdf")}><FileText />Inconsistências em PDF</DropdownMenuItem>}
                        {a.status === "completed" && !a.data_available && <DropdownMenuLabel className="max-w-[14rem] whitespace-normal text-xs font-normal text-muted-foreground">Base não armazenada: tratamento indisponível.</DropdownMenuLabel>}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-destructive" onSelect={() => setTarget(a)}><Trash2 />Excluir análise</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>
      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
          <span>Página {page} de {pages}</span>
          <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Próxima</Button>
        </div>
      )}
      {edaTarget && <GenerateEdaDialog analysisId={edaTarget.id} analysisName={edaTarget.filename} onClose={() => setEdaTarget(null)} />}
      {exportTarget && <ExportDialog analysisId={exportTarget.id} filename={exportTarget.filename} versionLabel="versão atual" onClose={() => setExportTarget(null)} />}
      <ConfirmDialog open={!!target} onOpenChange={(o) => !o && setTarget(null)} loading={deleting} title="Excluir análise?" confirmLabel="Excluir"
        description={<>Remover <strong>{target?.filename}</strong> e todas as suas ocorrências do histórico? Esta ação não pode ser desfeita.</>} onConfirm={remove} />
    </div>
  );
}
