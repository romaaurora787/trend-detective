import { lazy, Suspense, useEffect, useState } from "react";
import { api, examples, type Box, type PlaceHit, type Variable } from "./api";
import { CaseView } from "./CaseView";
import { PLACES, nameBox, placeName, sameBox } from "./lib";
import { ReportView } from "./ReportView";
import { MethodsView } from "./MethodsView";
import { CompareView } from "./CompareView";
import { Guide, guideSeen } from "./Guide";

const MapView = lazy(() => import("./MapView"));
const WorldView = lazy(() => import("./WorldView"));
const Picker = lazy(() => import("./MapView").then((m) => ({ default: m.Picker })));

type Route = "case" | "world" | "report" | "map" | "compare" | "methods";
const ROUTES: { id: Route; label: string }[] = [
  { id: "case", label: "Case" },
  { id: "report", label: "Report card" },
  { id: "map", label: "Map" },
  { id: "world", label: "World" },
  { id: "compare", label: "Compare" },
  { id: "methods", label: "How it works" },
];
// The judge's path: one case → everything in that place → its map → the world → the method → a harder case.
const NEXT: Partial<Record<Route, [Route, (place: string) => string, string?]>> = {
  report: ["map", (p) => `Map the trend across ${p}: which grid cells hold up`],
  map: ["world", () => "Zoom out: the whole world on trial"],
  world: ["compare", () => "Compare two places: is the gap itself real?"],
  compare: ["methods", () => "How the Detective works, and why you can trust it"],
  methods: ["case", () => "Try a harder case: Delhi, where the witnesses disagree", "#/case?var=T2M&box=28,29.5,76.5,78&name=Delhi"],
};

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

type Detail = "plain" | "full";
function useDetail() {
  const [d, setD] = useState<Detail>(() => { try { return localStorage.getItem("td-detail") === "full" ? "full" : "plain"; } catch { return "plain"; } });
  useEffect(() => { document.documentElement.dataset.detail = d; try { localStorage.setItem("td-detail", d); } catch { /* private mode */ } }, [d]);
  return [d, setD] as const;
}

export default function App() {
  const [detail, setDetail] = useDetail();
  const [s, setS] = useState(readHash);
  const [vars, setVars] = useState<Variable[]>(examples.variables);
  const [picking, setPicking] = useState(false);
  const [guide, setGuide] = useState(() => !guideSeen());

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
            <span className="tag">[NASA SPACE APPS 2026]</span>
            Trend Detective
          </a>
          <nav aria-label="Views">
            {ROUTES.map((r) => (
              <a key={r.id} href={`#/${r.id}?var=${s.varId}&box=${s.box.join(",")}${s.name ? `&name=${encodeURIComponent(s.name)}` : ""}`} aria-current={s.route === r.id ? "page" : undefined}>{r.label}</a>
            ))}
          </nav>
          <button className="btn ghost guide-open" aria-expanded={guide} onClick={() => setGuide(!guide)}>Guide</button>
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
          <div className="detail-switch" role="group" aria-label="How much detail">
            <span>Detail</span>
            <div>
              <button aria-pressed={detail === "plain"} onClick={() => setDetail("plain")}>Plain</button>
              <button aria-pressed={detail === "full"} onClick={() => setDetail("full")}>Detailed</button>
            </div>
          </div>
          <button className="btn ghost" aria-expanded={picking} onClick={() => setPicking(!picking)}>{picking ? "Close map" : "Pick on a map"}</button>
          {s.route !== "report" && s.route !== "world" && s.route !== "compare" && (
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
        {guide && <Guide onClose={() => setGuide(false)} />}
        {s.route === "case" && <CaseView varId={s.varId} box={s.box} onReport={() => go({ route: "report" })} />}
        {s.route === "report" && <ReportView box={s.box} onOpen={(varId) => go({ route: "case", varId })} />}
        {s.route === "map" && <Suspense fallback={<main className="sheet"><p className="status pad">Loading the map…</p></main>}><MapView varId={s.varId} box={s.box} /></Suspense>}
        {s.route === "world" && <Suspense fallback={<main className="sheet"><p className="status pad">Loading the globe…</p></main>}><WorldView /></Suspense>}
        {s.route === "compare" && <CompareView vars={vars} />}
        {s.route === "methods" && <MethodsView />}
        {NEXT[s.route] && (() => {
          const [to, text, href] = NEXT[s.route]!;
          return (
            <div className="sheet next">
              <a className="cue wide" href={href ?? `#/${to}?var=${s.varId}&box=${s.box.join(",")}${s.name ? `&name=${encodeURIComponent(s.name)}` : ""}`} onClick={() => scrollTo({ top: 0 })}>
                <span className="tag">[NEXT]</span>{text(placeName(s.box))} <span aria-hidden>→</span>
              </a>
            </div>
          );
        })()}
      </div>
      <footer className="foot">
        <p className="tag">[CREDITS] NASA Space Apps Challenge 2026 · Lincoln · Akshita &amp; Kanishk</p>
        <p>Data: NASA POWER (MERRA-2, CERES / GEWEX SRB); NASA MODIS via Microsoft Planetary Computer; NASA GPM IMERG and GPCP (GES DISC); NASA GISTEMP v4; NASA MERRA-2 monthly means (GES DISC, for the globe); NASA GLDAS-2.1 Noah; NASA GRACE / GRACE-FO JPL mascons; NASA EONET; Met Office HadCET (Open Government Licence); ESA CCI Soil Moisture; ERA5 and CMIP6 models served by Open-Meteo (CC BY 4.0), containing modified Copernicus Climate Change Service information; NOAA NCEI GHCN stations and NOAA PSL / CPC climate indices. Places: GeoNames (CC BY 4.0). Map tiles: Esri. Country outlines: Natural Earth (public domain).</p>
        <p>Code drafted with help from Claude (Anthropic); every verdict number is computed by our statistics code, never by AI.</p>
      </footer>
    </>
  );
}
