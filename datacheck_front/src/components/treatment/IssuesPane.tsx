import { ChevronLeft, ChevronRight, ListChecks, Wrench } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { FixTarget } from "@/components/treatment/FixDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { cleaningService } from "@/services";
import type { CleaningSummary, PendingIssue } from "@/types";
import { fmtInt } from "@/utils/format";

const ALL = "__all__";
const keyOf = (i: { row: number; column: string; category: string }) => `${i.row}|${i.column}|${i.category}`;
const TONE = { critical: "border-l-4 border-l-destructive", warning: "border-l-4 border-l-warning", info: "border-l-4 border-l-primary" };
const MAX_SELECT_ALL = 5000;

interface Props {
  analysisId: string; summary: CleaningSummary; refreshKey: number;
  onImpute: (column: string, rows: number[]) => void;
  onFix: (t: FixTarget) => void;
}

export function IssuesPane({ analysisId, summary, refreshKey, onImpute, onFix }: Props) {
  const [category, setCategory] = useState(ALL);
  const [column, setColumn] = useState(ALL);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: PendingIssue[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Map<string, PendingIssue>>(new Map());
  const [selecting, setSelecting] = useState(false);
  const req = useRef(0);
  const PAGE = 50;

  useEffect(() => { const t = setTimeout(() => setQ(search), 350); return () => clearTimeout(t); }, [search]);
  useEffect(() => { setPage(1); }, [category, column, q, accepted]);
  useEffect(() => { setSelected(new Map()); }, [category, column, q, accepted, refreshKey]);

  const params = useCallback((p: number, size: number) => ({
    category: category === ALL ? undefined : category, column: column === ALL ? undefined : column, q: q || undefined,
    include_accepted: accepted, page: p, page_size: size }), [category, column, q, accepted]);

  useEffect(() => {
    const id = ++req.current;
    setLoading(true);
    cleaningService.issues(analysisId, params(page, PAGE))
      .then((d) => id === req.current && (setData(d), setError(null)))
      .catch((e) => id === req.current && setError(errorMessage(e)))
      .finally(() => id === req.current && setLoading(false));
  }, [analysisId, params, page, refreshKey]);

  const columnsInData = useMemo(() => [...new Set((data?.items ?? []).map((i) => i.column))], [data]);
  const sel = [...selected.values()];
  const selCats = new Set(sel.map((i) => i.category));
  const selCols = new Set(sel.map((i) => i.column));
  const onlyMissing = sel.length > 0 && selCats.size === 1 && selCats.has("valores_ausentes");
  const pageKeys = (data?.items ?? []).map(keyOf);
  const allPageSelected = pageKeys.length > 0 && pageKeys.every((k) => selected.has(k));

  const toggle = (i: PendingIssue) => setSelected((m) => { const n = new Map(m); n.has(keyOf(i)) ? n.delete(keyOf(i)) : n.set(keyOf(i), i); return n; });
  const togglePage = () => setSelected((m) => { const n = new Map(m); (data?.items ?? []).forEach((i) => allPageSelected ? n.delete(keyOf(i)) : n.set(keyOf(i), i)); return n; });
  const selectAllFiltered = async () => {
    setSelecting(true);
    try {
      const n = new Map<string, PendingIssue>();
      for (let p = 1; n.size < Math.min(data?.total ?? 0, MAX_SELECT_ALL); p++) {
        const d = await cleaningService.issues(analysisId, params(p, 500));
        d.items.forEach((i) => n.set(keyOf(i), i));
        if (d.items.length < 500) break;
      }
      setSelected(n);
    } catch (e) { setError(errorMessage(e)); } finally { setSelecting(false); }
  };

  const cells = sel.map((i) => ({ row: i.row, column: i.column, category: i.category, value: i.value === "(vazio)" ? "" : i.value }));
  const act = (action: FixTarget["action"], defaults?: Record<string, unknown>) => onFix({ action, cells, defaults });

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {summary.by_category.map((c) => {
          const done = c.initial ? Math.round(100 * (c.initial - c.pending) / c.initial) : 100;
          const active = category === c.category;
          return (
            <button key={c.category} onClick={() => setCategory(active ? ALL : c.category)} aria-pressed={active}
              className={cn("rounded-xl border bg-card p-4 text-left shadow-soft transition-all hover:-translate-y-0.5", active && "border-primary ring-1 ring-primary")}>
              <p className="flex items-center justify-between text-sm font-semibold">{c.label}{c.pending === 0 && <Badge variant="success">resolvida</Badge>}</p>
              <p className="mt-1 text-2xl font-bold">{fmtInt(c.pending)}<span className="ml-1 text-xs font-normal text-muted-foreground">pendentes</span></p>
              <Progress value={done} className="mt-2" />
              <p className="mt-1.5 text-xs text-muted-foreground">{fmtInt(c.initial)} no início · {fmtInt(c.corrected)} corrigidas · {fmtInt(c.accepted)} aceitas</p>
            </button>);
        })}
      </div>

      <Card className="space-y-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar…" aria-label="Buscar ocorrências" />
          <Select value={category} onValueChange={setCategory}><SelectTrigger aria-label="Tipo"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value={ALL}>Todos os tipos</SelectItem>{summary.by_category.map((c) => <SelectItem key={c.category} value={c.category}>{c.label}</SelectItem>)}</SelectContent></Select>
          <Select value={column} onValueChange={setColumn}><SelectTrigger aria-label="Coluna"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value={ALL}>Todas as colunas</SelectItem>{[...new Set([...(column !== ALL ? [column] : []), ...columnsInData])].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select>
          <label className="flex items-center gap-2 text-sm"><Switch checked={accepted} onCheckedChange={setAccepted} />Incluir aceitas como exceção</label>
        </div>

        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/60 p-2.5 text-sm">
          <ListChecks className="size-4 text-muted-foreground" />
          <span>{sel.length ? `${fmtInt(sel.length)} selecionada(s)` : "Selecione ocorrências para tratá-las"}</span>
          {data && data.total > PAGE && sel.length < data.total && (
            <Button size="sm" variant="ghost" disabled={selecting} onClick={selectAllFiltered}>{selecting ? "Selecionando…" : `Selecionar as ${fmtInt(Math.min(data.total, MAX_SELECT_ALL))} do filtro`}</Button>)}
          {sel.length > 0 && <Button size="sm" variant="ghost" onClick={() => setSelected(new Map())}>Limpar</Button>}
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="sm" className="ml-auto" disabled={!sel.length}><Wrench />Tratar selecionadas</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Tratamento</DropdownMenuLabel><DropdownMenuSeparator />
              {onlyMissing && selCols.size === 1 && <DropdownMenuItem onSelect={() => onImpute([...selCols][0], sel.map((i) => i.row))}>Imputar valores ausentes…</DropdownMenuItem>}
              {onlyMissing && selCols.size > 1 && <DropdownMenuItem disabled>Imputação: selecione uma única coluna</DropdownMenuItem>}
              <DropdownMenuItem onSelect={() => act("set_value")}>Corrigir manualmente…</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => act("mark_missing")}>Marcar como ausente</DropdownMenuItem>
              {(selCats.has("tipo_incompativel") || selCats.has("fora_limites")) && <DropdownMenuItem onSelect={() => act("convert_number")}>Converter formato numérico…</DropdownMenuItem>}
              {(selCats.has("data_invalida") || selCats.has("tipo_incompativel")) && <DropdownMenuItem onSelect={() => act("convert_date")}>Converter formato de data…</DropdownMenuItem>}
              {[...selCats].some((c) => c.startsWith("geo_")) && <DropdownMenuItem onSelect={() => act("swap_latlon")}>Inverter latitude/longitude…</DropdownMenuItem>}
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => act("accept_exception")}>Manter com justificativa…</DropdownMenuItem>
              <DropdownMenuItem className="text-destructive" onSelect={() => act("remove_rows")}>Remover registros…</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : (
          <div className="overflow-hidden rounded-xl border">
            <Table>
              <TableHeader><TableRow className="hover:bg-transparent">
                <TableHead className="w-10"><Checkbox checked={allPageSelected} onCheckedChange={togglePage} aria-label="Selecionar a página" /></TableHead>
                <TableHead>Linha</TableHead><TableHead>Coluna</TableHead><TableHead>Valor original</TableHead><TableHead>Tipo</TableHead><TableHead>Severidade</TableHead><TableHead>Descrição</TableHead></TableRow></TableHeader>
              <TableBody>
                {loading && !data ? Array.from({ length: 5 }, (_, i) => <TableRow key={i}><TableCell colSpan={7}><Skeleton className="h-6" /></TableCell></TableRow>)
                  : data?.items.map((i) => (
                    <TableRow key={keyOf(i)} data-state={selected.has(keyOf(i)) ? "selected" : undefined} className={cn(TONE[i.severity], selected.has(keyOf(i)) && "bg-primary/5", i.accepted && "opacity-60", loading && "opacity-60")}>
                      <TableCell><Checkbox checked={selected.has(keyOf(i))} onCheckedChange={() => toggle(i)} aria-label={`Selecionar linha ${i.row}`} /></TableCell>
                      <TableCell className="font-mono text-xs">{i.row}</TableCell><TableCell className="font-medium">{i.column}</TableCell>
                      <TableCell><code className="block max-w-[12rem] truncate rounded bg-muted px-1.5 py-0.5 text-xs" title={i.value}>{i.value}</code></TableCell>
                      <TableCell>{i.category_label}{i.accepted && <Badge variant="muted" className="ml-1">aceita</Badge>}</TableCell>
                      <TableCell><SeverityBadge severity={i.severity} /></TableCell>
                      <TableCell className="min-w-[14rem] max-w-sm">
                        {i.description}
                        {i.category === "valores_ausentes" && !i.accepted && <button className="ml-2 text-xs font-medium text-primary hover:underline" onClick={() => onImpute(i.column, [i.row])}>Tratar</button>}
                      </TableCell>
                    </TableRow>))}
              </TableBody>
            </Table>
            {!loading && data?.items.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">Nenhuma inconsistência pendente com os filtros atuais.</p>}
          </div>
        )}
        {data && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{fmtInt(data.total)} ocorrência(s)</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon" className="size-8" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Página anterior"><ChevronLeft /></Button>
              <span>Página {page} de {Math.max(1, Math.ceil(data.total / PAGE))}</span>
              <Button variant="outline" size="icon" className="size-8" disabled={page >= Math.ceil(data.total / PAGE)} onClick={() => setPage(page + 1)} aria-label="Próxima página"><ChevronRight /></Button>
            </div>
          </div>)}
      </Card>
    </div>
  );
}
