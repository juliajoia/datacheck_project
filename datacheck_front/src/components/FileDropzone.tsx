import { FileSpreadsheet, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { cn } from "@/lib/utils";

interface Props { maxMb: number; disabled?: boolean; onFile: (f: File) => void }

export function FileDropzone({ maxMb, disabled, onFile }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const pick = (files: FileList | null) => { if (files?.[0]) onFile(files[0]); };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); if (!disabled) pick(e.dataTransfer.files); };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={cn("flex flex-col items-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors",
        over ? "border-primary bg-accent" : "bg-card hover:border-primary/60", disabled && "pointer-events-none opacity-60")}
    >
      <span className="flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/15 to-brand/15 text-primary">
        <UploadCloud className="size-7" />
      </span>
      <div>
        <p className="font-semibold">Arraste sua planilha aqui</p>
        <p className="text-sm text-muted-foreground">ou <button type="button" className="font-medium text-primary underline-offset-4 hover:underline" onClick={() => input.current?.click()}>escolha um arquivo</button></p>
      </div>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><FileSpreadsheet className="size-4" /> CSV ou XLSX · até {maxMb} MB</p>
      <input ref={input} type="file" accept=".csv,.xlsx" className="sr-only" aria-label="Selecionar arquivo" onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
    </div>
  );
}
