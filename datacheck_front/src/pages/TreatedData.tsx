import { ShieldQuestion } from "lucide-react";
import { Link } from "react-router-dom";
import { DataViewer } from "@/components/DataViewer";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/contexts/WorkspaceContext";

/** Base na versão corrente (somente leitura). Recarrega a cada alteração aplicada. */
export default function TreatedData() {
  const { id, summary, refreshKey } = useWorkspace();
  const version = summary.current_version ?? 0;
  if (!summary.data_available)
    return <EmptyState icon={ShieldQuestion} title="Dados indisponíveis para esta análise" description={summary.message ?? "A base não está armazenada."}
      action={<Button asChild variant="brand"><Link to="/nova-analise">Nova análise</Link></Button>} />;
  return (
    <Card>
      <CardHeader><CardTitle>Dados tratados</CardTitle>
        <CardDescription>{version === 0 ? "Nenhuma correção aplicada ainda: esta é a base original. " : ""}Versão atual da base (somente leitura). Para corrigir valores, use a etapa Tratamento.</CardDescription></CardHeader>
      <CardContent><DataViewer key={`${version}-${refreshKey}`} analysisId={id} version={version} /></CardContent>
    </Card>
  );
}
