import { ChartNoAxesCombined, Download, Eye, History, Loader2, MoreHorizontal, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { edaService } from "@/services";
import type { EdaListItem } from "@/types/eda";
import { fmtDateTime, fmtInt } from "@/utils/format";

export const EDA_STATUS = {
  queued: { label: "Na fila", variant: "muted" }, processing: { label: "Gerando…", variant: "info" },
  completed: { label: "Concluído", variant: "success" }, failed: { label: "Falhou", variant: "destructive" },
} as const;

export default function Eda() {
  const navigate = useNavigate();
  const [items, setItems] = useState<EdaListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<EdaListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setItems(await edaService.list()); setError(null); } catch (e) { setError(errorMessage(e)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  // Acompanha relatórios em geração (status consultável).
  const running = items?.some((i) => i.status === "queued" || i.status === "processing");
  useEffect(() => { if (!running) return; const t = setInterval(() => void load(), 2000); return () => clearInterval(t); }, [running, load]);

  const download = async (r: EdaListItem, fmt: "pdf" | "xlsx") => {
    setBusy(r.id + fmt);
    try { await edaService.download(r.id, fmt, r.report_name); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };
  const regenerate = async (r: EdaListItem) => {
    try { await edaService.regenerate(r.id); toast.success("Geração reiniciada com a mesma versão e configuração."); await load(); } catch (e) { toast.error(errorMessage(e)); }
  };
  const remove = async () => {
    if (!target) return;
    setDeleting(true);
    try { await edaService.remove(target.id); toast.success("Relatório excluído."); setTarget(null); await load(); } catch (e) { toast.error(errorMessage(e)); } finally { setDeleting(false); }
  };

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!items) return <Skeleton className="h-96" />;
  if (items.length === 0)
    return <EmptyState icon={ChartNoAxesCombined} title="Nenhum relatório exploratório ainda"
      description="Relatórios de análise exploratória são gerados a partir de uma análise com status «Pronta para EDA». Conclua o tratamento dos dados e use a ação «Gerar EDA» no Histórico."
      action={<Button asChild variant="brand"><Link to="/historico"><History />Ir para o Histórico</Link></Button>} />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Cada relatório está associado a uma versão específica da base tratada e não muda se você alterar os dados depois. Para analisar uma nova versão, gere uma nova EDA no Histórico.</p>
      <Card className="overflow-hidden"><Table>
        <TableHeader><TableRow className="hover:bg-transparent">{["Análise de origem", "Relatório", "Gerado em", "Registros", "Versão dos dados", "Seções incluídas", "Status", "Ações"].map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>{items.map((r) => {
          const s = EDA_STATUS[r.status];
          return (
            <TableRow key={r.id}>
              <TableCell className="max-w-[12rem] truncate font-medium">{r.analysis_name}</TableCell>
              <TableCell className="max-w-[14rem] truncate">{r.status === "completed" ? <Link to={`/eda/${r.id}`} className="hover:text-primary">{r.report_name}</Link> : r.report_name}</TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(r.completed_at ?? r.created_at)}</TableCell>
              <TableCell>{fmtInt(r.total_rows)}</TableCell>
              <TableCell><Badge variant="muted">{r.version_label}</Badge></TableCell>
              <TableCell className="min-w-[12rem] max-w-xs text-xs text-muted-foreground" title={r.sections_labels.join(", ")}>{r.sections.length} seção(ões): {r.sections_labels.slice(0, 3).join(", ")}{r.sections.length > 3 ? "…" : ""}</TableCell>
              <TableCell><Badge variant={s.variant}>{(r.status === "queued" || r.status === "processing") && <Loader2 className="size-3 animate-spin" />}{s.label}</Badge>
                {r.status === "failed" && r.error_message && <p className="mt-1 max-w-[12rem] text-xs text-destructive">{r.error_message}</p>}</TableCell>
              <TableCell>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label={`Ações para ${r.report_name}`}><MoreHorizontal /></Button></DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuLabel className="max-w-[14rem] truncate">{r.report_name}</DropdownMenuLabel><DropdownMenuSeparator />
                    {r.status === "completed" && <>
                      <DropdownMenuItem onSelect={() => navigate(`/eda/${r.id}`)}><Eye />Visualizar EDA</DropdownMenuItem>
                      <DropdownMenuItem disabled={!!busy} onSelect={() => void download(r, "pdf")}><Download />Baixar PDF</DropdownMenuItem>
                      <DropdownMenuItem disabled={!!busy} onSelect={() => void download(r, "xlsx")}><Download />Baixar Excel</DropdownMenuItem></>}
                    {(r.status === "completed" || r.status === "failed") && <DropdownMenuItem onSelect={() => void regenerate(r)}><RefreshCw />Gerar novamente</DropdownMenuItem>}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="text-destructive" onSelect={() => setTarget(r)}><Trash2 />Excluir relatório</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>);
        })}</TableBody>
      </Table></Card>
      <ConfirmDialog open={!!target} onOpenChange={(o) => !o && setTarget(null)} loading={deleting} title="Excluir relatório EDA?" confirmLabel="Excluir"
        description={<>Remover <strong>{target?.report_name}</strong> e seus arquivos (PDF e Excel)? A análise de origem e a base tratada não são afetadas.</>} onConfirm={remove} />
    </div>
  );
}
