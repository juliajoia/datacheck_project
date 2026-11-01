import { LogIn, LogOut, Settings, UserPlus, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AuthDialog, type AuthMode } from "@/components/AuthDialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

/** Avatar redondo: visitante vê um ícone neutro; logado vê a inicial do nome. Login é opcional. */
export function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<{ open: boolean; mode: AuthMode }>({ open: false, mode: "login" });
  const open = (mode: AuthMode) => setDialog({ open: true, mode });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            aria-label={user ? `Menu da conta de ${user.name}` : "Menu da conta: entrar ou criar conta"}
            className={cn("flex size-10 items-center justify-center rounded-full text-sm font-bold shadow-soft ring-2 ring-transparent transition hover:ring-primary/40 data-[state=open]:ring-primary/60",
              user ? "bg-gradient-to-br from-primary to-brand text-white" : "border bg-card text-muted-foreground hover:text-foreground")}
          >
            {user ? user.name.trim().charAt(0).toUpperCase() : <UserRound className="size-5" />}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {user ? (
            <>
              <DropdownMenuLabel className="space-y-0.5"><p className="truncate">{user.name}</p><p className="truncate text-xs font-normal text-muted-foreground">{user.email}</p></DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => navigate("/configuracoes")}><Settings />Configurações</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => { void logout().then(() => toast.success("Você saiu da conta.")); }}><LogOut />Sair</DropdownMenuItem>
            </>
          ) : (
            <>
              <DropdownMenuLabel className="space-y-0.5"><p>Visitante</p><p className="text-xs font-normal text-muted-foreground">Você pode usar o DataCheck sem conta.</p></DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => open("login")}><LogIn />Entrar</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => open("register")}><UserPlus />Criar conta</DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <AuthDialog open={dialog.open} mode={dialog.mode} onModeChange={(mode) => setDialog({ open: true, mode })} onOpenChange={(o) => setDialog((d) => ({ ...d, open: o }))} />
    </>
  );
}
