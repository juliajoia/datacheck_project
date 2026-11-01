import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { useAuth } from "@/contexts/AuthContext";

export function AppLayout() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="min-h-screen">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="lg:pl-64">
        <Header onMenu={() => setOpen(true)} />
        <main className="mx-auto max-w-7xl p-4 lg:p-8">{/* key: ao entrar/sair, as páginas recarregam os dados do usuário correto */}
        <Outlet key={user?.id ?? "visitante"} /></main>
      </div>
    </div>
  );
}
