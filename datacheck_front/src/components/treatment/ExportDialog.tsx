import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { errorMessage } from "@/lib/api";
import { cleaningService } from "@/services";

export function ExportDialog({ analysisId, filename, versionLabel, onClose }: { analysisId: string; filename: string; versionLabel: string; onClose: () => void }) {
  const [format, setFormat] = useState<"csv" | "xlsx">("xlsx");
  const [delimiter, setDelimiter] = useState("semicolon");
  const [encoding, setEncoding] = useState("utf-8-sig");
  const [decimal, setDecimal] = useState("keep");
  const [summary, setSummary] = useState(true);
  const [busy, setBusy] = useState(false);

  const go = async () => {
    setBusy(true);
    try {
      await cleaningService.download(analysisId, format === "csv" ? { format, delimiter, encoding, decimal } : { format, include_summary: summary }, filename);
      toast.success("Base tratada exportada."); onClose();
    } catch (e) { toast.error(errorMessage(e)); setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title="Baixar base tratada" description={`Versão exportada: ${versionLabel}. O arquivo reflete exatamente as correções confirmadas por você.`} className="max-w-lg">
      <div className="space-y-4">
        <div className="space-y-1.5"><Label>Formato</Label>
          <Select value={format} onValueChange={(v) => setFormat(v as "csv" | "xlsx")}><SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="xlsx">Excel (XLSX)</SelectItem><SelectItem value="csv">CSV</SelectItem></SelectContent></Select></div>
        {format === "csv" ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5"><Label>Delimitador</Label><Select value={delimiter} onValueChange={setDelimiter}><SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="semicolon">Ponto e vírgula ( ; )</SelectItem><SelectItem value="comma">Vírgula ( , )</SelectItem><SelectItem value="tab">Tabulação</SelectItem><SelectItem value="pipe">Barra vertical ( | )</SelectItem></SelectContent></Select></div>
            <div className="space-y-1.5"><Label>Codificação</Label><Select value={encoding} onValueChange={setEncoding}><SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="utf-8-sig">UTF-8 (com BOM, p/ Excel)</SelectItem><SelectItem value="utf-8">UTF-8</SelectItem><SelectItem value="cp1252">Windows-1252</SelectItem><SelectItem value="latin-1">Latin-1</SelectItem></SelectContent></Select></div>
            <div className="space-y-1.5"><Label>Decimal</Label><Select value={decimal} onValueChange={setDecimal}><SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="keep">Manter como está</SelectItem><SelectItem value="comma">Vírgula</SelectItem><SelectItem value="dot">Ponto</SelectItem></SelectContent></Select></div>
          </div>
        ) : (
          <label className="flex cursor-pointer items-center gap-2 text-sm"><Checkbox checked={summary} onCheckedChange={(c) => setSummary(c === true)} />Incluir aba «Resumo do tratamento»</label>
        )}
        <p className="text-xs text-muted-foreground">Identificadores e códigos preservam zeros à esquerda. Textos que parecem fórmulas recebem um apóstrofo para não serem executados pelo Excel.</p>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancelar</Button><Button onClick={go} disabled={busy}><Download />{busy ? "Gerando…" : "Baixar"}</Button></div>
      </div>
    </Modal>
  );
}
