import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AppLayout } from "@/layouts/AppLayout";
import History from "@/pages/History";
import NotFound from "@/pages/NotFound";
import Reports from "@/pages/Reports";
import Settings from "@/pages/Settings";
import { Skeleton } from "@/components/ui/skeleton";

// Páginas com gráficos/tabelas pesadas são carregadas sob demanda.
const About = lazy(() => import("@/pages/About"));
const AnalysisResults = lazy(() => import("@/pages/AnalysisResults"));
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const NewAnalysis = lazy(() => import("@/pages/NewAnalysis"));
const Treatment = lazy(() => import("@/pages/Treatment"));
const TreatedData = lazy(() => import("@/pages/TreatedData"));
const Changes = lazy(() => import("@/pages/Changes"));
const MyAnalyses = lazy(() => import("@/pages/MyAnalyses"));
const AnalysisWorkspace = lazy(() => import("@/layouts/AnalysisWorkspace"));
const Eda = lazy(() => import("@/pages/Eda"));
const EdaReport = lazy(() => import("@/pages/EdaReport"));
// Endereços antigos continuam funcionando.
const ToWorkspace = ({ step }: { step: string }) => { const { id = "" } = useParams(); return <Navigate to={`/minhas-analises/${id}/${step}`} replace />; };
const fallback = <Skeleton className="h-64 w-full" />;

export default function App() {
  return (
    <ThemeProvider>
        <AuthProvider>
      <TooltipProvider delayDuration={150}>
          <BrowserRouter>
            <Suspense fallback={fallback}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route index element={<Dashboard />} />
                <Route path="/nova-analise" element={<NewAnalysis />} />
                <Route path="/minhas-analises" element={<MyAnalyses />} />
                <Route path="/minhas-analises/:id" element={<AnalysisWorkspace />}>
                  <Route index element={<Navigate to="diagnostico" replace />} />
                  <Route path="diagnostico" element={<AnalysisResults />} />
                  <Route path="tratamento" element={<Treatment />} />
                  <Route path="dados-tratados" element={<TreatedData />} />
                  <Route path="alteracoes" element={<Changes />} />
                </Route>
                <Route path="/analises/:id" element={<ToWorkspace step="diagnostico" />} />
                <Route path="/analises/:id/tratamento" element={<ToWorkspace step="tratamento" />} />
                <Route path="/historico" element={<History />} />
                <Route path="/eda" element={<Eda />} />
                <Route path="/eda/:id" element={<EdaReport />} />
                <Route path="/relatorios" element={<Reports />} />
                <Route path="/configuracoes" element={<Settings />} />
                <Route path="/sobre" element={<About />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
            </Suspense>
          </BrowserRouter>
          <Toaster />
        </TooltipProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
