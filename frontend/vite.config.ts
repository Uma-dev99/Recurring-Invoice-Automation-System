import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Where the Vite dev server forwards /api and /admin requests.
// Locally: Django on :8000. In Docker Compose: the "backend" service.
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    // Docker Desktop on Windows/macOS does not pass file-change events from the host
    // into the container, so Vite never notices edits and keeps serving stale modules.
    // Polling checks files on an interval instead. Enabled only where it's needed
    // (docker-compose sets VITE_USE_POLLING=true), because polling costs CPU.
    watch: process.env.VITE_USE_POLLING === "true" ? { usePolling: true, interval: 300 } : undefined,
    // The proxy makes the browser see ONE origin (localhost:5173) for both the SPA
    // and the API. Cookies then behave as first-party and no CORS is needed.
    proxy: {
      "/api": { target: apiTarget, changeOrigin: false },
      "/admin": { target: apiTarget, changeOrigin: false },
      "/static": { target: apiTarget, changeOrigin: false },
    },
  },
});
