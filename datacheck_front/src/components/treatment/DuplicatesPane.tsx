import { Layers, Merge, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Modal } from "@/components/Modal";
import type { FixTarget } from "@/components/treatment/FixDialog";
import { PreviewPanel } from "@/components/treatment/PreviewPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { cleaningService } from "@/services";
import type { CleaningRequest, CleaningSummary, DuplicateGroup, DuplicatesInfo } from "@/types";

type Dialog = { request: CleaningRequest; title: string } | { merge: DuplicateGroup } | null;
interface Props { analysisId: string; version: number; refreshKey: number; onApplied: (s: CleaningSummary) => void; onFix: (t: FixTarget) => void }

export function DuplicatesPane({ analysisId, version, refreshKey, onApplied, onFix }: Props) {
  const [info, setInfo] = useState<DuplicatesInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [keep, setKeep] = useState<Record<number, number[]>>({});
  const [chosen, setChosen] = useState<number[]>([]);
  const [dateCol, setDateCol] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);

  useEffect(() => {
    setInfo(null); setKeep({}); setChosen([]);
    cleaningService.duplicates(analysisId).then((d) => { setInfo(d); setDateCol(d.temporal_columns[0] ?? ""); }).catch((e) => setError(errorMessage(e)));
  }, [analysisId, refreshKey]);

  if (error) return <p role="alert" className="text-sm text-destructive">{error}</p>;
  if (!info) return <Skeleton className="h-64" />;
  if (info.total_groups === 0) return <p className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">Nenhum registro duplicado nesta versão.</p>;

  const strategy = (s: string) => setDialog({ title: "Remoção de duplicatas", request: { base_version: version, action: "remove_duplicates",
    params: { strategy: s, date_column: dateCol || undefined, groups: chosen.length ? chosen : undefined } } });
  const decide = (g: DuplicateGroup) => setDialog({ title: `Grupo ${g.id}: manter os registros escolhidos`, request: { base_version: version, action: "remove_duplicates",
    params: { decisions: [{ group: g.id, keep: keep[g.id] ?? [] }] } } });
  const toggleKeep = (g: DuplicateGroup, row: number) => setKeep((k) => { const cur = k[g.id] ?? []; return { ...k, [g.id]: cur.includes(row) ? cur.filter((r) => r !== row) : [...cur, row] }; });

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Layers className="size-4 text-primary" /><b>{info.total_groups}</b> grupo(s) de duplicatas
          {info.conflicting_groups > 0 && <Badge variant="warning">{info.conflicting_groups} com valores conflitantes</Badge>}
          <span className="text-muted-foreground">· critério: {info.key_columns.length ? `colunas-chave (${info.key_columns.join(", ")})` : "linha completa"}</span>
        </div>
        <p className="text-xs text-muted-foreground">As estratégias abaixo são <b>sugestões</b>: você verá a prévia e confirmará antes de qualquer remoção. {chosen.length ? `Valem para os ${chosen.length} grupo(s) marcados.` : "Sem grupos marcados, valem para todos."}</p>
        <div className="flex flex-wrap items-end gap-2">
          <Button size="sm" variant="outline" onClick={() => strategy("first")}>Manter o primeiro</Button>
          <Button size="sm" variant="outline" onClick={() => strategy("last")}>Manter o último</Button>
          <Button size="sm" variant="outline" onClick={() => strategy("most_complete")}>Manter o mais completo</Button>
          {info.temporal_columns.length > 0 && (
            <div className="flex items-end gap-2">
              <div className="w-44"><Label className="text-xs">Coluna de data</Label>
                <Select value={dateCol} onValueChange={setDateCol}><SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                  <SelectContent>{info.temporal_columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
              <Button size="sm" variant="outline" onClick={() => strategy("latest")}>Manter o mais recente</Button>
            </div>)}
        </div>
      </Card>

      {info.groups.map((g) => (
        <Card key={g.id} className={cn("space-y-3 p-4", chosen.includes(g.id) && "ring-1 ring-primary")}>
          <div className="flex flex-wrap items-center gap-2">
            <Checkbox checked={chosen.includes(g.id)} onCheckedChange={(c) => setChosen((x) => c === true ? [...x, g.id] : x.filter((i) => i !== g.id))} aria-label={`Marcar grupo ${g.id}`} />
            <b className="text-sm">Grupo {g.id}</b><Badge variant="muted">{g.rows.length} registros</Badge>
            {g.exact ? <Badge variant="success">duplicata exata</Badge> : <Badge variant="warning">conflito em: {g.conflicts.join(", ")}</Badge>}
          </div>
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Manter</TableHead><TableHead>Linha</TableHead>
                {Object.keys(g.records[0].values).map((k) => <TableHead key={k} className={cn(g.conflicts.includes(k) && "text-warning")}>{k}</TableHead>)}</TableRow></TableHeader>
              <TableBody>{g.records.map((r) => (
                <TableRow key={r.row} className={(keep[g.id] ?? []).includes(r.row) ? "bg-success/5" : ""}>
                  <TableCell><Checkbox checked={(keep[g.id] ?? []).includes(r.row)} onCheckedChange={() => toggleKeep(g, r.row)} aria-label={`Manter a linha ${r.row}`} /></TableCell>
                  <TableCell className="font-mono text-xs">{r.row}</TableCell>
                  {Object.entries(r.values).map(([k, v]) => <TableCell key={k} className={cn("max-w-[10rem] truncate", g.conflicts.includes(k) && "font-semibold text-warning")}>{v || <span className="text-muted-foreground">—</span>}</TableCell>)}
                </TableRow>))}</TableBody>
            </Table>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={!(keep[g.id] ?? []).length} onClick={() => decide(g)}>Manter os marcados e remover os demais</Button>
            <Button size="sm" variant="outline" onClick={() => setDialog({ merge: g })}><Merge />Mesclar registros…</Button>
            <Button size="sm" variant="ghost" onClick={() => onFix({ action: "accept_exception", cells: g.rows.map((row) => ({ row, column: info.issue_column, category: "duplicados" })) })}><ShieldCheck />Manter todos (legítimo)…</Button>
          </div>
        </Card>
      ))}
      {info.truncated && <p className="text-xs text-muted-foreground">Exibindo parte dos grupos; aplique estratégias para tratar todos.</p>}

      {dialog && "request" in dialog && (
        <Modal open onClose={() => setDialog(null)} title={dialog.title}>
          <PreviewPanel analysisId={analysisId} request={dialog.request} onCancel={() => setDialog(null)} onApplied={(s) => { setDialog(null); onApplied(s); }} />
        </Modal>)}
      {dialog && "merge" in dialog && <MergeDialog analysisId={analysisId} version={version} group={dialog.merge} onClose={() => setDialog(null)} onApplied={(s) => { setDialog(null); onApplied(s); }} />}
    </div>
  );
}

function MergeDialog({ analysisId, version, group, onClose, onApplied }: { analysisId: string; version: number; group: DuplicateGroup; onClose: () => void; onApplied: (s: CleaningSummary) => void }) {
  const [keepRow, setKeepRow] = useState(group.rows[0]);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [step, setStep] = useState<"choose" | "preview">("choose");
  const missingChoice = group.merge.conflicts.filter((c) => !picked[c]);
  const request = useMemo<CleaningRequest>(() => ({ base_version: version, action: "merge_duplicates", params: { merges: [{ group: group.id, keep_row: keepRow, values: picked }] } }), [version, group, keepRow, picked]);
  return (
    <Modal open onClose={onClose} title={`Mesclar registros do grupo ${group.id}`}
      description="A linha mantida recebe os valores combinados e as demais são removidas. Quando houver informações conflitantes, você escolhe o valor final: a mesclagem nunca é automática.">
      {step === "choose" ? (
        <div className="space-y-4">
          <div className="space-y-1.5"><Label>Linha que será mantida</Label>
            <Select value={String(keepRow)} onValueChange={(v) => setKeepRow(Number(v))}><SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{group.rows.map((r) => <SelectItem key={r} value={String(r)}>Linha {r}</SelectItem>)}</SelectContent></Select></div>
          {group.merge.conflicts.length === 0 ? <p className="rounded-lg bg-success/10 p-3 text-sm">Os registros são complementares: não há valores conflitantes. O registro combinado terá os valores preenchidos de qualquer uma das linhas.</p>
            : group.merge.conflicts.map((col) => {
              const options = [...new Set(group.records.map((r) => r.values[col].trim()).filter(Boolean))];
              return (
                <fieldset key={col} className="space-y-1.5"><legend className="text-sm font-medium">Conflito em «{col}»: escolha o valor final</legend>
                  {options.map((o) => <label key={o} className="flex cursor-pointer items-center gap-2 text-sm"><input type="radio" name={col} checked={picked[col] === o} onChange={() => setPicked((p) => ({ ...p, [col]: o }))} className="accent-[hsl(var(--primary))]" />{o}</label>)}
                </fieldset>);
            })}
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancelar</Button>
            <Button disabled={missingChoice.length > 0} onClick={() => setStep("preview")}>{missingChoice.length ? `Escolha ${missingChoice.join(", ")}` : "Ver prévia"}</Button></div>
        </div>
      ) : <PreviewPanel analysisId={analysisId} request={request} onBack={() => setStep("choose")} onCancel={onClose} onApplied={onApplied} />}
    </Modal>
  );
}
