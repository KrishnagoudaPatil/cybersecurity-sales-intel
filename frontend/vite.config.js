import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api -> FastAPI so the frontend calls a same-origin path.
// In prod, set VITE_API_BASE to the deployed backend URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: p => p.replace(/^\/api/, "") } },
  },
});
