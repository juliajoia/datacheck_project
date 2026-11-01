import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authService } from "@/services";
import type { User } from "@/types";

/** Login é opcional: `user === null` significa visitante e o app funciona normalmente. */
interface AuthState {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => { authService.me().then(setUser).catch(() => setUser(null)); }, []);

  const login = useCallback(async (email: string, password: string) => setUser(await authService.login({ email, password })), []);
  const register = useCallback(
    async (name: string, email: string, password: string) => setUser(await authService.register({ name, email, password })), []);
  const logout = useCallback(async () => { await authService.logout().catch(() => undefined); setUser(null); }, []);

  const value = useMemo(() => ({ user, login, register, logout }), [user, login, register, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth precisa estar dentro de AuthProvider");
  return ctx;
}
