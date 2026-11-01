import { AlertTriangle, ArrowRight, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/input";
import { errorMessage } from "@/lib/api";
import { cleaningService } from "@/services";
import type { CleaningRequest, CleaningSummary, PreviewResult } from "@/types";
import { fmtInt } from "@/utils/format";

interface Props {
  analysisId: string;
  request: CleaningRequest;
  onApplied: (s: CleaningSummary) => void;
  onBack?: () => void;
  onCancel: () => void;
  applyLabel?: string;
}

const empty = (v: string) => (v === "" ? <span className="text-muted-foreground">Nulo</span> : v);

/** Prévia → confirmação explícita → aplicação. Nada é gravado antes de "Aplicar". */
export function PreviewPanel({ analysisId, request, onApplied, onBack, onCancel, applyLabel = "Aplicar correção" }: Props) {
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [ack, setAck] = useState<string[]>([]);
  const [justification, setJustification] = useState("");
  const [applying, setApplying] = useState(false);
  const key = useMemo(() => JSON.stringify(request), [request]);

  useEffect(() => {
    let live = true;
    setLoading(true); setError(null); setAck([]);
    cleaningService.preview(analysisId, request)
      .then((p) => live && setPreview(p))
      .catch((e) => live && setError(errorMessage(e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId, key]);

  if (loading) return <div className="space-y-2"><Skeleton className="h-6 w-1/2" /><Skeleton className="h-40" /></div>;
  if (error || !preview) return <div className="space-y-3"><p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p><Footer onBack={onBack} onCancel={onCancel} /></div>;

  const nothing = preview.n_changes === 0 && preview.n_removed === 0 && preview.n_exceptions === 0;
  const allAck = preview.requires.every((r) => ack.includes(r.key));
  const needJust = preview.requires_justification && !justification.trim();
  const canApply = !preview.errors.length && !nothing && allAck && !needJust && !applying;

  const apply = async () => {
    setApplying(true);
    try {
      const res = await cleaningService.apply(analysisId, { ...request, acknowledge: ack, justification: justification.trim() || null });
      toast.success(`Correção aplicada. Nova versão: ${res.label}.`);
      onApplied(res.summary);
    } catch (e) { toast.error(errorMessage(e)); setApplying(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge variant="info">{fmtInt(preview.n_rows_affected)} registro(s) afetado(s)</Badge>
        {preview.n_changes > 0 && <Badge variant="muted">{fmtInt(preview.n_changes)} valor(es) alterado(s)</Badge>}
        {preview.n_removed > 0 && <Badge variant="destructive">{fmtInt(preview.n_removed)} registro(s) removido(s)</Badge>}
        {preview.n_exceptions > 0 && <Badge variant="warning">{fmtInt(preview.n_exceptions)} ocorrência(s) mantida(s) como exceção</Badge>}
      </div>

      {preview.errors.map((e, i) => <p key={i} role="alert" className="flex gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive"><XCircle className="mt-0.5 size-4 shrink-0" />{e}</p>)}
      {preview.warnings.map((w, i) => <p key={i} className="flex gap-2 rounded-lg bg-warning/10 p-3 text-sm"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />{w}</p>)}
      {preview.notes.map((n, i) => <p key={i} className="flex gap-2 text-sm text-muted-foreground"><Info className="mt-0.5 size-4 shrink-0" />{n}</p>)}

      {preview.changes.length > 0 && (
        <div>
          <p className="mb-1.5 text-sm font-medium">Prévia das alterações</p>
          <div className="max-h-64 overflow-auto rounded-lg border">
            <Table>
              <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Registro</TableHead><TableHead>Coluna</TableHead><TableHead>Valor original</TableHead><TableHead /><TableHead>Novo valor</TableHead></TableRow></TableHeader>
              <TableBody>{preview.changes.map((c, i) => (
                <TableRow key={i}><TableCell className="font-mono text-xs">{c.row}</TableCell><TableCell>{c.column}</TableCell>
                  <TableCell>{empty(c.old)}</TableCell><TableCell><ArrowRight className="size-3.5 text-muted-foreground" /></TableCell>
                  <TableCell className="font-semibold text-primary">{empty(c.new)}{c.note && <span className="ml-2 text-xs font-normal text-muted-foreground">{c.note}</span>}</TableCell></TableRow>))}</TableBody>
            </Table>
          </div>
          {preview.changes_truncated && <p className="mt-1 text-xs text-muted-foreground">Exibindo as primeiras {preview.changes.length} de {fmtInt(preview.n_changes)} alterações; todas serão aplicadas.</p>}
        </div>
      )}

      {preview.removed.length > 0 && (
        <div>
          <p className="mb-1.5 text-sm font-medium">Registros que serão removidos</p>
          <div className="max-h-48 overflow-auto rounded-lg border">
            <Table>
              <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Linha</TableHead>{Object.keys(preview.removed[0].values).slice(0, 6).map((k) => <TableHead key={k}>{k}</TableHead>)}</TableRow></TableHeader>
              <TableBody>{preview.removed.map((r) => (
                <TableRow key={r.row} className="bg-destructive/[0.04]"><TableCell className="font-mono text-xs">{r.row}</TableCell>
                  {Object.values(r.values).slice(0, 6).map((v, i) => <TableCell key={i} className="max-w-[10rem] truncate">{empty(v)}</TableCell>)}</TableRow>))}</TableBody>
            </Table>
          </div>
        </div>
      )}

      {preview.impact && !nothing && (
        <div className="grid gap-2 rounded-lg bg-muted/60 p-3 text-sm sm:grid-cols-2">
          <p>Pendências: <b>{fmtInt(preview.impact.before.pending)}</b> → <b className="text-primary">{fmtInt(preview.impact.after.pending)}</b></p>
          <p>DataCheck Score: <b>{preview.impact.before.score ?? "—"}</b> → <b className="text-primary">{preview.impact.after.score ?? "—"}</b></p>
        </div>
      )}

      {preview.requires.length > 0 && (
        <div className="space-y-2 rounded-lg border border-warning/40 p-3">
          <p className="text-sm font-medium">Confirmações necessárias</p>
          {preview.requires.map((r) => (
            <label key={r.key} className="flex cursor-pointer items-start gap-2 text-sm">
              <Checkbox className="mt-0.5" checked={ack.includes(r.key)} onCheckedChange={(c) => setAck((a) => c === true ? [...a, r.key] : a.filter((x) => x !== r.key))} />{r.text}
            </label>
          ))}
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="just">Justificativa {preview.requires_justification ? <span className="text-destructive">(obrigatória)</span> : "(opcional)"}</Label>
        <Textarea id="just" value={justification} onChange={(e) => setJustification(e.target.value)} maxLength={2000} className="min-h-[64px]"
          placeholder="Registre o motivo desta decisão. Ela ficará no histórico de correções." />
      </div>

      <Footer onBack={onBack} onCancel={onCancel}>
        <Button onClick={apply} disabled={!canApply}>{applying ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}{applying ? "Aplicando…" : applyLabel}</Button>
      </Footer>
    </div>
  );
}

function Footer({ onBack, onCancel, children }: { onBack?: () => void; onCancel: () => void; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
      {onBack && <Button variant="ghost" onClick={onBack}>Voltar</Button>}
      <Button variant="outline" onClick={onCancel}>Cancelar</Button>{children}
    </div>
  );
}
