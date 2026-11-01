import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <ProgressPrimitive.Root value={value} className={cn("relative h-2 w-full overflow-hidden rounded-full bg-muted", className)}>
      <ProgressPrimitive.Indicator className="h-full bg-gradient-to-r from-primary to-brand transition-all" style={{ width: `${value}%` }} />
    </ProgressPrimitive.Root>
  );
}
