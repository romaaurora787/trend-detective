import { lazy, Suspense, useEffect, useState } from "react";
import { api, examples, type Box, type Variable } from "./api";
import { CaseView } from "./CaseView";
import { PLACES, placeName, sameBox } from "./lib";
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
  const box = p.get("box")?.split(",").map(Number);
  return {
    route: (ROUTES.some((r) => r.id === path) ? path : "case") as Route,
    varId: p.get("var") ?? "T2M",
    box: (box?.length === 4 && box.every(Number.isFinite) ? box : PLACES[0].box) as Box,
  };
}

export default function App() {
  const [s, setS] = useState(readHash);
  const [vars, setVars] = useState<Variable[]>(examples.variables);
  const [picking, setPicking] = useState(false);

  useEffect(() => {
    const on = () => setS(readHash());
    addEventListener("hashchange", on);
    api.variables().then((d) => setVars(d.variables)).catch(() => {});
    return () => removeEventListener("hashchange", on);
  }, []);

  const go = (next: Partial<typeof s>) => {
    const n = { ...s, ...next };
    location.hash = `/${n.route}?var=${n.varId}&box=${n.box.join(",")}`;
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
              <a key={r.id} href={`#/${r.id}?var=${s.varId}&box=${s.box.join(",")}`} aria-current={s.route === r.id ? "page" : undefined}>{r.label}</a>
            ))}
          </nav>
        </div>
        <div className="shell-row controls">
          <label>
            <span>Place</span>
            <select value={preset} onChange={(e) => { const i = +e.target.value; if (i >= 0) go({ box: PLACES[i].box }); }}>
              {preset < 0 && <option value={-1}>{placeName(s.box)} (your box)</option>}
              {PLACES.map((p, i) => <option key={p.name} value={i}>{p.name}</option>)}
            </select>
          </label>
          <button className="btn ghost" aria-expanded={picking} onClick={() => setPicking(!picking)}>{picking ? "Close map" : "Pick on a map"}</button>
          {s.route !== "report" && (
            <label className="grow">
              <span>Variable</span>
              <select value={s.varId} onChange={(e) => go({ varId: e.target.value })}>
                {vars.map((v) => <option key={v.id} value={v.id}>{v.name} ({v.units})</option>)}
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
        <p>Data: NASA POWER (MERRA-2, CERES), Met Office HadCET, NASA GPCP, ESA CCI Soil Moisture. Code drafted with help from Claude (Anthropic); every verdict number is computed by our statistics code, never by AI.</p>
      </footer>
    </>
  );
}
