export const fmtInt = (n: number) => n.toLocaleString("pt-BR");

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 ** 2).toFixed(1)} MB`;
}

export const fmtDateTime = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

export const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

export const scoreColor = (s: number | null) =>
  s === null ? "hsl(var(--muted-foreground))" : s >= 90 ? "hsl(var(--success))" : s >= 75 ? "hsl(var(--primary))" : s >= 50 ? "hsl(var(--warning))" : "hsl(var(--destructive))";

export const DATE_FORMATS: { label: string; value: string }[] = [
  { label: "Automático (AAAA-MM-DD, DD/MM/AAAA…)", value: "auto" },
  { label: "AAAA-MM-DD", value: "%Y-%m-%d" },
  { label: "DD/MM/AAAA", value: "%d/%m/%Y" },
  { label: "DD-MM-AAAA", value: "%d-%m-%Y" },
  { label: "MM/DD/AAAA", value: "%m/%d/%Y" },
];

export const WORKFLOW: Record<string, { label: string; variant: "muted" | "info" | "warning" | "success" | "default" }> = {
  analyzed: { label: "Analisada", variant: "muted" },
  in_treatment: { label: "Em tratamento", variant: "info" },
  pending: { label: "Com pendências", variant: "warning" },
  ready_for_eda: { label: "Pronta para EDA", variant: "success" },
  eda_generated: { label: "EDA gerada", variant: "default" },
};
