import { lazy, Suspense, useEffect, useState } from "react";
import { api, examples, type Box, type PlaceHit, type Variable } from "./api";
import { CaseView } from "./CaseView";
import { PLACES, nameBox, placeName, sameBox } from "./lib";
import { ReportView } from "./ReportView";
import { MethodsView } from "./MethodsView";

const MapView = lazy(() => import("./MapView"));
const Picker = lazy(() => import("./MapView").then((m) => ({ default: m.Picker })));

type Route = "case" | "report" | "map" | "methods";
const ROUTES: { id: Route; label: string }[] = [
  { id: "case", label: "Case" },
  { id: "report", label: "Report card" },
  { id: "map", label: "Map" },
  { id: "methods", label: "How it works" },
];

// URL holds the whole state so any view can be shared: #/case?var=T2M&box=52.6,53.7,-1,0.4
function readHash() {
  const [path, qs] = location.hash.replace(/^#\/?/, "").split("?");
  const p = new URLSearchParams(qs);
  const b = p.get("box")?.split(",").map(Number);
  const box = (b?.length === 4 && b.every(Number.isFinite) ? b : PLACES[0].box) as Box;
  const name = p.get("name") ?? "";
  if (name) nameBox(box, name);
  return { route: (ROUTES.some((r) => r.id === path) ? path : "case") as Route, varId: p.get("var") ?? "T2M", box, name };
}

/** Type-ahead over 34,215 GeoNames places (backend /api/places). Native datalist, no widget library. */
function PlaceSearch({ onPick }: { onPick: (h: PlaceHit) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PlaceHit[]>([]);
  useEffect(() => {
    if (q.trim().length < 2) return;
    const t = setTimeout(() => api.places(q).then((d) => setHits(d.results)).catch(() => setHits([])), 200);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <label className="grow search">
      <span>Search</span>
      <input type="search" list="place-hits" value={q} placeholder="Any city or town…" autoComplete="off"
        onChange={(e) => {
          const v = e.target.value;
          const hit = hits.find((h) => h.label === v);
          if (hit) { onPick(hit); setQ(""); setHits([]); } else setQ(v);
        }} />
      <datalist id="place-hits">
        {hits.map((h) => <option key={h.label} value={h.label}>{h.population.toLocaleString("en-GB")} people</option>)}
      </datalist>
    </label>
  );
}

export default function App() {
  const [s, setS] = useState(readHash);
  const [vars, setVars] = useState<Variable[]>(examples.variables);
  const [picking, setPicking] = useState(false);

  useEffect(() => {
    const on = () => setS(readHash());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  useEffect(() => { api.variables(s.box).then((d) => setVars(d.variables)).catch(() => {}); }, [s.box.join()]);

  const go = (next: Partial<typeof s>) => {
    const n = { ...s, ...next };
    if (next.box && next.name === undefined) n.name = "";
    location.hash = `/${n.route}?var=${n.varId}&box=${n.box.join(",")}${n.name ? `&name=${encodeURIComponent(n.name)}` : ""}`;
    if (next.route) scrollTo({ top: 0 });
  };
  const preset = PLACES.findIndex((p) => sameBox(p.box, s.box));

  return (
    <>
      <a className="skip" href="#content">Skip to content</a>
      <header className="shell">
        <div className="shell-row">
          <a className="brand" href="#/case">
            <svg viewBox="0 0 32 32" aria-hidden><path d="M5 23 L12 18 L17 20 L27 8" /></svg>
            Earth System Trend Detective
          </a>
          <nav aria-label="Views">
            {ROUTES.map((r) => (
              <a key={r.id} href={`#/${r.id}?var=${s.varId}&box=${s.box.join(",")}${s.name ? `&name=${encodeURIComponent(s.name)}` : ""}`} aria-current={s.route === r.id ? "page" : undefined}>{r.label}</a>
            ))}
          </nav>
        </div>
        <div className="shell-row controls">
          <PlaceSearch onPick={(h) => go({ box: h.box, name: h.label })} />
          <label>
            <span>Demo cases</span>
            <select value={preset} onChange={(e) => { const i = +e.target.value; if (i >= 0) go({ box: PLACES[i].box }); }}>
              {preset < 0 && <option value={-1}>{placeName(s.box)}{s.name ? "" : " (your box)"}</option>}
              {PLACES.map((p, i) => <option key={p.name} value={i}>{p.name}</option>)}
            </select>
          </label>
          <button className="btn ghost" aria-expanded={picking} onClick={() => setPicking(!picking)}>{picking ? "Close map" : "Pick on a map"}</button>
          {s.route !== "report" && (
            <label className="grow">
              <span>Variable</span>
              <select value={s.varId} onChange={(e) => go({ varId: e.target.value })}>
                {vars.map((v) => <option key={v.id} value={v.id}>{v.name} ({v.units}){v.ready === false ? ` · slow here: ${v.wait}` : ""}</option>)}
              </select>
            </label>
          )}
        </div>
        {picking && (
          <Suspense fallback={<div className="picker" />}>
            <Picker box={s.box} onPick={(box) => { setPicking(false); go({ box }); }} />
          </Suspense>
        )}
      </header>
      <div id="content">
        {s.route === "case" && <CaseView varId={s.varId} box={s.box} onReport={() => go({ route: "report" })} />}
        {s.route === "report" && <ReportView box={s.box} onOpen={(varId) => go({ route: "case", varId })} />}
        {s.route === "map" && <Suspense fallback={<main className="page"><p className="status">Loading the map…</p></main>}><MapView varId={s.varId} box={s.box} /></Suspense>}
        {s.route === "methods" && <MethodsView />}
      </div>
      <footer className="foot">
        <p>NASA Space Apps Challenge 2026 · Lincoln · Akshita &amp; Kanishk</p>
        <p>Data: NASA POWER (MERRA-2, CERES / GEWEX SRB); NASA MODIS via Microsoft Planetary Computer; NASA GPM IMERG and GPCP (GES DISC); NASA GISTEMP v4; NASA EONET; Met Office HadCET (Open Government Licence); ESA CCI Soil Moisture; ERA5 and CMIP6 models served by Open-Meteo (CC BY 4.0), containing modified Copernicus Climate Change Service information; NOAA NCEI GHCN stations and NOAA PSL / CPC climate indices. Places: GeoNames (CC BY 4.0). Map tiles: Esri.</p>
        <p>Code drafted with help from Claude (Anthropic); every verdict number is computed by our statistics code, never by AI.</p>
      </footer>
    </>
  );
}
