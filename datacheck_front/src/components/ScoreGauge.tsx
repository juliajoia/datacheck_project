import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { scoreColor } from "@/utils/format";

interface Props { value: number | null; label: string; disclaimer: string; formula: string }

export function ScoreGauge({ value, label, disclaimer, formula }: Props) {
  const r = 70, c = 2 * Math.PI * r, arc = c * 0.75;
  const pct = value ?? 0;
  const color = scoreColor(value);
  return (
    <div className="flex flex-col items-center">
      <div className="relative size-48">
        <svg viewBox="0 0 180 180" className="size-full -rotate-[225deg]" role="img" aria-label={`DataCheck Score ${value ?? "indisponível"} de 100`}>
          <circle cx="90" cy="90" r={r} fill="none" stroke="hsl(var(--muted))" strokeWidth="14" strokeLinecap="round" strokeDasharray={`${arc} ${c}`} />
          <circle cx="90" cy="90" r={r} fill="none" stroke={color} strokeWidth="14" strokeLinecap="round"
            strokeDasharray={`${(arc * pct) / 100} ${c}`} style={{ transition: "stroke-dasharray .8s ease" }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold tracking-tight" style={{ color }}>{value === null ? "—" : value.toLocaleString("pt-BR")}</span>
          <span className="text-xs text-muted-foreground">de 100</span>
        </div>
      </div>
      <div className="-mt-4 flex items-center gap-1.5">
        <span className="text-sm font-semibold">DataCheck Score · {label}</span>
        <Tooltip>
          <TooltipTrigger aria-label="Sobre o DataCheck Score" className="text-muted-foreground hover:text-foreground"><Info className="size-4" /></TooltipTrigger>
          <TooltipContent className="max-w-sm"><p className="font-semibold">{formula}</p><p className="mt-1">{disclaimer}</p></TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}
