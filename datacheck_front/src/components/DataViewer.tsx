import { ChevronLeft, ChevronRight, Search, SearchX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { analysisService } from "@/services";
import type { DataPage } from "@/types";
import { fmtInt } from "@/utils/format";

const CELL = { critical: "bg-destructive/15 ring-1 ring-inset ring-destructive/40", warning: "bg-warning/20 ring-1 ring-inset ring-warning/50", info: "bg-primary/10 ring-1 ring-inset ring-primary/30" };

/** Planilha somente leitura. Sem `version`, mostra a original com as células que têm ocorrências destacadas. */
export function DataViewer({ analysisId, version }: { analysisId: string; version?: number }) {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<DataPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const req = useRef(0);

  useEffect(() => { const t = setTimeout(() => setQ(search), 350); return () => clearTimeout(t); }, [search]);
  useEffect(() => { setPage(1); }, [q, pageSize]);
  useEffect(() => {
    const id = ++req.current;
    setLoading(true);
    analysisService.data(analysisId, { q: q || undefined, page, page_size: pageSize, version })
      .then((d) => id === req.current && (setData(d), setError(null)))
      .catch((e) => id === req.current && setError(errorMessage(e)))
      .finally(() => id === req.current && setLoading(false));
  }, [analysisId, q, page, pageSize, version]);

  if (error) return <ErrorState message={error} />;
  const pages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[14rem] flex-1"><Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar em qualquer coluna…" className="pl-9" aria-label="Buscar na planilha" /></div>
        {!version && <p className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><i className="inline-block size-3 rounded bg-destructive/30" />crítica</span>
          <span className="flex items-center gap-1"><i className="inline-block size-3 rounded bg-warning/40" />aviso</span>
          <span className="flex items-center gap-1"><i className="inline-block size-3 rounded bg-primary/25" />informativa</span></p>}
      </div>
      <div className="max-h-[60vh] overflow-auto rounded-xl border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-card"><TableRow className="hover:bg-transparent"><TableHead>Linha</TableHead>{data?.columns.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {loading && !data ? Array.from({ length: 6 }, (_, i) => <TableRow key={i}><TableCell colSpan={8}><Skeleton className="h-6" /></TableCell></TableRow>)
              : data?.rows.map((r) => (
                <TableRow key={r.row} className={cn(loading && "opacity-60")}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{r.row}</TableCell>
                  {r.values.map((v, i) => {
                    const flag = r.flags[data.columns[i]];
                    return <TableCell key={i} className={cn("max-w-[16rem] truncate", flag && CELL[flag.severity])} title={flag ? `${flag.description}` : v}>{v === "" ? <span className="text-muted-foreground">—</span> : v}</TableCell>;
                  })}
                </TableRow>))}
          </TableBody>
        </Table>
        {!loading && data?.rows.length === 0 && <div className="flex flex-col items-center gap-2 p-10 text-sm text-muted-foreground"><SearchX className="size-8" />Nenhuma linha encontrada.</div>}
      </div>
      {data && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <p className="text-muted-foreground" aria-live="polite">{fmtInt(data.total)} de {fmtInt(data.total_rows)} linha(s) · versão: {data.label}</p>
          <div className="flex items-center gap-2">
            <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}><SelectTrigger className="h-8 w-[110px]" aria-label="Linhas por página"><SelectValue /></SelectTrigger>
              <SelectContent>{[25, 50, 100, 200].map((n) => <SelectItem key={n} value={String(n)}>{n} / página</SelectItem>)}</SelectContent></Select>
            <Button variant="outline" size="icon" className="size-8" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Página anterior"><ChevronLeft /></Button>
            <span className="min-w-[5.5rem] text-center">Página {page} de {pages}</span>
            <Button variant="outline" size="icon" className="size-8" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Próxima página"><ChevronRight /></Button>
          </div>
        </div>)}
    </div>
  );
}
