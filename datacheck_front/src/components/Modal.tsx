import type { ReactNode } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/** Diálogo largo, com rolagem, para fluxos de tratamento. */
export function Modal({ open, onClose, title, description, children, className }: {
  open: boolean; onClose: () => void; title: string; description?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className={cn("max-h-[90vh] max-w-3xl overflow-y-auto", className)}>
        <DialogHeader><DialogTitle>{title}</DialogTitle>{description && <DialogDescription asChild><div>{description}</div></DialogDescription>}</DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  );
}
