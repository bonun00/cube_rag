import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api 는 FastAPI(localhost:8000)로 넘긴다 — 브라우저는 같은 출처로 보므로 CORS 문제가 없다
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
