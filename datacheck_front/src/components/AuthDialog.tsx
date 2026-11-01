import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { errorMessage } from "@/lib/api";

export type AuthMode = "login" | "register";

const loginSchema = z.object({
  email: z.string().min(1, "Informe seu e-mail").email("E-mail inválido"),
  password: z.string().min(1, "Informe sua senha"),
});
const registerSchema = z.object({
  name: z.string().trim().min(2, "Informe seu nome").max(120),
  email: z.string().min(1, "Informe seu e-mail").email("E-mail inválido"),
  password: z.string().min(8, "A senha deve ter ao menos 8 caracteres").max(128),
  confirm: z.string(),
}).refine((v) => v.password === v.confirm, { path: ["confirm"], message: "As senhas não coincidem" });

interface Props { open: boolean; mode: AuthMode; onModeChange: (m: AuthMode) => void; onOpenChange: (o: boolean) => void }

export function AuthDialog({ open, mode, onModeChange, onOpenChange }: Props) {
  const isLogin = mode === "login";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{isLogin ? "Entrar" : "Criar conta"}</DialogTitle>
          <DialogDescription>
            {isLogin ? "Acesse suas análises privadas." : "Opcional: com uma conta, suas análises ficam privadas e acessíveis em qualquer sessão."}
          </DialogDescription>
        </DialogHeader>
        {isLogin ? <LoginForm onDone={() => onOpenChange(false)} /> : <RegisterForm onDone={() => onOpenChange(false)} />}
        <p className="text-center text-sm text-muted-foreground">
          {isLogin ? "Ainda não tem conta? " : "Já tem conta? "}
          <button type="button" className="font-medium text-primary hover:underline" onClick={() => onModeChange(isLogin ? "register" : "login")}>
            {isLogin ? "Criar conta" : "Entrar"}
          </button>
        </p>
      </DialogContent>
    </Dialog>
  );
}

function useSubmitError() {
  const [error, setError] = useState<string | null>(null);
  useEffect(() => () => setError(null), []);
  return [error, setError] as const;
}

function LoginForm({ onDone }: { onDone: () => void }) {
  const { login } = useAuth();
  const [error, setError] = useSubmitError();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const submit = handleSubmit(async (v) => {
    setError(null);
    try { await login(v.email, v.password); toast.success("Você entrou no DataCheck."); onDone(); }
    catch (e) { setError(errorMessage(e)); }
  });
  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="space-y-1.5"><Label htmlFor="auth-email">E-mail</Label>
        <Input id="auth-email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} />
        {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}</div>
      <div className="space-y-1.5"><Label htmlFor="auth-password">Senha</Label>
        <Input id="auth-password" type="password" autoComplete="current-password" aria-invalid={!!errors.password} {...register("password")} />
        {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}</div>
      {error && <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      <Button type="submit" variant="brand" className="w-full" disabled={isSubmitting}>{isSubmitting ? "Entrando…" : "Entrar"}</Button>
    </form>
  );
}

function RegisterForm({ onDone }: { onDone: () => void }) {
  const { register: signUp } = useAuth();
  const [error, setError] = useSubmitError();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema) });
  const submit = handleSubmit(async (v) => {
    setError(null);
    try { await signUp(v.name, v.email, v.password); toast.success("Conta criada. Bem-vindo(a) ao DataCheck!"); onDone(); }
    catch (e) { setError(errorMessage(e)); }
  });
  const field = (id: "name" | "email" | "password" | "confirm", label: string, type = "text", auto?: string) => (
    <div className="space-y-1.5"><Label htmlFor={`reg-${id}`}>{label}</Label>
      <Input id={`reg-${id}`} type={type} autoComplete={auto} aria-invalid={!!errors[id]} {...register(id)} />
      {errors[id] && <p className="text-xs text-destructive">{errors[id]!.message}</p>}</div>
  );
  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      {field("name", "Nome", "text", "name")}{field("email", "E-mail", "email", "email")}
      {field("password", "Senha (mín. 8 caracteres)", "password", "new-password")}{field("confirm", "Confirmar senha", "password", "new-password")}
      {error && <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      <Button type="submit" variant="brand" className="w-full" disabled={isSubmitting}>{isSubmitting ? "Criando…" : "Criar conta"}</Button>
    </form>
  );
}
