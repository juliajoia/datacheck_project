import { FileSpreadsheet, FlaskConical, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AnalysisConfigForm, buildPayload, defaultValues, type ConfigFormValues } from "@/components/AnalysisConfigForm";
import { FileDropzone } from "@/components/FileDropzone";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useKeepDataPreference, useStoreValuesPreference } from "@/hooks/usePreferences";
import { errorMessage } from "@/lib/api";
import { analysisService, metaService } from "@/services";
import type { PublicSettings, UploadProfile } from "@/types";
import { fmtBytes, fmtInt } from "@/utils/format";

const DEFAULT_SETTINGS: PublicSettings = { max_upload_mb: 10, allowed_extensions: [".csv", ".xlsx"], default_markers: [] };

export default function NewAnalysis() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<PublicSettings>(DEFAULT_SETTINGS);
  const [profile, setProfile] = useState<UploadProfile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pct, setPct] = useState(0);
  const [running, setRunning] = useState(false);
  const [storeValues] = useStoreValuesPreference();
  const [keepData] = useKeepDataPreference();

  useEffect(() => { metaService.settings().then(setSettings).catch(() => undefined); }, []);

  const discard = useCallback((p: UploadProfile | null) => { if (p) analysisService.remove(p.id).catch(() => undefined); }, []);

  const handleFile = async (file: File) => {
    const ext = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] ?? "";
    if (!settings.allowed_extensions.includes(ext)) return toast.error("Formato não suportado. Envie um arquivo .csv ou .xlsx.");
    if (file.size === 0) return toast.error("O arquivo está vazio.");
    if (file.size > settings.max_upload_mb * 1024 * 1024) return toast.error(`O arquivo excede o limite de ${settings.max_upload_mb} MB.`);
    discard(profile);
    setProfile(null); setUploading(true); setPct(0);
    try { setProfile(await analysisService.upload(file, setPct)); }
    catch (e) { toast.error(errorMessage(e)); }
    finally { setUploading(false); }
  };

  const useSample = async (n: "1" | "2") => {
    discard(profile);
    setProfile(null); setUploading(true); setPct(100);
    try { setProfile(await analysisService.uploadSample(n)); }
    catch (e) { toast.error(errorMessage(e)); }
    finally { setUploading(false); }
  };

  const changeSheet = async (sheet: string) => {
    if (!profile) return;
    try { setProfile(await analysisService.profile(profile.id, sheet)); }
    catch (e) { toast.error(errorMessage(e)); }
  };

  const run = async (values: ConfigFormValues) => {
    if (!profile || running) return;
    setRunning(true);
    try {
      const res = await analysisService.run(profile.id, buildPayload(values, profile.selected_sheet));
      toast.success("Análise concluída.");
      navigate(`/minhas-analises/${res.id}`);
    } catch (e) {
      toast.error(errorMessage(e));
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Verifique a qualidade da sua planilha</h2>
        <p className="mt-1 text-muted-foreground">Envie o arquivo, escolha as verificações e receba um diagnóstico. Seus dados originais não são alterados.</p>
      </div>

      <Step n={1} title="Enviar planilha" />
      {!profile && (
        <>
          <FileDropzone maxMb={settings.max_upload_mb} disabled={uploading} onFile={handleFile} />
          {uploading && (
            <Card className="p-4"><div className="flex items-center gap-3 text-sm"><Loader2 className="size-4 animate-spin" /> Enviando e lendo o arquivo…<Progress value={pct} className="flex-1" /></div></Card>
          )}
          <Card className="border-dashed">
            <CardContent className="flex flex-wrap items-center gap-3 p-4">
              <FlaskConical className="size-5 text-brand" />
              <p className="flex-1 text-sm text-muted-foreground">Sem planilha à mão? Teste com uma base fictícia que contém erros propositais.</p>
              <Button variant="outline" size="sm" disabled={uploading} onClick={() => useSample("1")}>Base de demonstração 1</Button>
              <Button variant="outline" size="sm" disabled={uploading} onClick={() => useSample("2")}>Base 2 (formato brasileiro)</Button>
            </CardContent>
          </Card>
        </>
      )}

      {profile && (
        <>
          <Card className="animate-fade-up">
            <CardHeader className="flex-row items-start justify-between gap-4">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-success/10 text-success"><FileSpreadsheet className="size-5" /></span>
                <div className="min-w-0"><CardTitle className="truncate">{profile.filename}</CardTitle>
                  <CardDescription>{fmtBytes(profile.size_bytes)} · {profile.filename.split(".").pop()?.toUpperCase()}{profile.encoding ? ` · ${profile.encoding}` : ""}</CardDescription></div>
              </div>
              <Button variant="ghost" size="sm" disabled={running} onClick={() => { discard(profile); setProfile(null); }}><RefreshCw />Trocar arquivo</Button>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Info label="Linhas" value={fmtInt(profile.n_rows)} /><Info label="Colunas" value={profile.n_cols} />
                <Info label="Formato" value={profile.filename.split(".").pop()?.toUpperCase() ?? ""} />
                <Info label="Separador" value={profile.delimiter ? `«${profile.delimiter === "\t" ? "tab" : profile.delimiter}»` : "—"} />
              </div>
              {profile.sheets.length > 1 && (
                <div className="max-w-xs space-y-1.5"><p className="text-sm font-medium">Aba a analisar</p>
                  <Select value={profile.selected_sheet ?? undefined} onValueChange={changeSheet}>
                    <SelectTrigger aria-label="Aba"><SelectValue /></SelectTrigger>
                    <SelectContent>{profile.sheets.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select></div>
              )}
              <div>
                <p className="mb-1 text-sm font-medium">Colunas e tipos identificados</p>
                <p className="mb-2 text-xs text-muted-foreground">O tipo estatístico (ex.: quantitativa, qualitativa, identificador) é uma estimativa e pode ser alterado depois, na tela de tratamento. Códigos como CPF ou CEP não são tratados como números.</p>
                <div className="flex flex-wrap gap-2">
                  {profile.columns.map((c) => <Badge key={c.name} variant="muted" className="gap-1.5 py-1" title={c.stat_reasons?.join(" ")}><span className="font-semibold text-foreground">{c.name}</span>{c.dtype_label}{c.stat_label && <span className="text-primary">· {c.stat_label}</span>}</Badge>)}
                </div>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium">Prévia dos primeiros registros</p>
                <div className="overflow-hidden rounded-lg border">
                  <Table>
                    <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Linha</TableHead>{profile.preview.columns.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow></TableHeader>
                    <TableBody>
                      {profile.preview.rows.map((r, i) => (
                        <TableRow key={i}><TableCell className="font-mono text-xs text-muted-foreground">{profile.preview.lines[i]}</TableCell>
                          {r.map((v, j) => <TableCell key={j} className="max-w-[12rem] truncate">{v === "" ? <span className="text-muted-foreground">—</span> : v}</TableCell>)}</TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </CardContent>
          </Card>

          <Step n={2} title="Configurar verificações" />
          {running && (
            <Card className="animate-fade-up border-primary/40 p-5" role="status" aria-live="polite">
              <div className="flex items-center gap-3"><Loader2 className="size-5 animate-spin text-primary" />
                <div className="flex-1"><p className="font-medium">Executando as verificações…</p>
                  <p className="text-sm text-muted-foreground">Validando, calculando indicadores e registrando o resultado. Não feche esta página.</p></div></div>
            </Card>
          )}
          <fieldset disabled={running} className="min-w-0">
            <AnalysisConfigForm key={`${profile.id}-${profile.selected_sheet}`} profile={profile} running={running} onSubmit={run}
              initial={defaultValues(profile, storeValues, settings.default_markers, keepData)} />
          </fieldset>
        </>
      )}
    </div>
  );
}

function Step({ n, title }: { n: number; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex size-7 items-center justify-center rounded-full bg-gradient-to-br from-primary to-brand text-sm font-bold text-white">{n}</span>
      <h3 className="text-lg font-semibold">{title}</h3>
    </div>
  );
}

const Info = ({ label, value }: { label: string; value: string | number }) => (
  <div className="rounded-lg bg-muted/60 px-3 py-2"><p className="text-xs text-muted-foreground">{label}</p><p className="font-semibold">{value}</p></div>
);
