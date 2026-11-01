import axios, { AxiosError } from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
  withCredentials: true, // cookie de sessão HttpOnly (login opcional)
  timeout: 120_000,
});

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError<{ detail?: unknown }>) => {
    let detail = error.response?.data?.detail;
    // Downloads (blob) também trazem o erro em JSON.
    if (!detail && error.response?.data instanceof Blob) {
      try { detail = JSON.parse(await error.response.data.text()).detail; } catch { /* ignora */ }
    }
    const status = error.response?.status;
    let message: string;
    if (typeof detail === "string" && detail) message = detail;
    // O backend sempre envia um texto de erro; 5xx sem texto vem do proxy/rede (servidor fora do ar).
    else if (!error.response || (status !== undefined && status >= 500))
      message = "Não foi possível conectar ao servidor do DataCheck. Verifique se o backend está em execução.";
    else if (error.code === "ECONNABORTED") message = "O servidor demorou demais para responder.";
    else message = "Ocorreu um erro inesperado. Tente novamente.";
    return Promise.reject(new ApiError(message, status));
  },
);

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Ocorreu um erro inesperado.";
}
