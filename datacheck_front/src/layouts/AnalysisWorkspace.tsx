import { CheckCircle2, ClipboardList, Download, FileSearch, Table2, Undo2, Wrench } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState } from "@/components/ErrorState";
import { ExportDialog } from "@/components/treatment/ExportDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceContext, type Workspace } from "@/contexts/WorkspaceContext";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { analysisService, cleaningService } from "@/services";
import type { AnalysisResult, CleaningSummary } from "@/types";
import { fmtInt, WORKFLOW } from "@/utils/format";

/** Área de trabalho de uma base: diagnóstico, tratamento, dados tratados e alterações, sem voltar ao menu. */
export default function AnalysisWorkspace() {
  const { id = "" } = useParams();
  const { pathname } = useLocation();
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [summary, setSummary] = useState<CleaningSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [key, setKey] = useState(0);
  const [validating, setValidating] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    try {
      const a = await analysisService.get(id);
      const s = a.status === "completed" ? await cleaningService.summary(id) : null;
      setAnalysis(a); setSummary(s); setError(null);
    } catch (e) { setError(errorMessage(e)); }
  }, [id]);
  useEffect(() => { setAnalysis(null); setSummary(null); void load(); }, [load]);

  const applied = useCallback((s: CleaningSummary) => { setSummary(s); setKey((k) => k + 1); }, []);
  const bump = useCallback(() => setKey((k) => k + 1), []);

  const validate = async () => {
    setValidating(true);
    try { applied(await cleaningService.validate(id)); toast.success("Base validada novamente."); } catch (e) { toast.error(errorMessage(e)); } finally { setValidating(false); }
  };
  const undo = async () => {
    setUndoing(true);
    try { applied(await cleaningService.undo(id)); toast.success("Última alteração desfeita."); } catch (e) { toast.error(errorMessage(e)); } finally { setUndoing(false); }
  };

  const value = useMemo<Workspace | null>(() => (analysis && summary ? { id, analysis, summary, refreshKey: key, applied, bump, validating, validate, reload: load } : null),
    [id, analysis, summary, key, applied, bump, validating, validate, load]);

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!analysis) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-12" /><Skeleton className="h-80" /></div>;
  if (analysis.status !== "completed" || !summary || !value)
    return <ErrorState message={analysis.status === "failed" ? analysis.error_message ?? "Esta análise falhou." : "Esta análise ainda não foi concluída."} />;

  const hasData = summary.data_available;
  const wf = WORKFLOW[summary.workflow_status] ?? WORKFLOW.analyzed;
  const version = summary.current_version ?? 0;
  const onDiagnosis = pathname.endsWith("/diagnostico");
  const steps = [
    { to: "diagnostico", label: "Diagnóstico", icon: FileSearch, hint: `${fmtInt(analysis.metrics.total_occurrences)} ocorrência(s)`, needsData: false },
    { to: "tratamento", label: "Tratamento", icon: Wrench, hint: hasData ? `${fmtInt(summary.counts.pending)} pendente(s)` : "indisponível", needsData: true },
    { to: "dados-tratados", label: "Dados tratados", icon: Table2, hint: summary.version_label ?? "—", needsData: true },
    { to: "alteracoes", label: "Alterações", icon: ClipboardList, hint: `${fmtInt(summary.operations.operations)} operação(ões)`, needsData: true },
  ];

  return (
    <WorkspaceContext.Provider value={value}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate text-xl font-bold tracking-tight">{analysis.filename}</h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="muted">{analysis.file_type.toUpperCase()}</Badge>{analysis.sheet && <Badge variant="muted">Aba {analysis.sheet}</Badge>}
              <Badge variant={wf.variant}>{wf.label}</Badge>{hasData && <Badge variant="muted">{summary.version_label}</Badge>}
            </div>
          </div>
          {hasData && !onDiagnosis && (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={version === 0 || undoing} onClick={undo}><Undo2 />{undoing ? "Desfazendo…" : "Desfazer"}</Button>
              <Button variant="outline" onClick={() => setExporting(true)}><Download />Baixar base tratada</Button>
              <Button onClick={validate} disabled={validating}><CheckCircle2 />{validating ? "Validando…" : "Validar base tratada"}</Button>
            </div>)}
        </div>

        <nav aria-label="Etapas da análise" className="flex gap-1 overflow-x-auto rounded-xl border bg-card p-1">
          {steps.map(({ to, label, icon: Icon, hint, needsData }, i) => {
            const disabled = needsData && !hasData;
            const body = (<><span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">{i + 1}</span>
              <span className="text-left"><span className="flex items-center gap-1.5 text-sm font-medium"><Icon className="size-4" />{label}</span>
                <span className="block text-xs font-normal text-muted-foreground">{hint}</span></span></>);
            return disabled
              ? <span key={to} aria-disabled className="flex min-w-[10rem] flex-1 cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 opacity-50">{body}</span>
              : <NavLink key={to} to={to} className={({ isActive }) => cn("flex min-w-[10rem] flex-1 items-center gap-3 rounded-lg px-3 py-2 transition-colors",
                  isActive ? "bg-gradient-to-r from-primary/15 to-brand/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>{body}</NavLink>;
          })}
        </nav>

        <Outlet />
        {exporting && <ExportDialog analysisId={id} filename={analysis.filename} versionLabel={summary.version_label ?? ""} onClose={() => setExporting(false)} />}
      </div>
    </WorkspaceContext.Provider>
  );
}
