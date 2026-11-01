import { Download, Eye, FileSpreadsheet, FileText, Rows3, SearchCheck, Table2, Trash2, TriangleAlert, Columns3, Wrench } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AffectedDonut, HorizontalBars, SeverityDonut } from "@/components/Charts";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FeedbackDialog } from "@/components/FeedbackDialog";
import { DataViewer } from "@/components/DataViewer";
import { InsightsList } from "@/components/InsightsList";
import { Modal } from "@/components/Modal";
import { IssuesTable } from "@/components/IssuesTable";
import { ScoreGauge } from "@/components/ScoreGauge";
import { StatCard } from "@/components/StatCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { errorMessage } from "@/lib/api";
import { analysisService } from "@/services";
import { fmtDateTime, fmtInt } from "@/utils/format";

export default function AnalysisResults() {
  const navigate = useNavigate();
  const { analysis: a, reload } = useWorkspace();
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [viewing, setViewing] = useState(false);

  const m = a.metrics;
  const download = async (kind: "report-csv" | "report-xlsx" | "issues-xlsx" | "issues-pdf") => {
    setBusy(kind);
    try {
      if (kind.startsWith("report")) await analysisService.download(a.id, kind === "report-csv" ? "csv" : "xlsx", a.filename);
      else await analysisService.downloadIssues(a.id, kind === "issues-pdf" ? "pdf" : "xlsx", a.filename);
    } catch (e) { toast.error(errorMessage(e)); }
    finally { setBusy(null); }
  };
  const remove = async () => {
    setBusy("delete");
    try { await analysisService.remove(a.id); toast.success("Análise excluída."); navigate("/minhas-analises"); }
    catch (e) { toast.error(errorMessage(e)); setBusy(null); setConfirm(false); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">Executada em {fmtDateTime(a.completed_at)}</p>
        <div className="flex flex-wrap gap-2">
          {a.data_available && <Button asChild variant="brand"><Link to={`/minhas-analises/${a.id}/tratamento`}><Wrench />{m.total_occurrences > 0 ? "Tratar dados" : "Abrir tratamento"}</Link></Button>}
          <Button variant="outline" onClick={() => setViewing(true)} disabled={!a.data_available}><Eye />Visualizar tabela</Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button variant="outline" disabled={!!busy}><Download />{busy ? "Gerando…" : "Baixar"}</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Relatório completo</DropdownMenuLabel>
              <DropdownMenuItem onSelect={() => void download("report-xlsx")}><FileSpreadsheet />Excel (XLSX, com gráficos)</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => void download("report-csv")}><FileText />CSV</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Tabela de inconsistências</DropdownMenuLabel>
              <DropdownMenuItem onSelect={() => void download("issues-xlsx")}><FileSpreadsheet />Excel (XLSX)</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => void download("issues-pdf")}><FileText />PDF</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <FeedbackDialog analysisId={a.id} submitted={!!a.feedback_submitted} onSubmitted={() => void reload()} />
          <Button variant="ghost" size="icon" onClick={() => setConfirm(true)} aria-label="Excluir análise" className="text-destructive hover:text-destructive"><Trash2 /></Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Registros analisados" value={fmtInt(m.total_rows)} icon={Rows3} />
        <StatCard label="Colunas analisadas" value={fmtInt(m.total_columns)} icon={Columns3} tone="brand" />
        <StatCard label="Ocorrências" value={fmtInt(m.total_occurrences)} icon={TriangleAlert} tone="warning" hint="Uma linha pode ter várias" />
        <StatCard label="Linhas afetadas" value={fmtInt(m.affected_rows)} icon={Table2} tone="destructive" hint={`${m.affected_rows_pct.toLocaleString("pt-BR")}% do total`} />
        <StatCard label="Sem inconsistências" value={`${m.clean_rows_pct.toLocaleString("pt-BR")}%`} icon={SearchCheck} tone="success" hint={`${fmtInt(m.clean_rows)} linhas`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="flex items-center justify-center p-6 lg:col-span-1">
          <ScoreGauge value={a.score.value} label={a.score.label} formula={a.score.formula} disclaimer={a.score.disclaimer} />
        </Card>
        <Card className="lg:col-span-2"><CardHeader><CardTitle>Inconsistências por categoria</CardTitle></CardHeader>
          <CardContent>{m.by_category.length ? <HorizontalBars data={m.by_category.map((c) => ({ name: c.label, value: c.count }))} />
            : <p className="py-12 text-center text-sm text-muted-foreground">Nenhuma inconsistência encontrada.</p>}</CardContent></Card>
        <Card><CardHeader><CardTitle>Ocorrências por coluna</CardTitle><CardDescription>Colunas com mais problemas</CardDescription></CardHeader>
          <CardContent>{m.by_column.length ? <HorizontalBars color="hsl(var(--brand))" data={m.by_column.slice(0, 8).map((c) => ({ name: c.column, value: c.count }))} />
            : <p className="py-12 text-center text-sm text-muted-foreground">—</p>}</CardContent></Card>
        <Card><CardHeader><CardTitle>Distribuição por severidade</CardTitle></CardHeader>
          <CardContent>{m.total_occurrences ? <SeverityDonut data={m.by_severity} /> : <p className="py-12 text-center text-sm text-muted-foreground">—</p>}</CardContent></Card>
        <Card><CardHeader><CardTitle>Registros afetados</CardTitle><CardDescription>Linhas distintas</CardDescription></CardHeader>
          <CardContent><AffectedDonut affected={m.affected_rows} clean={m.clean_rows} /></CardContent></Card>
      </div>

      <Tabs defaultValue="issues">
        <TabsList>
          <TabsTrigger value="issues">Inconsistências ({fmtInt(m.total_occurrences)})</TabsTrigger>
          <TabsTrigger value="insights">Insights da análise</TabsTrigger>
          <TabsTrigger value="rules">Verificações executadas</TabsTrigger>
        </TabsList>
        <TabsContent value="issues"><Card className="p-4 sm:p-5"><IssuesTable analysis={a} />
          {a.issues_truncated && <p className="mt-3 text-xs text-muted-foreground">A lista foi limitada ao máximo armazenado; os totais acima continuam exatos.</p>}
          {!a.store_values && <p className="mt-3 text-xs text-muted-foreground">Esta análise foi feita sem armazenar os valores originais das células.</p>}</Card></TabsContent>
        <TabsContent value="insights">
          <p className="mb-3 text-sm text-muted-foreground">Comentários gerados por <strong>regras programadas</strong>. Nenhuma IA generativa está integrada e nenhum dado sai do servidor. Nada é corrigido automaticamente.</p>
          <InsightsList items={a.insights.items} />
        </TabsContent>
        <TabsContent value="rules">
          <Card><Table>
            <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Verificação</TableHead><TableHead>Status</TableHead><TableHead>Ocorrências</TableHead><TableHead>Finalidade</TableHead></TableRow></TableHeader>
            <TableBody>{a.rules.map((r) => (
              <TableRow key={r.code}><TableCell className="whitespace-nowrap font-medium">{r.letter}. {r.name}</TableCell>
                <TableCell>{r.executed ? <Badge variant="success">Executada</Badge> : <Badge variant="muted">Não executada</Badge>}</TableCell>
                <TableCell>{r.executed ? fmtInt(r.issues) : "—"}</TableCell><TableCell className="min-w-[18rem] text-muted-foreground">{r.description}</TableCell></TableRow>
            ))}</TableBody></Table></Card>
        </TabsContent>
      </Tabs>

      {viewing && <Modal open onClose={() => setViewing(false)} className="max-w-6xl" title="Tabela original"
        description="A planilha enviada, exatamente como está (somente leitura). Células com inconsistências aparecem destacadas; passe o mouse para ver o motivo.">
        <DataViewer analysisId={a.id} />
      </Modal>}
      <ConfirmDialog open={confirm} onOpenChange={setConfirm} loading={busy === "delete"} title="Excluir esta análise?" confirmLabel="Excluir"
        description="O resultado e todas as ocorrências armazenadas serão removidos permanentemente. Sua planilha original não é afetada." onConfirm={remove} />
    </div>
  );
}
