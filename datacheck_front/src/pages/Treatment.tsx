import { CheckCircle2, ChevronRight, Eraser, ListChecks, Rows3, ShieldQuestion, Target } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/EmptyState";
import { StatCard } from "@/components/StatCard";
import { ColumnTypesPane } from "@/components/treatment/ColumnTypesPane";
import { DuplicatesPane } from "@/components/treatment/DuplicatesPane";
import { FixDialog, type FixTarget } from "@/components/treatment/FixDialog";
import { ImputationDialog } from "@/components/treatment/ImputationDialog";
import { IssuesPane } from "@/components/treatment/IssuesPane";
import { OutliersPane } from "@/components/treatment/OutliersPane";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { fmtInt } from "@/utils/format";

export default function Treatment() {
  const { id, summary, refreshKey, applied, bump } = useWorkspace();
  const [impute, setImpute] = useState<{ column: string; rows: number[] } | null>(null);
  const [fix, setFix] = useState<FixTarget | null>(null);

  if (!summary.data_available)
    return <EmptyState icon={ShieldQuestion} title="Tratamento indisponível para esta análise"
      description={summary.message ?? "A base não está armazenada. Refaça a análise mantendo a base armazenada para poder tratá-la."}
      action={<Button asChild variant="brand"><Link to="/nova-analise">Nova análise</Link></Button>} />;

  const c = summary.counts;
  const version = summary.current_version ?? 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Inconsistências encontradas" value={fmtInt(c.total)} icon={ListChecks} hint="Desde o diagnóstico" />
        <StatCard label="Corrigidas" value={fmtInt(c.corrected)} icon={CheckCircle2} tone="success" hint={c.accepted ? `+ ${fmtInt(c.accepted)} aceitas como exceção` : undefined} />
        <StatCard label="Pendentes" value={fmtInt(c.pending)} icon={Eraser} tone={c.pending ? "warning" : "success"} hint={c.introduced ? `${fmtInt(c.introduced)} nova(s) após o tratamento` : undefined} />
        <StatCard label="Registros afetados" value={fmtInt(c.affected_rows)} icon={Rows3} tone="brand" hint="Com pendências" />
        <Card className="animate-fade-up p-5"><p className="text-sm text-muted-foreground">Progresso do tratamento</p>
          <p className="mt-1 text-2xl font-bold tracking-tight">{c.progress_pct.toLocaleString("pt-BR")}%</p><Progress value={c.progress_pct} className="mt-2" />
          <p className="mt-1.5 flex items-center gap-1 text-xs text-muted-foreground"><Target className="size-3" />{c.pending === 0 ? "Sem pendências" : `${fmtInt(c.pending)} restante(s)`}</p></Card>
      </div>

      <Card className={`p-4 text-sm ${summary.can_generate_eda ? "border-success/40 bg-success/5" : ""}`}>
        <p className="flex flex-wrap items-center gap-2">{summary.can_generate_eda ? <Badge variant="success">Pronta para EDA</Badge> : <Badge variant="warning">Com pendências</Badge>}{summary.readiness_message}</p>
        {summary.can_generate_eda && <p className="mt-2 flex flex-wrap items-center gap-1 text-muted-foreground">
          Gere a EDA no <Link to="/historico" className="font-medium text-primary hover:underline">Histórico</Link><ChevronRight className="size-3" />
          o relatório fica na página <Link to="/eda" className="font-medium text-primary hover:underline">EDA</Link>.</p>}
      </Card>

      <Tabs defaultValue="issues">
        <TabsList>
          <TabsTrigger value="issues">Inconsistências</TabsTrigger><TabsTrigger value="duplicates">Duplicatas</TabsTrigger>
          <TabsTrigger value="outliers">Valores extremos</TabsTrigger><TabsTrigger value="types">Tipos de variáveis</TabsTrigger>
        </TabsList>
        <TabsContent value="issues"><IssuesPane analysisId={id} summary={summary} refreshKey={refreshKey} onImpute={(column, rows) => setImpute({ column, rows })} onFix={setFix} /></TabsContent>
        <TabsContent value="duplicates"><DuplicatesPane analysisId={id} version={version} refreshKey={refreshKey} onApplied={applied} onFix={setFix} /></TabsContent>
        <TabsContent value="outliers"><OutliersPane analysisId={id} refreshKey={refreshKey} onFix={setFix} /></TabsContent>
        <TabsContent value="types"><ColumnTypesPane analysisId={id} refreshKey={refreshKey} onChanged={bump} /></TabsContent>
      </Tabs>

      {impute && <ImputationDialog analysisId={id} version={version} column={impute.column} rows={impute.rows} onClose={() => setImpute(null)} onApplied={applied} />}
      {fix && <FixDialog analysisId={id} version={version} target={fix} onClose={() => setFix(null)} onApplied={applied} />}
    </div>
  );
}
