import { ChevronRight, Menu } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/button";

const TITLES: Record<string, string> = {
  "/": "Dashboard", "/nova-analise": "Nova análise", "/minhas-analises": "Minhas análises", "/historico": "Histórico de análises",
  "/eda": "Análise exploratória (EDA)", "/relatorios": "Relatórios", "/configuracoes": "Configurações", "/sobre": "Sobre o DataCheck",
};

export function Header({ onMenu }: { onMenu: () => void }) {
  const { pathname } = useLocation();
  const inWorkspace = pathname.startsWith("/minhas-analises/");
  const isResult = inWorkspace || pathname.startsWith("/eda/");
  const STEPS: Record<string, string> = { diagnostico: "Diagnóstico", tratamento: "Tratamento", "dados-tratados": "Dados tratados", alteracoes: "Alterações" };
  const step = STEPS[pathname.split("/")[3] ?? ""] ?? "Diagnóstico";
  const title = pathname.startsWith("/eda/") ? "Relatório EDA" : inWorkspace ? step : TITLES[pathname] ?? "DataCheck";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur lg:px-8">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenu} aria-label="Abrir menu"><Menu /></Button>
      <div className="min-w-0 flex-1">
        {isResult && (
          <nav aria-label="Trilha de navegação" className="flex items-center gap-1 text-xs text-muted-foreground">
            <Link to={pathname.startsWith("/eda/") ? "/eda" : "/minhas-analises"} className="hover:text-foreground">{pathname.startsWith("/eda/") ? "EDA" : "Minhas análises"}</Link><ChevronRight className="size-3" /><span>{pathname.startsWith("/eda/") ? "Relatório" : "Análise"}</span>
          </nav>
        )}
        <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>
      </div>
      <ThemeToggle />
      <UserMenu />
    </header>
  );
}
