import { CheckCheck, Loader2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ColumnPicker } from "@/components/ColumnPicker";
import { Modal } from "@/components/Modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api";
import { edaService } from "@/services";
import type { EdaOptions } from "@/types/eda";
import { fmtDateTime, fmtInt } from "@/utils/format";

const AUTO = "__auto__";

export function GenerateEdaDialog({ analysisId, analysisName, onClose }: { analysisId: string; analysisName: string; onClose: () => void }) {
  const navigate = useNavigate();
  const [opts, setOpts] = useState<EdaOptions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState(`EDA — ${analysisName.replace(/\.[^.]+$/, "")}`);
  const [sections, setSections] = useState<string[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [method, setMethod] = useState<"pearson" | "spearman">("pearson");
  const [percentiles, setPercentiles] = useState("5, 25, 50, 75, 95");
  const [dateCol, setDateCol] = useState(AUTO);
  const [freq, setFreq] = useState<"D" | "M" | "Y">("M");
  const [valueCols, setValueCols] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    edaService.options(analysisId).then((o) => { setOpts(o); setSections(o.sections.filter((s) => s.ok).map((s) => s.key)); }).catch((e) => setError(errorMessage(e)));
  }, [analysisId]);

  const pctError = useMemo(() => {
    const vals = percentiles.split(/[,;\s]+/).filter(Boolean).map(Number);
    return vals.length === 0 || vals.some((v) => !Number.isFinite(v) || v <= 0 || v >= 100) ? "Use números entre 0 e 100, separados por vírgula." : null;
  }, [percentiles]);

  const submit = async () => {
    if (!opts) return;
    setBusy(true);
    try {
      await edaService.generate(analysisId, {
        report_name: name.trim() || "Análise exploratória", version_number: opts.version.number, sections, columns,
        correlation_method: method, percentiles: percentiles.split(/[,;\s]+/).filter(Boolean).map(Number),
        temporal: { date_column: dateCol === AUTO ? null : dateCol, frequency: freq, value_columns: valueCols },
      });
      toast.success("Geração iniciada. O relatório aparecerá na página EDA.");
      navigate("/eda");
    } catch (e) { toast.error(errorMessage(e)); setBusy(false); }
  };

  const applicableCols = opts?.columns.filter((c) => c.stat_type !== "identifier").map((c) => c.name) ?? [];
  return (
    <Modal open onClose={onClose} title="Gerar análise exploratória (EDA)" description="Escolha o que incluir no relatório. Só serão calculadas as análises compatíveis com o tipo de cada variável.">
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!opts && !error && <Skeleton className="h-72" />}
      {opts && (
        <div className="space-y-5">
          <div className="grid gap-2 rounded-xl bg-muted/60 p-4 text-sm sm:grid-cols-2">
            <p><span className="text-muted-foreground">Análise:</span> <b>{analysisName}</b></p>
            <p><span className="text-muted-foreground">Versão dos dados:</span> <b>{opts.version.label}</b> (nº {opts.version.number})</p>
            <p><span className="text-muted-foreground">Registros:</span> <b>{fmtInt(opts.version.rows)}</b> · <span className="text-muted-foreground">Variáveis:</span> <b>{opts.version.columns}</b></p>
            <p><span className="text-muted-foreground">Data da versão:</span> <b>{fmtDateTime(opts.version.created_at)}</b></p>
            <p className="sm:col-span-2 flex flex-wrap items-center gap-2"><span className="text-muted-foreground">Status de qualidade:</span>
              {opts.readiness.ready ? <Badge variant="success">Pronta para EDA</Badge> : <Badge variant="warning">{opts.readiness.pending} pendência(s)</Badge>}
              <span className="text-muted-foreground">Score {opts.readiness.score ?? "—"} (cobre apenas as regras executadas)</span></p>
          </div>

          {!opts.readiness.ready ? <p role="alert" className="rounded-lg bg-warning/10 p-3 text-sm">{opts.message}</p> : (<>
            <div className="space-y-1.5"><Label htmlFor="eda-name">Nome do relatório</Label><Input id="eda-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={255} /></div>

            <fieldset className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2"><legend className="text-sm font-medium">Seções do relatório</legend>
                <Button type="button" size="sm" variant="outline" onClick={() => setSections(opts.sections.filter((s) => s.ok).map((s) => s.key))}><CheckCheck />Selecionar todas as análises aplicáveis</Button></div>
              <div className="grid gap-2 sm:grid-cols-2">
                {opts.sections.map((s) => (
                  <label key={s.key} className={`flex items-start gap-2 rounded-lg border p-2.5 text-sm ${s.ok ? "cursor-pointer" : "opacity-55"}`}>
                    <Checkbox className="mt-0.5" disabled={!s.ok} checked={sections.includes(s.key)} onCheckedChange={(c) => setSections((x) => c === true ? [...x, s.key] : x.filter((k) => k !== s.key))} />
                    <span>{s.label}{!s.ok && s.reason && <span className="block text-xs text-muted-foreground">{s.reason}</span>}</span>
                  </label>))}
              </div>
            </fieldset>

            <div className="space-y-1.5"><Label>Colunas incluídas (opcional)</Label>
              <ColumnPicker columns={applicableCols} value={columns} onChange={setColumns} emptyHint="Todas as colunas aplicáveis. Identificadores não entram nas análises estatísticas." /></div>

            <div className="grid gap-3 sm:grid-cols-2">
              {sections.includes("correlation") && <div className="space-y-1.5"><Label>Correlação</Label>
                <Select value={method} onValueChange={(v) => setMethod(v as "pearson" | "spearman")}><SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="pearson">Pearson (relação linear)</SelectItem><SelectItem value="spearman">Spearman (relação monotônica, por postos)</SelectItem></SelectContent></Select></div>}
              {sections.includes("descriptive") && <div className="space-y-1.5"><Label htmlFor="pct">Percentis</Label><Input id="pct" value={percentiles} onChange={(e) => setPercentiles(e.target.value)} aria-invalid={!!pctError} />
                {pctError && <p className="text-xs text-destructive">{pctError}</p>}</div>}
            </div>

            {sections.includes("temporal") && (
              <div className="grid gap-3 rounded-lg border p-3 sm:grid-cols-3">
                <div className="space-y-1.5"><Label>Coluna de data</Label>
                  <Select value={dateCol} onValueChange={setDateCol}><SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value={AUTO}>Automática</SelectItem>{opts.temporal_columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
                <div className="space-y-1.5"><Label>Agrupar por</Label>
                  <Select value={freq} onValueChange={(v) => setFreq(v as "D" | "M" | "Y")}><SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="D">Dia</SelectItem><SelectItem value="M">Mês</SelectItem><SelectItem value="Y">Ano</SelectItem></SelectContent></Select></div>
                <div className="space-y-1.5 sm:col-span-3"><Label>Evolução de variáveis numéricas (opcional, até 3)</Label>
                  <ColumnPicker columns={opts.numeric_columns} value={valueCols} onChange={(v) => setValueCols(v.slice(0, 3))} emptyHint="Sem escolha, as duas primeiras variáveis quantitativas." /></div>
              </div>)}
          </>)}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancelar</Button>
            <Button variant="brand" disabled={busy || !opts.readiness.ready || sections.length === 0 || !!pctError} onClick={submit}>{busy ? <Loader2 className="animate-spin" /> : <Sparkles />}{busy ? "Iniciando…" : "Gerar relatório"}</Button>
          </div>
        </div>)}
    </Modal>
  );
}
