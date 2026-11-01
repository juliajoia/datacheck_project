import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    build: { rollupOptions: { output: { manualChunks: { charts: ["recharts"], vendor: ["react", "react-dom", "react-router-dom"] } } } },
    resolve: { alias: { "@": path.resolve(__dirname, "src") } },
    server: {
      port: 5173,
      // O proxy mantém front e API na mesma origem (cookie de sessão HttpOnly sem CORS em desenvolvimento).
      proxy: { "/api": { target: env.VITE_PROXY_TARGET || "http://localhost:8000", changeOrigin: true } },
    },
  };
});
