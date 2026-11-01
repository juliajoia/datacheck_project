import { ArrowRight, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { CleaningSummary } from "@/types";
import { fmtInt } from "@/utils/format";

const Row = ({ label, a, b }: { label: string; a: string | number; b: string | number }) => (
  <div className="flex items-center justify-between gap-3 border-b py-2 text-sm last:border-0">
    <span className="text-muted-foreground">{label}</span>
    <span className="flex items-center gap-2 font-medium">{a}<ArrowRight className="size-3.5 text-muted-foreground" /><b className="text-primary">{b}</b></span>
  </div>
);

export function BeforeAfterPane({ s, validating, onValidate }: { s: CleaningSummary; validating: boolean; onValidate: () => void }) {
  const o = s.operations;
  const n = (x: number | null | undefined) => (x == null ? "—" : x.toLocaleString("pt-BR"));
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <p className="mb-2 text-sm font-semibold">Antes e depois do tratamento</p>
          <Row label="Registros" a={fmtInt(s.before.rows ?? 0)} b={fmtInt(s.after.rows)} />
          <Row label="Inconsistências identificadas" a={fmtInt(s.before.total_issues ?? 0)} b={fmtInt(s.after.total_issues)} />
          <Row label="Linhas afetadas" a={fmtInt(s.before.affected_rows ?? 0)} b={fmtInt(s.after.affected_rows)} />
          <Row label="Pendências (sem exceções)" a={fmtInt(s.before.total_issues ?? 0)} b={fmtInt(s.after.pending)} />
          <Row label="DataCheck Score" a={n(s.before.score)} b={n(s.after.score)} />
          <p className="mt-3 text-xs text-muted-foreground">O score considera todas as ocorrências ainda presentes, inclusive as aceitas como exceção. Ele representa apenas a cobertura das regras executadas.</p>
        </Card>
        <Card className="p-5">
          <p className="mb-2 text-sm font-semibold">O que foi feito</p>
          {[["Valores imputados", o.imputed_values], ["Registros removidos", o.removed_rows], ["Duplicidades resolvidas", o.duplicates_resolved],
            ["Correções manuais e de formato (registros)", o.manual_corrections], ["Ocorrências aceitas como exceção", s.after.accepted], ["Operações registradas", o.operations]].map(([l, v]) => (
            <div key={String(l)} className="flex items-center justify-between border-b py-2 text-sm last:border-0"><span className="text-muted-foreground">{l}</span><b>{fmtInt(Number(v))}</b></div>))}
        </Card>
      </div>
      <Card className="flex flex-wrap items-center gap-3 p-5">
        <ShieldCheck className="size-6 text-primary" />
        <div className="min-w-0 flex-1"><p className="font-semibold">Validar base tratada</p>
          <p className="text-sm text-muted-foreground">Reexecuta todas as regras na versão atual para identificar problemas remanescentes.</p></div>
        <Button onClick={onValidate} disabled={validating}>{validating ? "Validando…" : "Validar base tratada"}</Button>
      </Card>
      <p className="flex items-center gap-2 text-sm">{s.can_generate_eda ? <Badge variant="success">Pronta para EDA</Badge> : <Badge variant="warning">{fmtInt(s.counts.pending)} pendência(s)</Badge>}<span className="text-muted-foreground">{s.readiness_message}</span></p>
    </div>
  );
}
