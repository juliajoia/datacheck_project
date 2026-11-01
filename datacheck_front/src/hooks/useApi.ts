import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/api";

/** Carrega dados da API com estados de loading/erro e recarga manual. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    return fnRef.current().then(setData).catch((e) => setError(errorMessage(e))).finally(() => setLoading(false));
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void reload(); }, deps);
  return { data, error, loading, reload };
}
