import { zodResolver } from "@hookform/resolvers/zod";
import { MessageSquareHeart } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/input";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { analysisService } from "@/services";

const schema = z.object({
  usability_rating: z.number({ required_error: "Escolha uma nota" }).int().min(1).max(5),
  usefulness_rating: z.number({ required_error: "Escolha uma nota" }).int().min(1).max(5),
  would_use_again: z.enum(["sim", "talvez", "nao"], { required_error: "Escolha uma opção" }),
  difficulties: z.string().max(2000, "Máximo de 2000 caracteres"),
  suggestions: z.string().max(2000, "Máximo de 2000 caracteres"),
});
type Values = z.infer<typeof schema>;

function Rating({ value, onChange, label }: { value?: number; onChange: (n: number) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex gap-2">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} onClick={() => onChange(n)}
          className={cn("size-10 rounded-lg border text-sm font-semibold transition-colors", value === n ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent")}>
          {n}
        </button>
      ))}
    </div>
  );
}

export function FeedbackDialog({ analysisId, submitted, onSubmitted }: { analysisId: string; submitted: boolean; onSubmitted: () => void }) {
  const [open, setOpen] = useState(false);
  const { control, register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({
    resolver: zodResolver(schema), defaultValues: { difficulties: "", suggestions: "" },
  });

  const submit = handleSubmit(async (v) => {
    try {
      await analysisService.feedback(analysisId, v);
      toast.success("Obrigado! Seu feedback foi registrado.");
      setOpen(false);
      onSubmitted();
    } catch (e) { toast.error(errorMessage(e)); }
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline"><MessageSquareHeart />{submitted ? "Enviar outro feedback" : "Dar feedback"}</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Como foi usar o DataCheck?</DialogTitle>
          <DialogDescription>Sua opinião real orienta as próximas melhorias. Não inclua dados pessoais.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5" noValidate>
          <div className="space-y-2">
            <Label>Facilidade de utilização (1 = muito difícil · 5 = muito fácil)</Label>
            <Controller control={control} name="usability_rating" render={({ field }) => <Rating label="Facilidade" value={field.value} onChange={field.onChange} />} />
            {errors.usability_rating && <p className="text-xs text-destructive">{errors.usability_rating.message}</p>}
          </div>
          <div className="space-y-2">
            <Label>Utilidade percebida (1 = nada útil · 5 = muito útil)</Label>
            <Controller control={control} name="usefulness_rating" render={({ field }) => <Rating label="Utilidade" value={field.value} onChange={field.onChange} />} />
            {errors.usefulness_rating && <p className="text-xs text-destructive">{errors.usefulness_rating.message}</p>}
          </div>
          <div className="space-y-2">
            <Label>Você usaria o DataCheck novamente?</Label>
            <Controller control={control} name="would_use_again" render={({ field }) => (
              <div role="radiogroup" aria-label="Usaria novamente" className="flex gap-2">
                {([["sim", "Sim"], ["talvez", "Talvez"], ["nao", "Não"]] as const).map(([v, l]) => (
                  <button key={v} type="button" role="radio" aria-checked={field.value === v} onClick={() => field.onChange(v)}
                    className={cn("h-10 flex-1 rounded-lg border text-sm font-medium transition-colors", field.value === v ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent")}>{l}</button>
                ))}
              </div>
            )} />
            {errors.would_use_again && <p className="text-xs text-destructive">{errors.would_use_again.message}</p>}
          </div>
          <div className="space-y-2"><Label htmlFor="fb-diff">Dificuldades encontradas</Label><Textarea id="fb-diff" {...register("difficulties")} /></div>
          <div className="space-y-2"><Label htmlFor="fb-sug">Melhorias sugeridas</Label><Textarea id="fb-sug" {...register("suggestions")} /></div>
          <DialogFooter><Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Enviando…" : "Enviar feedback"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
