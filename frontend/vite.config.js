import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy /api to the FastAPI backend on :8099.
// Build: emit the SPA into ../backend/static so FastAPI can serve it.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8099",
    },
  },
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
});
