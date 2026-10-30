import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

import {
  DESCRIPTION,
  NAME,
  ORIGIN,
  SOCIAL_IMAGE,
  SOCIAL_IMAGE_ALT,
  THEME_COLOR,
  TITLE,
} from "./src/brand";

const BRAND_TOKENS: Record<string, string> = {
  name: NAME,
  title: TITLE,
  description: DESCRIPTION,
  origin: ORIGIN,
  socialImage: SOCIAL_IMAGE,
  socialImageAlt: SOCIAL_IMAGE_ALT,
  themeColor: THEME_COLOR,
};

function escapeAttribute(text: string): string {
  return text.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}

/** Fills the {{brand.x}} tokens in index.html from src/brand.ts, so the name, title and
 * description are written once. A token with no value stops the build. */
function brandHtml(): Plugin {
  return {
    name: "brand-html",
    transformIndexHtml: {
      order: "pre",
      handler: (html) =>
        html.replace(/\{\{brand\.(\w+)\}\}/g, (_token, key: string) => {
          const value = BRAND_TOKENS[key];
          if (value === undefined) {
            throw new Error(`index.html names {{brand.${key}}}, which src/brand.ts does not give`);
          }
          return escapeAttribute(value);
        }),
    },
  };
}

// Locally, /api is the Python dev server (`python -m dev.api_server`, port 8787). On Vercel the
// same paths are served by the functions in api/. `xfwd` passes the visitor's address on as
// X-Forwarded-For, as Vercel does, so per-visitor features behave the same in both places.
export default defineConfig({
  plugins: [react(), tailwindcss(), brandHtml()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8787", xfwd: true },
    },
  },
});
