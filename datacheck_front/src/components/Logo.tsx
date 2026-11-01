import { cn } from "@/lib/utils";

/**
 * Logo oficial do DataCheck: uma versão para fundo claro e outra para fundo escuro,
 * trocadas pelo tema. `showText=false` mostra só o ícone.
 */
export function Logo({ className, showText = true }: { className?: string; showText?: boolean }) {
  if (!showText) return <img src="/logo-mark.png" alt="DataCheck" className={cn("size-9", className)} />;
  return (
    <>
      <img src="/logo-light.png" alt="DataCheck" className={cn("h-9 w-auto dark:hidden", className)} />
      <img src="/logo-dark.png" alt="" aria-hidden className={cn("hidden h-9 w-auto dark:block", className)} />
    </>
  );
}
