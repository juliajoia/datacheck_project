import { ChevronDown, ChevronRight, History, RotateCcw, Undo2 } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { cleaningService } from "@/services";
import type { CleaningOperationRow, CleaningSummary, VersionRow } from "@/types";
import { fmtDateTime, fmtInt } from "@/utils/format";

interface Props { analysisId: string; currentVersion: number; refreshKey: number; onChanged: (s: CleaningSummary) => void }

export function HistoryPane({ analysisId, currentVersion, refreshKey, onChanged }: Props) {
  const [versions, setVersions] = useState<VersionRow[] | null>(null);
  const [ops, setOps] = useState<CleaningOperationRow[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([cleaningService.versions(analysisId), cleaningService.history(analysisId)])
      .then(([v, o]) => { setVersions(v); setOps(o); }).catch((e) => toast.error(errorMessage(e)));
  }, [analysisId, refreshKey]);

  const run = async (key: string, fn: () => Promise<CleaningSummary>, ok: string) => {
    setBusy(key);
    try { onChanged(await fn()); toast.success(ok); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };
  if (!versions || !ops) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <p className="mr-auto flex items-center gap-2 text-sm font-semibold"><History className="size-4 text-primary" />Versões da base</p>
          <Button size="sm" variant="outline" disabled={currentVersion === 0 || !!busy} onClick={() => run("undo", () => cleaningService.undo(analysisId), "Última alteração desfeita.")}><Undo2 />Desfazer última alteração</Button>
          <Button size="sm" variant="outline" disabled={currentVersion === 0 || !!busy} onClick={() => run("orig", () => cleaningService.restore(analysisId, 0), "Base original restaurada.")}><RotateCcw />Restaurar base original</Button>
        </div>
        <p className="text-xs text-muted-foreground">O arquivo enviado (versão original) nunca é sobrescrito. Cada correção cria uma nova versão; restaurar uma versão não apaga as demais.</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {versions.map((v) => (
            <div key={v.id} className={cn("rounded-xl border p-3 text-sm", v.is_current && "border-primary bg-primary/5")}>
              <p className="flex items-center gap-2 font-semibold">{v.label}{v.is_current && <Badge variant="info">atual</Badge>}{!v.in_current_lineage && <Badge variant="muted">fora da linha atual</Badge>}</p>
              <p className="mt-1 text-xs text-muted-foreground">{fmtInt(v.total_rows)} registros · score {v.quality_score ?? "—"} · {fmtDateTime(v.created_at)}</p>
              {!v.is_current && <Button size="sm" variant="ghost" className="mt-1.5 h-7 px-2" disabled={!v.data_available || !!busy} onClick={() => run(`v${v.version_number}`, () => cleaningService.restore(analysisId, v.version_number), `${v.label} restaurada.`)}>
                {v.data_available ? "Restaurar esta versão" : "Dados expirados"}</Button>}
            </div>))}
        </div>
      </Card>

      <Card className="p-4">
        <p className="mb-3 text-sm font-semibold">Histórico de correções</p>
        {ops.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">Nenhuma correção realizada ainda.</p> : (
          <div className="overflow-x-auto rounded-lg border"><Table>
            <TableHeader><TableRow className="hover:bg-transparent"><TableHead className="w-8" /><TableHead>Data e hora</TableHead><TableHead>Responsável</TableHead><TableHead>Operação</TableHead><TableHead>Coluna</TableHead><TableHead>Registros</TableHead><TableHead>Método</TableHead><TableHead>Versão</TableHead></TableRow></TableHeader>
            <TableBody>{ops.map((o) => (
              <Fragment key={o.id}>
                <TableRow className={cn(!o.in_current_version && o.operation_type !== "undo" && o.operation_type !== "restore" && "opacity-60")}>
                  <TableCell><button aria-label="Detalhes" onClick={() => setOpen(open === o.id ? null : o.id)}>{open === o.id ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</button></TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(o.created_at)}</TableCell><TableCell>{o.user}</TableCell>
                  <TableCell className="font-medium">{o.operation_label}{o.undone && <Badge variant="muted" className="ml-2">desfeita</Badge>}</TableCell>
                  <TableCell>{o.column ?? "—"}</TableCell><TableCell>{fmtInt(o.affected_rows)}</TableCell><TableCell className="text-xs">{o.method ?? "—"}</TableCell>
                  <TableCell className="whitespace-nowrap text-xs">{o.from_version != null ? `${o.from_version} → ${o.to_version}` : o.to_version}</TableCell>
                </TableRow>
                {open === o.id && (
                  <TableRow className="bg-muted/40 hover:bg-muted/40"><TableCell /><TableCell colSpan={7} className="space-y-2 text-sm">
                    {o.justification && <p><b>Justificativa:</b> {o.justification}</p>}
                    {o.original_values.length > 0 ? (
                      <div className="max-h-48 overflow-auto rounded border bg-card"><Table>
                        <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Linha</TableHead><TableHead>Coluna</TableHead><TableHead>Valor anterior</TableHead><TableHead>Valor novo</TableHead></TableRow></TableHeader>
                        <TableBody>{o.original_values.map((v, i) => {
                          const n = o.replacement_values.find((r) => r.row === v.row && r.column === v.column);
                          return <TableRow key={i}><TableCell className="font-mono text-xs">{String(v.row)}</TableCell><TableCell>{String(v.column ?? "(registro removido)")}</TableCell>
                            <TableCell>{v.removed ? "removido" : String(v.value) || "Nulo"}</TableCell><TableCell>{n ? String(n.value) || "Nulo" : "—"}</TableCell></TableRow>;
                        })}</TableBody></Table></div>) : <p className="text-muted-foreground">Sem valores alterados (decisão registrada).</p>}
                    {o.values_truncated && <p className="text-xs text-muted-foreground">Exibindo os primeiros 200 valores.</p>}
                  </TableCell></TableRow>)}
              </Fragment>))}</TableBody></Table></div>)}
      </Card>
    </div>
  );
}
