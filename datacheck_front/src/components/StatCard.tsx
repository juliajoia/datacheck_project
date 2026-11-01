import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number | null | undefined;
  icon: LucideIcon;
  hint?: string;
  tone?: "primary" | "brand" | "success" | "warning" | "destructive";
  loading?: boolean;
}
const tones = {
  primary: "bg-primary/10 text-primary", brand: "bg-brand/10 text-brand", success: "bg-success/10 text-success",
  warning: "bg-warning/15 text-warning", destructive: "bg-destructive/10 text-destructive",
};

export function StatCard({ label, value, icon: Icon, hint, tone = "primary", loading }: Props) {
  return (
    <Card className="animate-fade-up p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          {loading ? <Skeleton className="mt-2 h-8 w-20" /> : <p className="mt-1 truncate text-2xl font-bold tracking-tight">{value ?? "—"}</p>}
          {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
        </div>
        <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", tones[tone])}><Icon className="size-5" /></span>
      </div>
    </Card>
  );
}
