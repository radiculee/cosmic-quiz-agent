import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Locally, /api is the Python dev server (`python -m dev.api_server`, port 8787). On Vercel the
// same paths are served by the functions in api/. `xfwd` passes the visitor's address on as
// X-Forwarded-For, as Vercel does, so per-visitor features behave the same in both places.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8787", xfwd: true },
    },
  },
});
