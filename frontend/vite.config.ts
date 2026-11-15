import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build id: baked into the bundle and written to version.json, so a page served from a stale
// browser cache can notice a newer deploy and reload itself (kaakserver can't send Cache-Control).
const BUILD = String(Date.now());

export default defineConfig({
  plugins: [react(), { name: "version-json", generateBundle() { this.emitFile({ type: "asset", fileName: "version.json", source: JSON.stringify({ build: BUILD }) }); } }],
  define: { __BUILD__: JSON.stringify(BUILD) },
});
