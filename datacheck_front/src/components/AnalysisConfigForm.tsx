import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, CalendarClock, Copy, MapPin, PlayCircle, Ruler, Shapes, SearchX, ShieldCheck, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { Controller, useForm, useWatch, type Control } from "react-hook-form";
import { z } from "zod";
import { ColumnPicker } from "@/components/ColumnPicker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { AnalysisConfig, ExpectedType, UploadProfile } from "@/types";
import { DATE_FORMATS } from "@/utils/format";

const NONE = "__none__";
const cols = z.array(z.string());
const num = (s: string) => (s.trim() === "" ? null : Number(s.replace(",", ".")));

const schema = z.object({
  decimalSeparator: z.enum(["auto", "comma", "dot"]),
  storeValues: z.boolean(),
  keepData: z.boolean(),
  missing: z.object({ enabled: z.boolean(), markers: z.string(), columns: cols, required: cols }),
  duplicates: z.object({ enabled: z.boolean(), keyColumns: cols }),
  types: z.object({ enabled: z.boolean(), dateFormat: z.string(), expected: z.record(z.enum(["none", "integer", "decimal", "text", "date"])) }),
  ranges: z.object({ enabled: z.boolean(), columns: cols, limits: z.record(z.object({ min: z.string(), max: z.string() })), suspect: cols }),
  geo: z.object({ enabled: z.boolean(), lat: z.string(), lon: z.string() }),
  dates: z.object({ enabled: z.boolean(), columns: cols, dateFormat: z.string(), flagFuture: z.boolean(), minDate: z.string(), maxDate: z.string() }),
}).superRefine((v, ctx) => {
  const err = (path: (string | number)[], message: string) => ctx.addIssue({ code: "custom", path, message });
  for (const c of v.ranges.columns) {
    const l = v.ranges.limits[c] ?? { min: "", max: "" };
    const lo = num(l.min), hi = num(l.max);
    if (lo !== null && Number.isNaN(lo)) err(["ranges", "limits", c, "min"], "Use apenas números");
    if (hi !== null && Number.isNaN(hi)) err(["ranges", "limits", c, "max"], "Use apenas números");
    if (lo !== null && hi !== null && !Number.isNaN(lo) && !Number.isNaN(hi) && lo > hi) err(["ranges", "limits", c, "max"], "O máximo deve ser maior que o mínimo");
  }
  if (v.geo.lat && v.geo.lat === v.geo.lon) err(["geo", "lon"], "Latitude e longitude devem ser colunas diferentes");
  if (v.dates.minDate && v.dates.maxDate && v.dates.minDate > v.dates.maxDate) err(["dates", "maxDate"], "A data máxima deve ser posterior à mínima");
  const hasLimit = v.ranges.columns.some((c) => v.ranges.limits[c] && (num(v.ranges.limits[c].min) !== null || num(v.ranges.limits[c].max) !== null));
  const effective = v.missing.enabled || v.duplicates.enabled
    || (v.types.enabled && Object.values(v.types.expected).some((t) => t !== "none"))
    || (v.ranges.enabled && (hasLimit || v.ranges.suspect.length > 0))
    || (v.geo.enabled && !!(v.geo.lat || v.geo.lon))
    || (v.dates.enabled && v.dates.columns.length > 0);
  if (!effective) err(["_form"], "Ative ao menos uma verificação e escolha as colunas necessárias.");
});
export type ConfigFormValues = z.infer<typeof schema>;

export function defaultValues(p: UploadProfile, storeValues: boolean, markers: string[], keepData = true): ConfigFormValues {
  const s = p.suggested_config;
  const expected = Object.fromEntries(p.columns.map((c) => [c.name, (s.types[c.name] ?? "none") as ExpectedType | "none"]));
  return {
    decimalSeparator: "auto", storeValues, keepData,
    missing: { enabled: true, markers: markers.join(", "), columns: [], required: [] },
    duplicates: { enabled: true, keyColumns: [] },
    types: { enabled: true, dateFormat: "auto", expected },
    ranges: { enabled: true, columns: [], limits: {}, suspect: [] },
    geo: { enabled: !!(s.lat_column || s.lon_column), lat: s.lat_column ?? "", lon: s.lon_column ?? "" },
    dates: { enabled: s.dates.length > 0, columns: s.dates, dateFormat: "auto", flagFuture: false, minDate: "", maxDate: "" },
  };
}

export function buildPayload(v: ConfigFormValues, sheet: string | null) {
  const fmt = (s: string) => (s === "auto" ? null : s);
  const limits: AnalysisConfig["ranges"]["limits"] = {};
  for (const c of v.ranges.columns) {
    const l = v.ranges.limits[c];
    const lo = l ? num(l.min) : null, hi = l ? num(l.max) : null;
    if (lo !== null || hi !== null) limits[c] = { min: lo, max: hi };
  }
  const config: AnalysisConfig = {
    decimal_separator: v.decimalSeparator,
    missing: {
      enabled: v.missing.enabled, columns: v.missing.columns.length ? v.missing.columns : null,
      markers: v.missing.markers.split(",").map((m) => m.trim()).filter(Boolean), required_columns: v.missing.required,
    },
    duplicates: { enabled: v.duplicates.enabled, key_columns: v.duplicates.keyColumns.length ? v.duplicates.keyColumns : null },
    types: {
      enabled: v.types.enabled, date_format: fmt(v.types.dateFormat),
      expected: Object.fromEntries(Object.entries(v.types.expected).filter(([, t]) => t !== "none")) as Record<string, ExpectedType>,
    },
    ranges: { enabled: v.ranges.enabled, limits, suspect_columns: v.ranges.suspect },
    geo: { enabled: v.geo.enabled, lat_column: v.geo.lat || null, lon_column: v.geo.lon || null },
    dates: {
      enabled: v.dates.enabled, columns: v.dates.columns, date_format: fmt(v.dates.dateFormat), flag_future: v.dates.flagFuture,
      min_date: v.dates.minDate || null, max_date: v.dates.maxDate || null,
    },
  };
  return { sheet, config, store_values: v.storeValues, keep_data: v.keepData };
}

function RuleCard({ icon, title, description, name, control, children }: {
  icon: ReactNode; title: string; description: string; name: "missing" | "duplicates" | "types" | "ranges" | "geo" | "dates";
  control: Control<ConfigFormValues>; children: ReactNode;
}) {
  const enabled = useWatch({ control, name: `${name}.enabled` });
  return (
    <Card className={enabled ? "" : "opacity-70"}>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div className="flex gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground [&_svg]:size-5">{icon}</span>
          <div><CardTitle>{title}</CardTitle><CardDescription className="mt-1">{description}</CardDescription></div>
        </div>
        <Controller control={control} name={`${name}.enabled`} render={({ field }) => (
          <Switch checked={field.value} onCheckedChange={field.onChange} aria-label={`Ativar ${title}`} />
        )} />
      </CardHeader>
      {enabled && <CardContent className="space-y-4">{children}</CardContent>}
    </Card>
  );
}

const Field = ({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) => (
  <div className="space-y-1.5"><Label>{label}</Label>{children}{hint && <p className="text-xs text-muted-foreground">{hint}</p>}</div>
);

function FormatSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label="Formato de data"><SelectValue /></SelectTrigger>
      <SelectContent>{DATE_FORMATS.map((f) => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}</SelectContent>
    </Select>
  );
}

function ColumnSelect({ value, onChange, columns, label }: { value: string; onChange: (v: string) => void; columns: string[]; label: string }) {
  return (
    <Select value={value || NONE} onValueChange={(v) => onChange(v === NONE ? "" : v)}>
      <SelectTrigger aria-label={label}><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>(nenhuma)</SelectItem>
        {columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

interface Props { profile: UploadProfile; initial: ConfigFormValues; running: boolean; onSubmit: (v: ConfigFormValues) => void }

export function AnalysisConfigForm({ profile, initial, running, onSubmit }: Props) {
  const { control, handleSubmit, formState: { errors } } = useForm<ConfigFormValues>({ resolver: zodResolver(schema), defaultValues: initial });
  const names = profile.columns.map((c) => c.name);
  const rangeCols = useWatch({ control, name: "ranges.columns" });
  const formError = (errors as unknown as Record<string, { message?: string }>)._form?.message;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <RuleCard name="missing" control={control} icon={<SearchX />} title="Valores ausentes"
        description="Células vazias, só com espaços ou com marcadores como N/A e NULL.">
        <Field label="Marcadores de ausência (separados por vírgula)">
          <Controller control={control} name="missing.markers" render={({ field }) => <Input {...field} />} />
        </Field>
        <Field label="Colunas obrigatórias" hint="Ausência nessas colunas é classificada como crítica.">
          <Controller control={control} name="missing.required" render={({ field }) => <ColumnPicker columns={names} value={field.value} onChange={field.onChange} emptyHint="Nenhuma obrigatória." />} />
        </Field>
        <Field label="Colunas a verificar" hint="Se nenhuma for escolhida, todas são verificadas.">
          <Controller control={control} name="missing.columns" render={({ field }) => <ColumnPicker columns={names} value={field.value} onChange={field.onChange} emptyHint="Todas as colunas." />} />
        </Field>
      </RuleCard>

      <RuleCard name="duplicates" control={control} icon={<Copy />} title="Registros duplicados"
        description="Aponta todos os registros de cada grupo repetido. Nada é excluído automaticamente.">
        <Field label="Colunas-chave" hint="Sem escolha, compara a linha inteira. Escolha, por exemplo, o ID para detectar identificadores repetidos.">
          <Controller control={control} name="duplicates.keyColumns" render={({ field }) => <ColumnPicker columns={names} value={field.value} onChange={field.onChange} emptyHint="Linha completa." />} />
        </Field>
      </RuleCard>

      <RuleCard name="types" control={control} icon={<Shapes />} title="Tipos de dados incorretos"
        description="Diga o que cada coluna deve conter. Valores como «não informado» em coluna numérica serão apontados.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Separador decimal dos números" hint="Textos numéricos que seguem a configuração são aceitos.">
            <Controller control={control} name="decimalSeparator" render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger aria-label="Separador decimal"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Automático (ponto ou vírgula)</SelectItem>
                  <SelectItem value="comma">Vírgula (1.234,56)</SelectItem>
                  <SelectItem value="dot">Ponto (1,234.56)</SelectItem>
                </SelectContent>
              </Select>
            )} />
          </Field>
          <Field label="Formato de data (colunas do tipo Data)">
            <Controller control={control} name="types.dateFormat" render={({ field }) => <FormatSelect value={field.value} onChange={field.onChange} />} />
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {names.map((n) => (
            <Controller key={n} control={control} name={`types.expected.${n}` as `types.expected.${string}`} render={({ field }) => (
              <div className="space-y-1"><Label className="text-xs text-muted-foreground">{n}</Label>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger aria-label={`Tipo esperado de ${n}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Não verificar</SelectItem><SelectItem value="integer">Inteiro</SelectItem>
                    <SelectItem value="decimal">Decimal</SelectItem><SelectItem value="text">Texto</SelectItem><SelectItem value="date">Data</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )} />
          ))}
        </div>
      </RuleCard>

      <RuleCard name="ranges" control={control} icon={<Ruler />} title="Valores fora dos limites"
        description="Defina mínimo e máximo. Violações são confirmadas pela sua regra; valores suspeitos são apenas alertas.">
        <Field label="Colunas numéricas com limites">
          <Controller control={control} name="ranges.columns" render={({ field }) => <ColumnPicker columns={names} value={field.value} onChange={field.onChange} emptyHint="Escolha as colunas para definir mínimo e máximo." />} />
        </Field>
        {rangeCols.map((c) => (
          <div key={c} className="grid items-start gap-3 rounded-lg bg-muted/50 p-3 sm:grid-cols-[1fr_1fr_1fr]">
            <p className="pt-2 text-sm font-medium">{c}</p>
            {(["min", "max"] as const).map((k) => (
              <div key={k}>
                <Controller control={control} name={`ranges.limits.${c}.${k}` as `ranges.limits.${string}.min`} defaultValue="" render={({ field }) => (
                  <Input {...field} inputMode="decimal" placeholder={k === "min" ? "Mínimo" : "Máximo"} aria-label={`${k === "min" ? "Mínimo" : "Máximo"} de ${c}`}
                    aria-invalid={!!errors.ranges?.limits?.[c]?.[k]} />
                )} />
                {errors.ranges?.limits?.[c]?.[k] && <p className="mt-1 text-xs text-destructive">{errors.ranges.limits[c]![k]!.message}</p>}
              </div>
            ))}
          </div>
        ))}
        <Field label="Detectar valores suspeitos (estatístico)" hint="Marca valores muito distantes dos demais como «suspeitos», sem tratá-los como erro.">
          <Controller control={control} name="ranges.suspect" render={({ field }) => <ColumnPicker columns={names} value={field.value} onChange={field.onChange} emptyHint="Desativado." />} />
        </Field>
      </RuleCard>

      <RuleCard name="geo" control={control} icon={<MapPin />} title="Coordenadas geográficas"
        description="Latitude entre -90 e 90, longitude entre -180 e 180, sem valores ausentes ou não numéricos.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Coluna de latitude"><Controller control={control} name="geo.lat" render={({ field }) => <ColumnSelect label="Coluna de latitude" columns={names} value={field.value} onChange={field.onChange} />} /></Field>
          <Field label="Coluna de longitude">
            <Controller control={control} name="geo.lon" render={({ field }) => <ColumnSelect label="Coluna de longitude" columns={names} value={field.value} onChange={field.onChange} />} />
            {errors.geo?.lon && <p className="text-xs text-destructive">{errors.geo.lon.message}</p>}
          </Field>
        </div>
      </RuleCard>

      <RuleCard name="dates" control={control} icon={<CalendarClock />} title="Datas inválidas"
        description="Datas impossíveis (30/02), fora do formato, fora de um período ou futuras.">
        <Field label="Colunas de data"><Controller control={control} name="dates.columns" render={({ field }) => <ColumnPicker columns={names} value={field.value} onChange={field.onChange} emptyHint="Escolha ao menos uma coluna." />} /></Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Formato esperado"><Controller control={control} name="dates.dateFormat" render={({ field }) => <FormatSelect value={field.value} onChange={field.onChange} />} /></Field>
          <Field label="Data mínima (opcional)"><Controller control={control} name="dates.minDate" render={({ field }) => <Input type="date" {...field} />} /></Field>
          <Field label="Data máxima (opcional)">
            <Controller control={control} name="dates.maxDate" render={({ field }) => <Input type="date" {...field} />} />
            {errors.dates?.maxDate && <p className="text-xs text-destructive">{errors.dates.maxDate.message}</p>}
          </Field>
        </div>
        <Controller control={control} name="dates.flagFuture" render={({ field }) => (
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox checked={field.value} onCheckedChange={(c) => field.onChange(c === true)} /> Considerar datas futuras inválidas
          </label>
        )} />
      </RuleCard>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div className="flex gap-3">
            <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-success/10 text-success"><ShieldCheck className="size-5" /></span>
            <div><CardTitle>Privacidade</CardTitle>
              <CardDescription className="mt-1">Guardar o valor original das células nas ocorrências facilita a revisão. Desative para armazenar apenas posição e tipo do problema.</CardDescription></div>
          </div>
          <Controller control={control} name="storeValues" render={({ field }) => <Switch checked={field.value} onCheckedChange={field.onChange} aria-label="Armazenar valores originais" />} />
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div className="flex gap-3">
            <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand"><Wrench className="size-5" /></span>
            <div><CardTitle>Manter a base para tratamento e análise exploratória</CardTitle>
              <CardDescription className="mt-1">Guarda uma cópia privada e versionada da planilha para você corrigir os problemas e gerar a EDA. Seu arquivo original nunca é alterado e você pode excluir tudo a qualquer momento (a cópia também expira sozinha). Desativado, o DataCheck só faz o diagnóstico.</CardDescription></div>
          </div>
          <Controller control={control} name="keepData" render={({ field }) => <Switch checked={field.value} onCheckedChange={field.onChange} aria-label="Manter a base armazenada" />} />
        </CardHeader>
      </Card>

      {formError && <p role="alert" className="flex items-center gap-2 text-sm text-destructive"><AlertCircle className="size-4" />{formError}</p>}
      {Object.keys(errors).filter((k) => k !== "_form").length > 0 && <p role="alert" className="flex items-center gap-2 text-sm text-destructive"><AlertCircle className="size-4" />Corrija os campos destacados.</p>}
      <div className="sticky bottom-4 flex justify-end">
        <Button type="submit" size="lg" variant="brand" disabled={running} className="shadow-lg">
          <PlayCircle />{running ? "Analisando…" : "Analisar dados"}
        </Button>
      </div>
    </form>
  );
}
