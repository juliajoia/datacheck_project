import { createContext, useContext } from "react";
import type { AnalysisResult, CleaningSummary } from "@/types";

/** Estado compartilhado pelas etapas de uma base aberta em «Minhas análises». */
export interface Workspace {
  id: string;
  analysis: AnalysisResult;
  summary: CleaningSummary;
  /** Muda a cada alteração aplicada; os painéis que listam dados a usam para recarregar. */
  refreshKey: number;
  /** Registra o resumo devolvido por uma correção, desfazer, restauração ou validação. */
  applied: (s: CleaningSummary) => void;
  bump: () => void;
  validating: boolean;
  validate: () => Promise<void>;
  reload: () => Promise<void>;
}

export const WorkspaceContext = createContext<Workspace | null>(null);

export function useWorkspace(): Workspace {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace deve ser usado dentro de AnalysisWorkspace");
  return ctx;
}
