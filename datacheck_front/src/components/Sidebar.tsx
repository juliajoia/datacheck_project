import { ChartNoAxesCombined, FilePlus2, FolderOpen, History, Info, LayoutDashboard, FileBarChart, Settings, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";

export const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/nova-analise", label: "Nova análise", icon: FilePlus2 },
  { to: "/minhas-analises", label: "Minhas análises", icon: FolderOpen },
  { to: "/historico", label: "Histórico", icon: History },
  { to: "/eda", label: "EDA", icon: ChartNoAxesCombined },
  { to: "/relatorios", label: "Relatórios", icon: FileBarChart },
  { to: "/configuracoes", label: "Configurações", icon: Settings },
  { to: "/sobre", label: "Sobre o DataCheck", icon: Info },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm lg:hidden" onClick={onClose} aria-hidden />}
      <aside
        className={cn("fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card transition-transform duration-200 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full")}
        aria-label="Navegação principal"
      >
        <div className="relative flex h-16 items-center justify-center px-5">
          <Logo className="h-11" />
          <button className="absolute right-3 rounded-md p-1 lg:hidden" onClick={onClose} aria-label="Fechar menu"><X className="size-5" /></button>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={onClose}
              className={({ isActive }) => cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive ? "bg-gradient-to-r from-primary/15 to-brand/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
              <Icon className="size-[18px]" />{label}
            </NavLink>
          ))}
        </nav>
        <p className="px-5 pb-5 text-xs text-muted-foreground">Dados confiáveis.<br />Decisões inteligentes.</p>
      </aside>
    </>
  );
}
