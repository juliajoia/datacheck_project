import { Moon, ShieldCheck, Sun } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useApi } from "@/hooks/useApi";
import { useKeepDataPreference, useStoreValuesPreference } from "@/hooks/usePreferences";
import { metaService } from "@/services";

export default function Settings() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const [store, setStore] = useStoreValuesPreference();
  const [keep, setKeep] = useKeepDataPreference();
  const { data: server } = useApi(metaService.settings);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card>
        <CardHeader><CardTitle>Conta</CardTitle></CardHeader>
        <CardContent className="space-y-1 text-sm">
          {user ? (<><p><span className="text-muted-foreground">Nome:</span> {user.name}</p><p><span className="text-muted-foreground">E-mail:</span> {user.email}</p></>)
            : (<><Badge variant="muted">Visitante</Badge><p className="pt-1 text-muted-foreground">Você está usando o DataCheck sem conta. Para manter suas análises privadas, use o avatar no canto superior direito para entrar ou criar uma conta. É opcional.</p></>)}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Aparência</CardTitle><CardDescription>O tema é lembrado neste navegador.</CardDescription></CardHeader>
        <CardContent className="flex gap-2">
          <Button variant={theme === "light" ? "default" : "outline"} onClick={() => setTheme("light")}><Sun />Claro</Button>
          <Button variant={theme === "dark" ? "default" : "outline"} onClick={() => setTheme("dark")}><Moon />Escuro</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="size-4" />Privacidade</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div><Label htmlFor="store">Armazenar valores originais das células</Label>
              <p className="mt-1 text-sm text-muted-foreground">Padrão para novas análises. Desativado, o sistema guarda só a posição e o tipo de cada problema, sem o conteúdo da célula (minimização de dados). Você ainda pode alterar em cada análise.</p></div>
            <Switch id="store" checked={store} onCheckedChange={setStore} />
          </div>
          <div className="flex items-start justify-between gap-4">
            <div><Label htmlFor="keep">Manter a base armazenada para tratamento e EDA</Label>
              <p className="mt-1 text-sm text-muted-foreground">Padrão para novas análises. Guarda uma cópia privada e versionada da planilha (o arquivo original nunca é alterado), necessária para corrigir dados e gerar a análise exploratória. Desativado, o DataCheck só faz o diagnóstico.</p></div>
            <Switch id="keep" checked={keep} onCheckedChange={setKeep} />
          </div>
          <p className="text-sm text-muted-foreground">O arquivo enviado fica em área temporária até a análise terminar (ou por até 1 hora). Se você mantiver a base, a cópia é apagada ao excluir a análise ou automaticamente após {server?.data_retention_days ?? 30} dias.</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Limites do servidor</CardTitle></CardHeader>
        <CardContent className="grid gap-1 text-sm">
          <p><span className="text-muted-foreground">Tamanho máximo de upload:</span> {server ? `${server.max_upload_mb} MB` : "…"}</p>
          <p><span className="text-muted-foreground">Formatos aceitos:</span> {server?.allowed_extensions.join(", ") ?? "…"}</p>
          <p className="text-xs text-muted-foreground">O limite é definido pelo administrador (variável DATACHECK_MAX_UPLOAD_MB no backend).</p>
        </CardContent>
      </Card>
    </div>
  );
}
