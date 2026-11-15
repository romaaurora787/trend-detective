import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import "./styles.css";
import App from "./App";

declare const __BUILD__: string;

// Stale-page guard: tailscale serve sends no Cache-Control, so a browser may keep an old index.html.
// If version.json (fetched uncached) names a newer build, load a fresh URL once (?v= busts the cache).
function checkBuild() {
  fetch(`version.json?t=${Date.now()}`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .then((d: { build?: string } | null) => {
      if (!d?.build || d.build === __BUILD__) return;
      if (new URLSearchParams(location.search).get("v") === d.build) return; // already tried: never loop
      location.replace(`${location.pathname}?v=${d.build}${location.hash}`);
    })
    .catch(() => {});
}
checkBuild();
document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && checkBuild());

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
