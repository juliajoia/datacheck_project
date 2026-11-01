import { Toaster as Sonner } from "sonner";
import { useTheme } from "@/contexts/ThemeContext";

export function Toaster() {
  const { theme } = useTheme();
  return <Sonner theme={theme} position="top-right" richColors closeButton />;
}
