import { Badge } from "@/components/ui/badge";
import type { Severity } from "@/types";

const variant = { critical: "destructive", warning: "warning", info: "info" } as const;
export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "hsl(var(--destructive))", warning: "hsl(var(--warning))", info: "hsl(var(--primary))",
};
const label = { critical: "Crítica", warning: "Aviso", info: "Informativa" };

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge variant={variant[severity]}>{label[severity]}</Badge>;
}
