import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      default: "bg-accent text-accent-foreground",
      muted: "bg-muted text-muted-foreground",
      success: "bg-success/15 text-success",
      warning: "bg-warning/20 text-[hsl(32_90%_35%)] dark:text-warning",
      destructive: "bg-destructive/15 text-destructive",
      info: "bg-primary/15 text-primary",
    },
  },
  defaultVariants: { variant: "default" },
});

export function Badge({ className, variant, ...p }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...p} />;
}
