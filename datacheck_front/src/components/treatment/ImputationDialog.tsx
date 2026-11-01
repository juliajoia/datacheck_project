import { Lightbulb, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ColumnPicker } from "@/components/ColumnPicker";
import { Modal } from "@/components/Modal";
import { PreviewPanel } from "@/components/treatment/PreviewPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { cleaningService } from "@/services";
import type { CleaningRequest, CleaningSummary, ColumnOptions } from "@/types";

interface Props {
  analysisId: string; version: number; column: string; rows: number[];  // rows vazio = todos os ausentes da coluna
  onClose: () => void; onApplied: (s: CleaningSummary) => void;
}

const pct = (x: number) => `${x.toFixed(1).replace(".", ",")}%`;
const NONE = "__none__";

export function ImputationDialog({ analysisId, version, column, rows, onClose, onApplied }: Props) {
  const [opts, setOpts] = useState<ColumnOptions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"configure" | "preview">("configure");
  const [scope, setScope] = useState<"selected" | "column_all">(rows.length ? "selected" : "column_all");
  const [method, setMethod] = useState("");
  const [value, setValue] = useState("");
  const [perRow, setPerRow] = useState<Record<number, string>>({});
  const [text, setText] = useState("");
  const [groupBy, setGroupBy] = useState<string[]>([]);
  const [statistic, setStatistic] = useState("median");
  const [minGroup, setMinGroup] = useState("3");
  const [fallback, setFallback] = useState(NONE);
  const [fallbackValue, setFallbackValue] = useState("");
  const [orderBy, setOrderBy] = useState("");
  const [interpGroup, setInterpGroup] = useState<string[]>([]);
  const [showWhy, setShowWhy] = useState(false);

  useEffect(() => {
    cleaningService.options(analysisId, column).then((o) => {
      setOpts(o);
      const r = o.recommendation;
      const avail = new Set(o.methods?.filter((m) => m.available).map((m) => m.key));
      setMethod(r && avail.has(r.method) ? r.method : "");
      if (r?.statistic) setStatistic(r.statistic);
      if (r?.group_by) setGroupBy(r.group_by);
      setText(o.not_informed_text ?? "");
      setOrderBy(o.order_columns?.[0] ?? "");
    }).catch((e) => setError(errorMessage(e)));
  }, [analysisId, column]);

  const prof = opts?.profile, rec = opts?.recommendation;
  const isQual = prof?.stat_type === "nominal" || prof?.stat_type === "ordinal";
  const isIdent = prof?.stat_type === "identifier";

  const request = useMemo<CleaningRequest>(() => {
    const params: Record<string, unknown> = { method };
    if (method === "constant") {
      if (isIdent || Object.keys(perRow).length) params.values = Object.fromEntries(Object.entries(perRow).filter(([, v]) => v.trim()));
      params.value = value;
    }
    if (method === "not_informed" && isQual) params.text = text;
    if (method === "group") {
      Object.assign(params, { group_by: groupBy, statistic: isQual ? "mode" : statistic, min_group_size: Number(minGroup) || 3 });
      if (fallback !== NONE) Object.assign(params, { fallback, fallback_value: fallbackValue });
    }
    if (method === "interpolate") Object.assign(params, { order_by: orderBy, group_by: interpGroup });
    return { base_version: version, action: "impute", column, scope, rows: scope === "selected" ? rows : [], params };
  }, [method, value, perRow, text, groupBy, statistic, minGroup, fallback, fallbackValue, orderBy, interpGroup, scope, rows, column, version, isIdent, isQual]);

  const methodMeta = opts?.methods?.find((m) => m.key === method);
  const others = (opts?.columns ?? []).filter((c) => c.name !== column).map((c) => c.name);
  const configError = !method ? "Escolha um método." : method === "group" && !groupBy.length ? "Escolha ao menos uma coluna de agrupamento."
    : method === "interpolate" && !orderBy ? "Escolha a coluna de ordenação."
    : method === "constant" && !value.trim() && !Object.values(perRow).some((v) => v.trim()) ? "Informe o valor." : null;

  return (
    <Modal open onClose={onClose} title="Tratamento de valores ausentes"
      description="Revise o método sugerido, escolha como tratar e confira a prévia. Nada é alterado antes da sua confirmação.">
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!opts && !error && <Skeleton className="h-64" />}
      {opts && prof && rec && step === "configure" && (
        <div className="space-y-5">
          <div className="grid gap-2 rounded-xl bg-muted/60 p-4 text-sm sm:grid-cols-2">
            <p><span className="text-muted-foreground">Coluna:</span> <b>{column}</b></p>
            <p><span className="text-muted-foreground">Tipo:</span> <b>{prof.stat_label}</b></p>
            <p><span className="text-muted-foreground">Valores ausentes:</span> <b>{prof.n_missing}</b></p>
            <p><span className="text-muted-foreground">Percentual:</span> <b>{pct(prof.pct_missing)}</b></p>
          </div>

          <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold"><Lightbulb className="size-4 text-primary" />Método recomendado pelo DataCheck: {rec.label}</p>
            <p className="mt-1 text-sm">{rec.justification}</p>
            {rec.warnings.map((w, i) => <p key={i} className="mt-2 flex gap-2 text-sm text-muted-foreground"><TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" />{w}</p>)}
            <div className="mt-2 flex flex-wrap gap-2">
              {opts.methods?.some((m) => m.key === rec.method && m.available) && method !== rec.method && (
                <Button size="sm" variant="outline" onClick={() => { setMethod(rec.method); if (rec.group_by) setGroupBy(rec.group_by); if (rec.statistic) setStatistic(rec.statistic); }}>Usar o método recomendado</Button>)}
              <Button size="sm" variant="ghost" onClick={() => setShowWhy((s) => !s)}>{showWhy ? "Ocultar" : "Como o método é escolhido?"}</Button>
            </div>
            {showWhy && <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted-foreground">{opts.methodology.map((m, i) => <li key={i}>{m}</li>)}</ul>}
            {rec.method === "manual_review" && <p className="mt-2 text-sm font-medium">Identificadores exigem revisão manual: informe valores registro a registro.</p>}
          </div>

          {rows.length > 0 && (
            <fieldset className="space-y-2"><legend className="text-sm font-medium">Aplicar em</legend>
              {([["selected", rows.length === 1 ? "Somente o registro selecionado" : `Somente os ${rows.length} registros selecionados`], ["column_all", `Todos os valores ausentes da coluna (${prof.n_missing})`]] as const).map(([v, l]) => (
                <label key={v} className="flex cursor-pointer items-center gap-2 text-sm"><input type="radio" name="scope" checked={scope === v} onChange={() => setScope(v)} className="accent-[hsl(var(--primary))]" />{l}</label>))}
            </fieldset>
          )}

          <fieldset className="space-y-2"><legend className="text-sm font-medium">Método de tratamento</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {opts.methods?.map((m) => (
                <button key={m.key} type="button" disabled={!m.available} onClick={() => setMethod(m.key)} aria-pressed={method === m.key}
                  className={cn("rounded-lg border p-3 text-left text-sm transition-colors", method === m.key ? "border-primary bg-primary/10" : "bg-card hover:bg-accent", !m.available && "cursor-not-allowed opacity-50 hover:bg-card")}>
                  <span className="flex items-center gap-2 font-medium">{m.label}{m.key === rec.method && <Badge variant="info">sugerido</Badge>}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{m.available ? m.description : m.reason}</span>
                </button>))}
            </div>
          </fieldset>

          {method === "constant" && (
            <div className="space-y-2">
              {isIdent && scope === "selected" ? rows.slice(0, 20).map((r) => (
                <div key={r} className="flex items-center gap-2"><Label className="w-24 shrink-0 text-xs">Linha {r}</Label>
                  <Input value={perRow[r] ?? ""} onChange={(e) => setPerRow((p) => ({ ...p, [r]: e.target.value }))} placeholder="Valor do identificador" /></div>))
                : <div className="space-y-1.5"><Label>Valor de preenchimento</Label><Input value={value} onChange={(e) => setValue(e.target.value)} placeholder={isQual ? "Categoria personalizada" : "Valor"} /></div>}
            </div>
          )}
          {method === "not_informed" && isQual && <div className="space-y-1.5"><Label>Texto da categoria</Label><Input value={text} onChange={(e) => setText(e.target.value)} /></div>}
          {method === "not_informed" && !isQual && <p className="rounded-lg bg-muted/60 p-3 text-sm">Em colunas numéricas o valor continua <b>nulo</b>: escrever «Não Informado» alteraria o tipo de armazenamento e poderia prejudicar cálculos posteriores. A decisão será registrada no histórico.</p>}
          {method === "group" && (
            <div className="space-y-3">
              <div className="space-y-1.5"><Label>Colunas de agrupamento</Label>
                <ColumnPicker columns={others} value={groupBy} onChange={setGroupBy} emptyHint="Escolha uma ou mais colunas." />
                {opts.group_candidates && opts.group_candidates.length > 0 && <p className="text-xs text-muted-foreground">Colunas que mais explicam a variação: {opts.group_candidates.map((g) => `${g.column} (η² ${(g.eta_squared * 100).toFixed(0)}%)`).join(", ")}.</p>}</div>
              <div className="grid gap-3 sm:grid-cols-3">
                {!isQual && <div className="space-y-1.5"><Label>Estatística</Label>
                  <Select value={statistic} onValueChange={setStatistic}><SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="mean">Média</SelectItem><SelectItem value="median">Mediana</SelectItem><SelectItem value="mode">Moda</SelectItem></SelectContent></Select></div>}
                <div className="space-y-1.5"><Label>Observações mínimas por grupo</Label><Input inputMode="numeric" value={minGroup} onChange={(e) => setMinGroup(e.target.value)} /></div>
                <div className="space-y-1.5"><Label>Se o grupo for insuficiente</Label>
                  <Select value={fallback} onValueChange={setFallback}><SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value={NONE}>Deixar sem tratar</SelectItem>
                      {!isQual && <><SelectItem value="mean">Média geral</SelectItem><SelectItem value="median">Mediana geral</SelectItem></>}
                      <SelectItem value="mode">Moda geral</SelectItem><SelectItem value="constant">Valor fixo</SelectItem></SelectContent></Select></div>
              </div>
              {fallback === "constant" && <Input value={fallbackValue} onChange={(e) => setFallbackValue(e.target.value)} placeholder="Valor para grupos insuficientes" />}
            </div>
          )}
          {method === "interpolate" && (
            <div className="space-y-3">
              <div className="space-y-1.5"><Label>Coluna de ordenação (data ou número)</Label>
                <Select value={orderBy || undefined} onValueChange={setOrderBy}><SelectTrigger><SelectValue placeholder="Escolha a coluna" /></SelectTrigger>
                  <SelectContent>{opts.order_columns?.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-1.5"><Label>Interpolar dentro de grupos (opcional)</Label><ColumnPicker columns={others} value={interpGroup} onChange={setInterpGroup} emptyHint="Sem grupos: uma única série." /></div>
              <p className="text-xs text-muted-foreground">Use apenas quando os registros formarem uma sequência lógica. Pontas da série não são extrapoladas.</p>
            </div>
          )}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
            {configError && <p className="text-sm text-muted-foreground sm:mr-auto">{configError}</p>}
            {methodMeta && !methodMeta.available && <p className="text-sm text-destructive sm:mr-auto">{methodMeta.reason}</p>}
            <Button variant="outline" onClick={onClose}>Cancelar</Button>
            <Button disabled={!!configError || !!(methodMeta && !methodMeta.available)} onClick={() => setStep("preview")}>Ver prévia das alterações</Button>
          </div>
        </div>
      )}
      {opts && step === "preview" && (
        <PreviewPanel analysisId={analysisId} request={request} onBack={() => setStep("configure")} onCancel={onClose}
          onApplied={(s) => { onApplied(s); onClose(); }} />
      )}
    </Modal>
  );
}
