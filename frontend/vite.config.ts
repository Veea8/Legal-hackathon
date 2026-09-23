import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API proxy target for `npm run dev`; override with API_PROXY=http://localhost:8001 npm run dev
const apiProxy = process.env.API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": apiProxy },
  },
});
