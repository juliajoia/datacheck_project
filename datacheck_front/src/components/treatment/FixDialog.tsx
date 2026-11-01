import { useEffect, useMemo, useState } from "react";
import { Modal } from "@/components/Modal";
import { PreviewPanel } from "@/components/treatment/PreviewPanel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cleaningService } from "@/services";
import type { CleaningAction, CleaningRequest, CleaningSummary } from "@/types";

export interface FixTarget {
  action: CleaningAction;
  cells: { row: number; column: string; category?: string; value?: string }[];
  /** Para ações por coluna inteira (ex.: converter formato de toda a coluna). */
  column?: string;
  defaults?: Record<string, unknown>;
}
interface Props { analysisId: string; version: number; target: FixTarget; onClose: () => void; onApplied: (s: CleaningSummary) => void }

const TITLES: Record<CleaningAction, string> = {
  impute: "Imputar valores", remove_duplicates: "Remover duplicatas", merge_duplicates: "Mesclar duplicatas",
  set_value: "Corrigir manualmente", mark_missing: "Marcar como ausente", convert_number: "Converter formato numérico",
  convert_date: "Converter formato de data", clip: "Aplicar limites de substituição", swap_latlon: "Inverter latitude e longitude",
  remove_rows: "Remover registros", accept_exception: "Manter com justificativa",
};
const DESCRIPTIONS: Partial<Record<CleaningAction, string>> = {
  mark_missing: "Os valores ficam vazios (ausentes) e poderão ser tratados depois pela imputação.",
  remove_rows: "Os registros deixam de existir na versão tratada. A base original permanece intacta e pode ser restaurada.",
  accept_exception: "As ocorrências permanecem como estão e ficam registradas como decisão sua. A justificativa é obrigatória.",
  clip: "Valores atípicos não são necessariamente erros. Substitua pelos limites somente se tiver certeza.",
  swap_latlon: "Troca o conteúdo das colunas de latitude e longitude nos registros selecionados.",
};
const DATE_FORMATS = [["auto", "Automático"], ["%Y-%m-%d", "AAAA-MM-DD"], ["%d/%m/%Y", "DD/MM/AAAA"], ["%d-%m-%Y", "DD-MM-AAAA"], ["%m/%d/%Y", "MM/DD/AAAA"]] as const;
const NEEDS_FORM: CleaningAction[] = ["set_value", "convert_number", "convert_date", "clip", "swap_latlon"];

export function FixDialog({ analysisId, version, target, onClose, onApplied }: Props) {
  const { action, cells, column } = target;
  const [step, setStep] = useState<"form" | "preview">(NEEDS_FORM.includes(action) ? "form" : "preview");
  const [values, setValues] = useState<Record<string, string>>({});
  const [common, setCommon] = useState("");
  const [srcDec, setSrcDec] = useState("auto");
  const [dstDec, setDstDec] = useState("dot");
  const [srcFmt, setSrcFmt] = useState("auto");
  const [dstFmt, setDstFmt] = useState("%Y-%m-%d");
  const [lower, setLower] = useState(String(target.defaults?.lower ?? ""));
  const [upper, setUpper] = useState(String(target.defaults?.upper ?? ""));
  const [geo, setGeo] = useState<{ lat: string; lon: string }>({ lat: "", lon: "" });

  useEffect(() => {
    if (action === "swap_latlon") cleaningService.coordinateSuggestions(analysisId).then((g) => setGeo({ lat: g.lat_column ?? "", lon: g.lon_column ?? "" })).catch(() => undefined);
  }, [action, analysisId]);

  const many = cells.length > 20;
  const request = useMemo<CleaningRequest>(() => {
    const base: CleaningRequest = { base_version: version, action, column: column ?? null, scope: column && !cells.length ? "column_all" : "selected" };
    const rows = cells.map((c) => c.row);
    switch (action) {
      case "set_value":
        return { ...base, cells: cells.map((c) => ({ row: c.row, column: c.column, value: many || !values[`${c.row}|${c.column}`] ? common : values[`${c.row}|${c.column}`] })) };
      case "convert_number":
        return { ...base, cells: cells.map((c) => ({ row: c.row, column: c.column })), params: { source_decimal: srcDec, target_decimal: dstDec } };
      case "convert_date":
        return { ...base, cells: cells.map((c) => ({ row: c.row, column: c.column })), params: { source_format: srcFmt === "auto" ? null : srcFmt, target_format: dstFmt } };
      case "clip":
        return { ...base, cells: cells.map((c) => ({ row: c.row, column: c.column })), column: cells[0]?.column ?? column,
          params: { lower: lower.trim() ? Number(lower.replace(",", ".")) : null, upper: upper.trim() ? Number(upper.replace(",", ".")) : null } };
      case "swap_latlon":
        return { ...base, rows, params: { lat_column: geo.lat, lon_column: geo.lon } };
      case "remove_rows":
        return { ...base, rows: [...new Set(rows)] };
      case "accept_exception":
        return { ...base, cells: cells.map((c) => ({ row: c.row, column: c.column, category: c.category })) };
      default:
        return { ...base, cells: cells.map((c) => ({ row: c.row, column: c.column })) };
    }
  }, [action, cells, column, version, values, common, srcDec, dstDec, srcFmt, dstFmt, lower, upper, geo, many]);

  const formReady = action === "set_value" ? (many ? common.trim() !== "" : cells.every((c) => (values[`${c.row}|${c.column}`] ?? common).trim() !== ""))
    : action === "clip" ? lower.trim() !== "" || upper.trim() !== "" : action === "swap_latlon" ? !!geo.lat && !!geo.lon : true;

  return (
    <Modal open onClose={onClose} title={TITLES[action]} description={DESCRIPTIONS[action]}>
      {step === "form" ? (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">{cells.length} registro(s) selecionado(s).</p>
          {action === "set_value" && (many
            ? <div className="space-y-1.5"><Label>Novo valor (aplicado a todos os selecionados)</Label><Input value={common} onChange={(e) => setCommon(e.target.value)} /></div>
            : <div className="space-y-2">{cells.map((c) => (
              <div key={`${c.row}|${c.column}`} className="grid items-center gap-2 sm:grid-cols-[8rem_1fr_1fr]">
                <span className="text-xs text-muted-foreground">Linha {c.row} · {c.column}</span>
                <code className="truncate rounded bg-muted px-2 py-1 text-xs">{c.value || "(vazio)"}</code>
                <Input value={values[`${c.row}|${c.column}`] ?? ""} onChange={(e) => setValues((v) => ({ ...v, [`${c.row}|${c.column}`]: e.target.value }))} placeholder="Novo valor" aria-label={`Novo valor da linha ${c.row}`} />
              </div>))}</div>)}
          {action === "convert_number" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5"><Label>Separador decimal de origem</Label>
                <Select value={srcDec} onValueChange={setSrcDec}><SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="auto">Automático</SelectItem><SelectItem value="comma">Vírgula (1.234,5)</SelectItem><SelectItem value="dot">Ponto (1,234.5)</SelectItem></SelectContent></Select></div>
              <div className="space-y-1.5"><Label>Separador decimal de destino</Label>
                <Select value={dstDec} onValueChange={setDstDec}><SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="dot">Ponto (1234.5)</SelectItem><SelectItem value="comma">Vírgula (1234,5)</SelectItem></SelectContent></Select></div>
              <p className="text-xs text-muted-foreground sm:col-span-2">Valores que não puderem ser interpretados (ex.: «12,5x») permanecem como estão e são listados na prévia.</p>
            </div>)}
          {action === "convert_date" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5"><Label>Formato de origem</Label>
                <Select value={srcFmt} onValueChange={setSrcFmt}><SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{DATE_FORMATS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-1.5"><Label>Formato de destino</Label>
                <Select value={dstFmt} onValueChange={setDstFmt}><SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{DATE_FORMATS.slice(1).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent></Select></div>
              <p className="text-xs text-muted-foreground sm:col-span-2">Datas desconhecidas nunca são inventadas: valores não interpretáveis permanecem como estão.</p>
            </div>)}
          {action === "clip" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5"><Label>Limite inferior</Label><Input inputMode="decimal" value={lower} onChange={(e) => setLower(e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Limite superior</Label><Input inputMode="decimal" value={upper} onChange={(e) => setUpper(e.target.value)} /></div>
            </div>)}
          {action === "swap_latlon" && (geo.lat && geo.lon
            ? <p className="text-sm">Colunas: latitude <b>{geo.lat}</b> ↔ longitude <b>{geo.lon}</b>.</p>
            : <p className="text-sm text-destructive">Defina as colunas de latitude e longitude na configuração da análise para usar esta ação.</p>)}
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancelar</Button><Button disabled={!formReady} onClick={() => setStep("preview")}>Ver prévia das alterações</Button></div>
        </div>
      ) : (
        <PreviewPanel analysisId={analysisId} request={request} onBack={NEEDS_FORM.includes(action) ? () => setStep("form") : undefined}
          onCancel={onClose} onApplied={(s) => { onApplied(s); onClose(); }} />
      )}
    </Modal>
  );
}
