import { AlertOctagon, AlertTriangle, CheckCircle2, Info, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";
import type { InsightItem } from "@/types";

const style = {
  success: { icon: CheckCircle2, cls: "border-success/40 bg-success/5 [&_.i]:text-success" },
  info: { icon: Info, cls: "border-primary/30 bg-primary/5 [&_.i]:text-primary" },
  warning: { icon: AlertTriangle, cls: "border-warning/50 bg-warning/5 [&_.i]:text-warning" },
  critical: { icon: AlertOctagon, cls: "border-destructive/40 bg-destructive/5 [&_.i]:text-destructive" },
};

export function InsightsList({ items }: { items: InsightItem[] }) {
  return (
    <ul className="space-y-3">
      {items.map((it, i) => {
        const { icon: Icon, cls } = style[it.level];
        return (
          <li key={i} className={cn("animate-fade-up rounded-xl border p-4", cls)} style={{ animationDelay: `${i * 40}ms` }}>
            <div className="flex gap-3">
              <Icon className="i mt-0.5 size-5 shrink-0" />
              <div className="min-w-0 space-y-1">
                <p className="font-semibold">{it.title}</p>
                <p className="text-sm">{it.text}</p>
                <p className="flex items-start gap-1.5 text-sm text-muted-foreground"><Lightbulb className="mt-0.5 size-4 shrink-0" />{it.recommendation}</p>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
