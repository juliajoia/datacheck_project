import { useCallback, useState } from "react";

const KEY = "datacheck-store-values";

/** Preferência local: guardar (ou não) os valores originais das células nas ocorrências. */
export function useStoreValuesPreference() {
  const [value, setValue] = useState<boolean>(() => {
    try { return localStorage.getItem(KEY) !== "false"; } catch { return true; }
  });
  const update = useCallback((v: boolean) => {
    setValue(v);
    try { localStorage.setItem(KEY, String(v)); } catch { /* ignora */ }
  }, []);
  return [value, update] as const;
}

const KEEP_KEY = "datacheck-keep-data";

/** Preferência local: manter a base armazenada (privada e versionada) para tratamento e EDA. */
export function useKeepDataPreference() {
  const [value, setValue] = useState<boolean>(() => {
    try { return localStorage.getItem(KEEP_KEY) !== "false"; } catch { return true; }
  });
  const update = useCallback((v: boolean) => {
    setValue(v);
    try { localStorage.setItem(KEEP_KEY, String(v)); } catch { /* ignora */ }
  }, []);
  return [value, update] as const;
}
