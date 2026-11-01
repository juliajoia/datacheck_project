import {
  flexRender, getCoreRowModel, useReactTable, type ColumnDef, type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search, SearchX } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { analysisService } from "@/services";
import type { AnalysisResult, IssueRow, Paginated } from "@/types";
import { fmtInt } from "@/utils/format";
import { ErrorState } from "@/components/ErrorState";

const ALL = "__all__";
const ROW_TONE = {
  critical: "border-l-4 border-l-destructive bg-destructive/[0.04]",
  warning: "border-l-4 border-l-warning bg-warning/[0.05]",
  info: "border-l-4 border-l-primary bg-primary/[0.04]",
};
const PAGE_SIZES = [25, 50, 100, 250];

function useDebounced<T>(value: T, ms = 350) {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

export function IssuesTable({ analysis }: { analysis: AnalysisResult }) {
  const { metrics } = analysis;
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const [column, setColumn] = useState(ALL);
  const [category, setCategory] = useState(ALL);
  const [severity, setSeverity] = useState(ALL);
  const [sorting, setSorting] = useState<SortingState>([{ id: "row", desc: false }]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<Paginated<IssueRow> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const req = useRef(0);

  useEffect(() => { setPage(1); }, [q, column, category, severity, sorting, pageSize]);

  const load = () => {
    const id = ++req.current;
    setLoading(true);
    analysisService
      .issues(analysis.id, {
        q: q || undefined,
        column: column === ALL ? undefined : column,
        category: category === ALL ? undefined : category,
        severity: severity === ALL ? undefined : severity,
        sort_by: sorting[0]?.id ?? "row", descending: sorting[0]?.desc ?? false, page, page_size: pageSize,
      })
      .then((d) => { if (id === req.current) { setData(d); setError(null); } })
      .catch((e) => id === req.current && setError(errorMessage(e)))
      .finally(() => id === req.current && setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [analysis.id, q, column, category, severity, sorting, page, pageSize]);

  const columns = useMemo<ColumnDef<IssueRow>[]>(() => [
    { id: "row", accessorKey: "row", header: "Linha", cell: (c) => <span className="font-mono text-xs">{c.getValue<number>()}</span> },
    { id: "column", accessorKey: "column", header: "Coluna", cell: (c) => <span className="font-medium">{c.getValue<string>()}</span> },
    { id: "value", accessorKey: "value", header: "Valor original",
      cell: (c) => <code className="block max-w-[14rem] truncate rounded bg-muted px-1.5 py-0.5 text-xs" title={c.getValue<string>()}>{c.getValue<string>()}</code> },
    { id: "category", accessorKey: "category_label", header: "Tipo" },
    { id: "severity", accessorKey: "severity", header: "Severidade", cell: (c) => <SeverityBadge severity={c.getValue<IssueRow["severity"]>()} /> },
    { id: "description", accessorKey: "description", header: "Descrição", enableSorting: false,
      cell: (c) => <span className="block min-w-[16rem] max-w-md">{c.getValue<string>()}</span> },
    { id: "suggestion", accessorKey: "suggestion", header: "Sugestão de revisão", enableSorting: false,
      cell: (c) => <span className="block min-w-[16rem] max-w-md text-muted-foreground">{c.getValue<string>()}</span> },
  ], []);

  const table = useReactTable({
    data: data?.items ?? [], columns, state: { sorting }, onSortingChange: setSorting,
    manualSorting: true, enableSortingRemoval: false, getCoreRowModel: getCoreRowModel(),
  });

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const filtered = !!q || column !== ALL || category !== ALL || severity !== ALL;

  if (analysis.total_issues === 0)
    return <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Nenhuma inconsistência foi encontrada pelas regras executadas.</p>;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative sm:col-span-2 lg:col-span-1">
          <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar valor, coluna, descrição…" className="pl-9" aria-label="Buscar ocorrências" />
        </div>
        <FilterSelect label="Coluna" value={column} onChange={setColumn} options={metrics.by_column.map((c) => ({ value: c.column, label: `${c.column} (${c.count})` }))} />
        <FilterSelect label="Tipo" value={category} onChange={setCategory} options={metrics.by_category.map((c) => ({ value: c.category, label: `${c.label} (${c.count})` }))} />
        <FilterSelect label="Severidade" value={severity} onChange={setSeverity} options={metrics.by_severity.filter((s) => s.count).map((s) => ({ value: s.severity, label: `${s.label} (${s.count})` }))} />
      </div>

      {error ? <ErrorState message={error} onRetry={load} /> : (
        <div className="overflow-hidden rounded-xl border bg-card">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((hg) => (
                <TableRow key={hg.id} className="hover:bg-transparent">
                  {hg.headers.map((h) => {
                    const sorted = h.column.getIsSorted();
                    const canSort = h.column.getCanSort();
                    return (
                      <TableHead key={h.id} aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"}>
                        {canSort ? (
                          <button className="inline-flex items-center gap-1 uppercase hover:text-foreground" onClick={h.column.getToggleSortingHandler()}>
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            {sorted === "asc" ? <ArrowUp className="size-3" /> : sorted === "desc" ? <ArrowDown className="size-3" /> : <ArrowUpDown className="size-3 opacity-40" />}
                          </button>
                        ) : flexRender(h.column.columnDef.header, h.getContext())}
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {loading && !data
                ? Array.from({ length: 6 }, (_, i) => <TableRow key={i}><TableCell colSpan={7}><Skeleton className="h-6 w-full" /></TableCell></TableRow>)
                : table.getRowModel().rows.map((row) => (
                  <TableRow key={row.id} className={cn(ROW_TONE[row.original.severity], loading && "opacity-60")}>
                    {row.getVisibleCells().map((cell) => <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>)}
                  </TableRow>
                ))}
            </TableBody>
          </Table>
          {!loading && data && data.items.length === 0 && (
            <div className="flex flex-col items-center gap-2 p-10 text-sm text-muted-foreground">
              <SearchX className="size-8" /> Nenhuma ocorrência corresponde aos filtros.
              {filtered && <Button variant="outline" size="sm" onClick={() => { setSearch(""); setColumn(ALL); setCategory(ALL); setSeverity(ALL); }}>Limpar filtros</Button>}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className="text-muted-foreground" aria-live="polite">{fmtInt(total)} ocorrência(s){filtered ? " com os filtros atuais" : ""}</p>
        <div className="flex items-center gap-2">
          <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}>
            <SelectTrigger className="h-8 w-[110px]" aria-label="Linhas por página"><SelectValue /></SelectTrigger>
            <SelectContent>{PAGE_SIZES.map((n) => <SelectItem key={n} value={String(n)}>{n} / página</SelectItem>)}</SelectContent>
          </Select>
          <Button variant="outline" size="icon" className="size-8" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Página anterior"><ChevronLeft /></Button>
          <span className="min-w-[5.5rem] text-center">Página {page} de {pages}</span>
          <Button variant="outline" size="icon" className="size-8" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Próxima página"><ChevronRight /></Button>
        </div>
      </div>
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={`Filtrar por ${label.toLowerCase()}`}><SelectValue placeholder={label} /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{label}: todas</SelectItem>
        {options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}
