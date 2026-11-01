import { HistoryPane } from "@/components/treatment/HistoryPane";
import { BeforeAfterPane } from "@/components/treatment/BeforeAfterPane";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspace } from "@/contexts/WorkspaceContext";

/** Registro das correções, versões da base e comparação antes × depois. */
export default function Changes() {
  const { id, summary, refreshKey, applied, validating, validate } = useWorkspace();
  return (
    <Tabs defaultValue="history">
      <TabsList><TabsTrigger value="history">Histórico e versões</TabsTrigger><TabsTrigger value="compare">Antes × depois</TabsTrigger></TabsList>
      <TabsContent value="history"><HistoryPane analysisId={id} currentVersion={summary.current_version ?? 0} refreshKey={refreshKey} onChanged={applied} /></TabsContent>
      <TabsContent value="compare"><BeforeAfterPane s={summary} validating={validating} onValidate={validate} /></TabsContent>
    </Tabs>
  );
}
