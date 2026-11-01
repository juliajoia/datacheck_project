import { Logo } from "@/components/Logo";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { metaService } from "@/services";

export default function About() {
  const { data } = useApi(metaService.rules);
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card className="bg-gradient-to-br from-primary/10 to-brand/10 p-6">
        <Logo />
        <p className="mt-4 text-lg font-semibold">Dados confiáveis. Decisões inteligentes.</p>
        <p className="mt-2 text-muted-foreground">O DataCheck automatiza a verificação da qualidade de dados em planilhas: encontra inconsistências antes que elas cheguem a relatórios, dashboards e decisões. Pensado para analistas, pesquisadores, estudantes e equipes administrativas.</p>
      </Card>
      <Card><CardHeader><CardTitle>Verificações disponíveis</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {data ? data.rules.map((r) => <div key={r.code}><p className="font-medium">{r.letter}. {r.name}</p><p className="text-sm text-muted-foreground">{r.description}</p></div>) : <Skeleton className="h-40" />}
        </CardContent></Card>
      <Card><CardHeader><CardTitle>DataCheck Score</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p className="font-mono text-foreground">Score = 100 × (1 − linhas distintas afetadas ÷ total de linhas)</p>
          <p>A mesma linha nunca é contada duas vezes, mesmo que tenha vários problemas. O score representa apenas a cobertura das regras executadas e não garante que os dados estejam completamente corretos.</p></CardContent></Card>
      <Card><CardHeader><CardTitle>Privacidade e limites</CardTitle></CardHeader>
        <CardContent className="space-y-1.5 text-sm text-muted-foreground">
          <p>• Nenhuma planilha é enviada a serviços externos.</p><p>• Os arquivos originais não são guardados permanentemente.</p>
          <p>• Fórmulas e conteúdo das planilhas nunca são executados.</p><p>• O DataCheck nunca corrige ou exclui dados automaticamente: apenas sugere revisões.</p>
          <p>• Os insights são gerados por regras programadas; não há IA generativa integrada nesta versão.</p></CardContent></Card>
    </div>
  );
}
