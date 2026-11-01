import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { cleaningService } from "@/services";
import type { ColumnOptions } from "@/types";

const AUTO = "auto";

export function ColumnTypesPane({ analysisId, refreshKey, onChanged }: { analysisId: string; refreshKey: number; onChanged: () => void }) {
  const [opts, setOpts] = useState<ColumnOptions | null>(null);
  const [draft, setDraft] = useState<Record<string, { type: string; order: string }>>({});
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    cleaningService.options(analysisId).then((o) => {
      setOpts(o);
      setDraft(Object.fromEntries(o.columns.map((c) => [c.name, { type: c.source === "manual" ? c.stat_type : AUTO, order: (c.order ?? []).join("\n") }])));
    }).catch((e) => toast.error(errorMessage(e)));
  }, [analysisId, refreshKey]);

  if (!opts) return <Skeleton className="h-64" />;
  const save = async (name: string) => {
    const d = draft[name];
    setSaving(name);
    try {
      const order = d.order.split(/[\n,;]/).map((s) => s.trim()).filter(Boolean);
      await cleaningService.setColumnTypes(analysisId, { [name]: d.type === AUTO ? { type: null } : { type: d.type, ...(d.type === "ordinal" ? { order } : {}) } });
      toast.success(`Classificação de «${name}» atualizada.`);
      onChanged();
    } catch (e) { toast.error(errorMessage(e)); } finally { setSaving(null); }
  };

  return (
    <Card className="space-y-3 p-4">
      <p className="text-sm text-muted-foreground">O DataCheck não usa apenas o tipo de armazenamento: códigos e documentos (CPF, CEP, IBGE…) são tratados como <b>identificadores</b>, não como números. Revise a classificação e altere se necessário; para variáveis ordinais, informe a ordem das categorias.</p>
      <div className="overflow-x-auto rounded-lg border"><Table>
        <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Coluna</TableHead><TableHead>Classificação</TableHead><TableHead>Ausentes</TableHead><TableHead>Por quê?</TableHead><TableHead /></TableRow></TableHeader>
        <TableBody>{opts.columns.map((c) => {
          const d = draft[c.name] ?? { type: AUTO, order: "" };
          const dirty = d.type !== (c.source === "manual" ? c.stat_type : AUTO) || (d.type === "ordinal" && d.order !== (c.order ?? []).join("\n"));
          return (
            <TableRow key={c.name}>
              <TableCell className="font-medium">{c.name}</TableCell>
              <TableCell className="min-w-[14rem] space-y-2">
                <Select value={d.type} onValueChange={(v) => setDraft((x) => ({ ...x, [c.name]: { ...d, type: v } }))}>
                  <SelectTrigger aria-label={`Classificação de ${c.name}`}><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value={AUTO}>Automático ({opts.stat_types[c.stat_type]})</SelectItem>
                    {Object.entries(opts.stat_types).map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent></Select>
                {d.type === "ordinal" && <Textarea value={d.order} onChange={(e) => setDraft((x) => ({ ...x, [c.name]: { ...d, order: e.target.value } }))} placeholder={"Uma categoria por linha, da menor para a maior"} className="min-h-[72px] text-xs" />}
              </TableCell>
              <TableCell>{c.n_missing > 0 ? <Badge variant="warning">{c.n_missing}</Badge> : <span className="text-muted-foreground">0</span>}</TableCell>
              <TableCell className="max-w-xs text-xs text-muted-foreground">{c.source === "manual" && <Badge variant="info" className="mr-1">manual</Badge>}{c.reasons.join(" ")}</TableCell>
              <TableCell><Button size="sm" disabled={!dirty || saving === c.name} onClick={() => save(c.name)}>{saving === c.name ? "Salvando…" : "Salvar"}</Button></TableCell>
            </TableRow>);
        })}</TableBody></Table></div>
    </Card>
  );
}
