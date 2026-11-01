import { cn } from "@/lib/utils";

interface Props {
  columns: string[];
  value: string[];
  onChange: (v: string[]) => void;
  emptyHint?: string;
}

/** Seleção múltipla de colunas por "chips" acessíveis. */
export function ColumnPicker({ columns, value, onChange, emptyHint }: Props) {
  const toggle = (c: string) => onChange(value.includes(c) ? value.filter((x) => x !== c) : [...value, c]);
  return (
    <div>
      <div className="flex flex-wrap gap-1.5" role="group">
        {columns.map((c) => {
          const on = value.includes(c);
          return (
            <button key={c} type="button" aria-pressed={on} onClick={() => toggle(c)}
              className={cn("rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                on ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent")}>
              {c}
            </button>
          );
        })}
      </div>
      {emptyHint && value.length === 0 && <p className="mt-1.5 text-xs text-muted-foreground">{emptyHint}</p>}
    </div>
  );
}
