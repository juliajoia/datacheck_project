import { Radar } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { FixTarget } from "@/components/treatment/FixDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { cleaningService } from "@/services";
import type { ColumnStat, OutlierResult } from "@/types";

export function OutliersPane({ analysisId, refreshKey, onFix }: { analysisId: string; refreshKey: number; onFix: (t: FixTarget) => void }) {
  const [cols, setCols] = useState<ColumnStat[]>([]);
  const [column, setColumn] = useState("");
  const [method, setMethod] = useState("iqr");
  const [factor, setFactor] = useState("1.5");
  const [threshold, setThreshold] = useState("3");
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [res, setRes] = useState<OutlierResult | null>(null);
  const [sel, setSel] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    cleaningService.options(analysisId).then((o) => {
      const q = o.columns.filter((c) => c.stat_type === "quant_discrete" || c.stat_type === "quant_continuous");
      setCols(q); setColumn((c) => c || q[0]?.name || "");
    }).catch(() => undefined);
    setRes(null); setSel([]);
  }, [analysisId, refreshKey]);

  const detect = async () => {
    setBusy(true);
    try {
      const params = method === "iqr" ? { factor: Number(factor) } : method === "zscore" ? { threshold: Number(threshold) }
        : { min: min.trim() ? Number(min.replace(",", ".")) : null, max: max.trim() ? Number(max.replace(",", ".")) : null };
      const r = await cleaningService.outliers(analysisId, { column, method, params });
      setRes(r); setSel([]);
      if (r.error) toast.error(r.error);
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  if (!cols.length) return <p className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">Não há variáveis quantitativas nesta base.</p>;
  const cells = (res?.candidates ?? []).filter((c) => sel.includes(c.row)).map((c) => ({ row: c.row, column, value: c.value }));

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold"><Radar className="size-4 text-primary" />Detecção de valores extremos</p>
        <p className="text-xs text-muted-foreground">Valores atípicos <b>não são necessariamente erros</b>. Esta ferramenta aponta candidatos e explica o critério; você decide o que fazer.</p>
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="space-y-1.5"><Label>Coluna</Label>
            <Select value={column} onValueChange={setColumn}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{cols.map((c) => <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1.5"><Label>Critério</Label>
            <Select value={method} onValueChange={setMethod}><SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="iqr">Intervalo interquartil (IQR)</SelectItem><SelectItem value="zscore">Z-score</SelectItem><SelectItem value="limits">Limites definidos por mim</SelectItem></SelectContent></Select></div>
          {method === "iqr" && <div className="space-y-1.5"><Label>Fator (×IQR)</Label><Input inputMode="decimal" value={factor} onChange={(e) => setFactor(e.target.value)} /></div>}
          {method === "zscore" && <div className="space-y-1.5"><Label>Limiar (desvios padrão)</Label><Input inputMode="decimal" value={threshold} onChange={(e) => setThreshold(e.target.value)} /></div>}
          {method === "limits" && <><div className="space-y-1.5"><Label>Mínimo</Label><Input inputMode="decimal" value={min} onChange={(e) => setMin(e.target.value)} /></div><div className="space-y-1.5"><Label>Máximo</Label><Input inputMode="decimal" value={max} onChange={(e) => setMax(e.target.value)} /></div></>}
        </div>
        <Button onClick={detect} disabled={busy || !column}>{busy ? "Detectando…" : "Detectar valores extremos"}</Button>
      </Card>

      {res && !res.error && (
        <Card className="space-y-3 p-4">
          <p className="text-sm">{res.justification}</p>
          <p className="text-xs text-muted-foreground">{res.note} Observações numéricas analisadas: {res.n_numeric}.</p>
          {res.candidates.length === 0 ? <Badge variant="success">Nenhum valor extremo segundo este critério</Badge> : (<>
            <div className="flex flex-wrap items-center gap-2 text-sm"><Badge variant="warning">{res.n_candidates} candidato(s)</Badge>
              <Button size="sm" variant="ghost" onClick={() => setSel(res.candidates.map((c) => c.row))}>Selecionar todos</Button>
              <div className="ml-auto flex flex-wrap gap-2">
                <Button size="sm" variant="outline" disabled={!sel.length} onClick={() => { setSel([]); toast.message("Mantidos como estão. Nenhuma alteração foi feita."); }}>Manter</Button>
                <Button size="sm" variant="outline" disabled={!sel.length} onClick={() => onFix({ action: "set_value", cells })}>Corrigir manualmente…</Button>
                <Button size="sm" variant="outline" disabled={!sel.length} onClick={() => onFix({ action: "mark_missing", cells })}>Marcar como ausente</Button>
                <Button size="sm" variant="outline" disabled={!sel.length || (res.lower == null && res.upper == null)} onClick={() => onFix({ action: "clip", cells, defaults: { lower: res.lower ?? "", upper: res.upper ?? "" } })}>Aplicar limites…</Button>
                <Button size="sm" variant="outline" className="text-destructive" disabled={!sel.length} onClick={() => onFix({ action: "remove_rows", cells })}>Remover registro…</Button>
              </div></div>
            <div className="max-h-96 overflow-auto rounded-lg border"><Table>
              <TableHeader><TableRow className="hover:bg-transparent"><TableHead className="w-10" /><TableHead>Linha</TableHead><TableHead>Valor</TableHead><TableHead>Motivo</TableHead></TableRow></TableHeader>
              <TableBody>{res.candidates.map((c) => (
                <TableRow key={c.row}><TableCell><Checkbox checked={sel.includes(c.row)} onCheckedChange={(v) => setSel((s) => v === true ? [...s, c.row] : s.filter((r) => r !== c.row))} aria-label={`Selecionar linha ${c.row}`} /></TableCell>
                  <TableCell className="font-mono text-xs">{c.row}</TableCell><TableCell className="font-semibold">{c.value}</TableCell><TableCell className="text-muted-foreground">{c.reason}</TableCell></TableRow>))}</TableBody></Table></div></>)}
        </Card>)}
    </div>
  );
}
