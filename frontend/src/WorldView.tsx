// "The world on trial": a see-through globe of 111 places, re-coloured by each test in turn.
// AI-use note: drafted with Claude (Anthropic) during the hackathon.
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { geoArea, geoBounds, geoCentroid, geoContains, geoDistance, geoGraticule10, geoOrthographic, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { feature, mesh } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import countries from "world-atlas/countries-110m.json";
import exWorld from "../../docs/examples/world.json";
import { api, examples, type Label } from "./api";
import { Reveal, still, useInView, useSize, useTween } from "./Chart";
import { LABELS, dirTone, short, signed } from "./lib";
import { Trust } from "./Trust";

type Cell = { label: Label; slope: number; alibi: string | null; typical: boolean } | null;
export interface WorldVar {
  id: string; name: string; units: string; n_points: number; n_proven: number; n_rising: number; n_falling: number;
  n_typical: number; n_fooled: number; alibi: Record<string, number>; cells: Cell[];
}
export interface World { n_points: number; points: { lat: number; lon: number }[]; variables: WorldVar[] }
type Mode = "typical" | "detective" | "satellite";

const proven = (c: Cell) => !!c && (c.label === "strong" || c.label === "some");
const FEATURED = ["T2M", "PRECTOTCORR", "CLOUD_AMT", "GWETROOT", "AOD_55", "SNODP"];
const topo = countries as unknown as Topology<{ countries: GeometryCollection }>;
const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// Country outlines, also used to name the place a spike sits in.
const LAND = feature(topo, topo.objects.countries) as unknown as { features: { properties: { name: string }; geometry: GeoPermissibleObjects }[] };
const BYNAME = new Map(LAND.features.map((f) => [f.properties.name, f]));
/** A country's biggest piece, so France zooms to France, not to France + French Guiana. */
function mainland(name: string): GeoPermissibleObjects | null {
  const g = BYNAME.get(name)?.geometry as unknown as { type: string; coordinates: unknown[] } | undefined;
  if (!g) return null;
  if (g.type !== "MultiPolygon") return g as unknown as GeoPermissibleObjects;
  const parts = g.coordinates.map((c) => ({ type: "Polygon", coordinates: c }) as unknown as GeoPermissibleObjects);
  return parts.reduce((a, b) => (geoArea(b) > geoArea(a) ? b : a));
}

/**
 * The globe: drawn on a 2D canvas with an orthographic projection, so it needs no WebGL.
 * The far side shows faintly through the glass; each place is a spike whose height is the size of its trend.
 * ponytail: d3-geo + canvas, not three.js; 111 spikes don't need a 3D engine.
 */
function Globe({ v, points, mode, sel, focus, picked, onPick }: { v: WorldVar; points: World["points"]; mode: Mode; sel: number | null; focus: string | null; picked: string[]; onPick: (i: number | null, country: string | null) => void }) {
  const [box, w, h] = useSize<HTMLDivElement>();
  const cv = useRef<HTMLCanvasElement>(null);
  const live = useRef({ v, mode, sel, focus, picked });
  live.current = { v, mode, sel, focus, picked };
  const s = useRef({ rot: [-10, -22] as [number, number], drag: null as null | { x: number; y: number; r: [number, number]; moved: boolean }, last: 0, cur: new Float32Array(points.length), tips: new Float32Array(points.length * 2), hover: -1, zoom: 1, goal: null as null | { rot: [number, number]; zoom: number } });
  const borders = useMemo(() => mesh(topo, topo.objects.countries), []);
  const land = LAND as unknown as GeoPermissibleObjects;
  const grat = useMemo(() => geoGraticule10(), []);

  // Fly to the chosen country (or back out to the whole globe).
  useEffect(() => {
    const m = focus ? mainland(focus) : null;
    if (!m) { s.current.goal = { rot: [...s.current.rot] as [number, number], zoom: 1 }; return; }
    const [lon, lat] = geoCentroid(m);
    const [[x0, y0], [x1, y1]] = geoBounds(m);
    const ext = Math.max(((x1 - x0 + 360) % 360) * Math.cos((lat * Math.PI) / 180), y1 - y0, 3);
    s.current.goal = { rot: [-lon, -lat], zoom: Math.max(1, Math.min(4, 55 / ext)) };
  }, [focus]);

  useEffect(() => {
    const c = cv.current;
    if (!c || !w || !h) return;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    c.width = w * dpr; c.height = h * dpr;
    const ctx = c.getContext("2d")!;
    const col = { ink: css("--ink"), ink3: css("--ink-3"), rule: css("--rule"), rule2: css("--rule-2"), paper: css("--paper-3"), paper2: css("--paper-2"), rise: css("--signal"), fall: css("--fall") };
    const R = Math.min(w, h) / 2 / 1.22, cx = w / 2, cy = h / 2 - R * 0.04;
    const front = geoOrthographic().scale(R).translate([cx, cy]).clipAngle(90).precision(0.6);
    const back = geoOrthographic().scale(R).translate([cx, cy]).clipAngle(90).reflectX(true).precision(0.6);
    const pf = geoPath(front, ctx), pb = geoPath(back, ctx);
    let raf = 0;
    const calm = still();

    const frame = (t: number) => {
      const st = s.current, { v, mode, sel, focus, picked } = live.current;
      const go = st.goal;
      if (go && !st.drag) {
        const k = calm ? 1 : 0.07, d = ((go.rot[0] - st.rot[0] + 540) % 360) - 180;
        st.rot = [st.rot[0] + d * k, st.rot[1] + (go.rot[1] - st.rot[1]) * k];
        st.zoom += (go.zoom - st.zoom) * k;
        if (Math.abs(d) < 0.05 && Math.abs(go.zoom - st.zoom) < 0.002) st.goal = null;
      } else if (!st.drag && !calm && sel == null && !focus && t - st.last > 2500) st.rot[0] += 0.06;
      front.scale(R * st.zoom); back.scale(R * st.zoom);
      front.rotate([st.rot[0], st.rot[1]]);
      back.rotate([st.rot[0] + 180, -st.rot[1]]);
      const centre: [number, number] = [-st.rot[0], -st.rot[1]];
      const mags = v.cells.map((c) => (c ? Math.abs(c.slope) : 0)).sort((a, b) => a - b);
      const top = mags[Math.floor(mags.length * 0.95)] || 1;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      // A soft shadow under the globe, for depth.
      const sh = ctx.createRadialGradient(cx, cy + R * 1.12, 0, cx, cy + R * 1.12, R * 0.9);
      sh.addColorStop(0, "rgba(40,40,90,0.16)"); sh.addColorStop(1, "rgba(40,40,90,0)");
      ctx.save(); ctx.globalAlpha = Math.max(0, 1.5 - st.zoom); ctx.translate(0, (cy + R * 1.12) * (1 - 0.18)); ctx.scale(1, 0.18); ctx.fillStyle = sh; ctx.beginPath(); ctx.arc(cx, cy + R * 1.12, R * 0.9, 0, 7); ctx.fill(); ctx.restore();
      // Far side, seen through the glass.
      ctx.beginPath(); pb(borders); ctx.strokeStyle = col.rule2; ctx.lineWidth = 0.6; ctx.stroke();
      // The glass: a soft lit sphere.
      const g = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.1, cx, cy, R);
      g.addColorStop(0, "rgba(255,255,255,0.55)"); g.addColorStop(1, "rgba(255,255,255,0.05)");
      ctx.beginPath(); pf({ type: "Sphere" }); ctx.fillStyle = g; ctx.fill();
      ctx.lineWidth = 1.2; ctx.strokeStyle = col.ink; ctx.stroke();
      ctx.beginPath(); pf(grat); ctx.strokeStyle = col.rule2; ctx.lineWidth = 0.5; ctx.stroke();
      ctx.beginPath(); pf(land); ctx.fillStyle = col.paper2; ctx.globalAlpha = 0.75; ctx.fill(); ctx.globalAlpha = 1;
      ctx.beginPath(); pf(borders); ctx.strokeStyle = col.ink; ctx.globalAlpha = 0.55; ctx.lineWidth = 0.7; ctx.stroke(); ctx.globalAlpha = 1;
      // Chosen countries: the focus in ink, the ones pinned for comparison in red.
      for (const name of new Set([...picked, focus])) {
        const f = name && BYNAME.get(name);
        if (!f) continue;
        const on = name === focus;
        ctx.beginPath(); pf(f.geometry);
        ctx.fillStyle = on ? col.ink : col.rise; ctx.globalAlpha = on ? 0.13 : 0.1; ctx.fill(); ctx.globalAlpha = 1;
        ctx.strokeStyle = on ? col.ink : col.rise; ctx.lineWidth = 1.6; ctx.stroke();
      }

      // Spikes, far ones first.
      const order = points.map((p, i) => ({ i, d: geoDistance([p.lon, p.lat], centre) })).sort((a, b) => b.d - a.d);
      for (const { i, d } of order) {
        const c = v.cells[i];
        const lit = !c ? 0 : mode === "typical" ? +c.typical : +proven(c);
        st.cur[i] += (lit - st.cur[i]) * (calm ? 1 : 0.08);
        const k = st.cur[i];
        const p = [points[i].lon, points[i].lat] as [number, number];
        const onFront = d < Math.PI / 2;
        const xy = (onFront ? front : back)(p);
        if (!xy || !c) continue;
        const hgt = (0.02 + k * Math.min(Math.abs(c.slope) / top, 1) * 0.18) / Math.sqrt(st.zoom);
        const tx = cx + (xy[0] - cx) * (1 + (onFront ? hgt : 0)), ty = cy + (xy[1] - cy) * (1 + (onFront ? hgt : 0));
        if (onFront) { st.tips[2 * i] = tx; st.tips[2 * i + 1] = ty; }
        const hue = dirTone(v.id, c.slope) === "rise" ? col.rise : col.fall;
        ctx.globalAlpha = onFront ? 0.25 + 0.75 * k : 0.12 * k;
        ctx.strokeStyle = k > 0.5 ? hue : col.ink3;
        ctx.lineWidth = 2.2;
        ctx.beginPath(); ctx.moveTo(xy[0], xy[1]); ctx.lineTo(tx, ty); ctx.stroke();
        ctx.fillStyle = k > 0.5 ? hue : col.ink3;
        ctx.beginPath(); ctx.arc(tx, ty, onFront ? 2 + 2.2 * k : 1.6, 0, 7); ctx.fill();
        ctx.globalAlpha = 1;
        if (onFront && mode === "satellite" && proven(c) && c.alibi === "could_be_instrument") {
          const r = 7 + 4 * (calm ? 0.5 : (Math.sin(t / 280 + i) + 1) / 2);
          ctx.beginPath(); ctx.arc(xy[0], xy[1], r, 0, 7); ctx.strokeStyle = col.rise; ctx.lineWidth = 2; ctx.stroke();
        }
        if (onFront && (i === sel || i === st.hover)) {
          ctx.beginPath(); ctx.arc(tx, ty, 9, 0, 7); ctx.strokeStyle = col.ink; ctx.lineWidth = i === sel ? 2.5 : 1.2; ctx.stroke();
        }
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    // Drag to turn; tap a spike to open its card.
    const pick = (x: number, y: number) => {
      const centre: [number, number] = [-s.current.rot[0], -s.current.rot[1]];
      let best = -1, bd = 14;
      points.forEach((p, i) => {
        if (geoDistance([p.lon, p.lat], centre) >= Math.PI / 2) return;
        const xy = front([p.lon, p.lat]);
        if (!xy) return;
        const t = s.current.tips;
        const dd = Math.min(Math.hypot(xy[0] - x, xy[1] - y), Math.hypot(t[2 * i] - x, t[2 * i + 1] - y));
        if (dd < bd) { bd = dd; best = i; }
      });
      return best;
    };
    const at = (e: PointerEvent) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    const down = (e: PointerEvent) => { s.current.goal = null; s.current.drag = { x: e.clientX, y: e.clientY, r: [...s.current.rot] as [number, number], moved: false }; s.current.last = performance.now(); };
    const move = (e: PointerEvent) => {
      const d = s.current.drag;
      if (d) {
        const dx = e.clientX - d.x, dy = e.clientY - d.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) { d.moved = true; c.setPointerCapture(e.pointerId); }
        const sp = 90 / (R * s.current.zoom);
        s.current.rot = [d.r[0] + dx * sp, Math.max(-75, Math.min(75, d.r[1] - dy * sp))];
        s.current.last = performance.now();
      } else {
        const [x, y] = at(e);
        s.current.hover = pick(x, y);
        c.style.cursor = s.current.hover >= 0 ? "pointer" : "grab";
      }
    };
    const up = (e: PointerEvent) => {
      const d = s.current.drag;
      s.current.drag = null;
      if (d && !d.moved) {
        const [x, y] = at(e), i = pick(x, y);
        const ll = i >= 0 ? [points[i].lon, points[i].lat] as [number, number] : Math.hypot(x - cx, y - cy) <= R * s.current.zoom ? front.invert!([x, y]) : null;
        const hit = ll && LAND.features.find((f) => geoContainsSafe(f.geometry, ll));
        onPick(i >= 0 ? i : null, hit ? hit.properties.name : null);
      }
    };
    c.addEventListener("pointerdown", down); c.addEventListener("pointermove", move); addEventListener("pointerup", up);
    return () => { cancelAnimationFrame(raf); c.removeEventListener("pointerdown", down); c.removeEventListener("pointermove", move); removeEventListener("pointerup", up); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [w, h]);

  return (
    <div ref={box} className="globe">
      <canvas ref={cv} style={{ width: w, height: h }} role="img"
        aria-label={`Globe of ${points.length} places for ${v.name}. ${mode === "typical" ? `${v.n_typical} look like change to a typical analysis` : `${v.n_proven} proven after our checks`}.`} />
    </div>
  );
}

function placeOf(p: { lat: number; lon: number }) {
  const hit = LAND.features.find((f) => geoContainsSafe(f.geometry, [p.lon, p.lat]));
  return hit?.properties.name ?? "Open ocean / coast";
}
const geoContainsSafe = (g: GeoPermissibleObjects, p: [number, number]) => { try { return geoContains(g, p); } catch { return false; } };
const ll = (p: { lat: number; lon: number }) => `${Math.abs(p.lat).toFixed(0)}°${p.lat >= 0 ? "N" : "S"}, ${Math.abs(p.lon).toFixed(0)}°${p.lon >= 0 ? "E" : "W"}`;

/** The places we tested inside a country; if none sit inside it, the nearest one. */
function placesIn(world: World, name: string, where: string[]) {
  const idx = where.flatMap((c, i) => (c === name ? [i] : []));
  if (idx.length) return { idx, km: 0 };
  const m = mainland(name);
  if (!m) return { idx: [] as number[], km: 0 };
  const c = geoCentroid(m);
  let best = 0, bd = Infinity;
  world.points.forEach((p, i) => { const d = geoDistance([p.lon, p.lat], c); if (d < bd) { bd = d; best = i; } });
  return { idx: [best], km: Math.round((bd * 6371) / 10) * 10 };
}

// The record ends in 2025: 2.5 decades to 2050.
const TO_2050 = 2.5;

/** One variable at a set of places: how many proven, the average proven trend, how many fooled the typical test. */
function sum(v: WorldVar, idx: number[]) {
  const cs = idx.map((i) => v.cells[i]).filter((c): c is NonNullable<Cell> => !!c);
  const pr = cs.filter(proven);
  // ponytail: plain mean of the proven slopes; mixed directions inside one country just average out.
  const slope = pr.length ? pr.reduce((a, c) => a + c.slope, 0) / pr.length : null;
  return { n: cs.length, p: pr.length, slope, fooled: cs.filter((c) => c.typical && !proven(c)).length, sat: pr.filter((c) => c.alibi === "could_be_instrument").length };
}

function CountryTable({ world, cols, where, varId, onVar, onDrop }: { world: World; cols: string[]; where: string[]; varId: string; onVar: (id: string) => void; onDrop: (c: string) => void }) {
  const at = cols.map((c) => ({ name: c, ...placesIn(world, c, where) }));
  const vars = [...FEATURED.map((id) => world.variables.find((x) => x.id === id)).filter((x): x is WorldVar => !!x), ...world.variables.filter((x) => !FEATURED.includes(x.id))];
  return (
    <section className="frame sec" id="country">
      <h2 className="sec-title"><span className="tag">[{cols.length > 1 ? "COMPARE" : "COUNTRY"}]</span>{cols.join(" vs ")}</h2>
      <p className="sec-lede">
        Every variable we tested, at the places inside {cols.length > 1 ? "each country" : cols[0]}. A trend counts only if it is proven after our checks.
        "By 2050" draws today's proven trend straight on: a what-if, not a climate-model forecast.
      </p>
      <div className="ctable-scroll">
        <table className="ctable">
          <thead>
            <tr>
              <th scope="col">Variable</th>
              {at.map((c, j) => (
                <th key={c.name} scope="col">
                  <span className="cname">{c.name}</span>
                  <span className="tag">{c.km ? `no place inside; nearest ${c.km.toLocaleString("en-GB")} km away` : `${c.idx.length} place${c.idx.length === 1 ? "" : "s"} tested`}</span>
                  {j > 0 && <button className="linkish" onClick={() => onDrop(c.name)}>Remove {c.name}</button>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vars.map((v) => {
              const u = short(v.units);
              return (
                <tr key={v.id} className={v.id === varId ? "on" : undefined}>
                  <th scope="row"><button className="linkish" onClick={() => onVar(v.id)}>{v.name}</button></th>
                  {at.map((c) => {
                    const r = sum(v, c.idx);
                    if (!r.n) return <td key={c.name} className="muted">no data</td>;
                    if (r.slope == null) return (
                      <td key={c.name}>
                        <span className="cno">No proven change</span>
                        {r.fooled > 0 && <span className="chip warn">typical test says change</span>}
                      </td>
                    );
                    return (
                      <td key={c.name}>
                        <span className={`cval t-${dirTone(v.id, r.slope)}`}><b>{signed(r.slope)}</b> {u}/decade</span>
                        <span className="tag">proven at {r.p} of {r.n}{r.sat ? ` · ${r.sat} could be the satellite` : ""}</span>
                        <span className="c2050">If it keeps going, by 2050: {signed(r.slope * TO_2050)} {u} on today</span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Big({ to, of, label, pct }: { to: number; of?: number; label: string; pct?: boolean }) {
  const [ref, seen] = useInView<HTMLDivElement>();
  const n = useTween(seen ? to : 0, 1300);
  return (
    <div ref={ref} className="fig">
      <b>{Math.round(n).toLocaleString("en-GB")}{pct ? "%" : ""}{of != null && <small>/{of}</small>}</b>
      <p>{label}</p>
    </div>
  );
}

export default function WorldView() {
  const [world, setWorld] = useState<World>(exWorld as unknown as World);
  const [varId, setVarId] = useState("CLOUD_AMT");
  const [mode, setMode] = useState<Mode>("typical");
  const [sel, setSel] = useState<number | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { api.world<World>().then((d) => d.variables && setWorld(d)).catch(() => {}); }, []);
  useEffect(() => {
    if (!playing) return;
    const order: Mode[] = ["typical", "detective", "satellite"];
    const t = setInterval(() => setMode((m) => { const n = order[(order.indexOf(m) + 1) % 3]; if (n === "typical") setPlaying(false); return n; }), 2600);
    return () => clearInterval(t);
  }, [playing]);

  const v = world.variables.find((x) => x.id === varId) ?? world.variables[0];
  const where = useMemo(() => world.points.map(placeOf), [world.points]);
  const cols = [...new Set([focus, ...picked].filter((c): c is string => !!c))];
  const here = focus ? placesIn(world, focus, where) : null;
  const fs = here ? sum(v, here.idx) : null;
  const tot = world.variables.reduce((a, x) => ({ n: a.n + x.n_points, t: a.t + x.n_typical, p: a.p + x.n_proven, f: a.f + x.n_fooled }), { n: 0, t: 0, p: 0, f: 0 });
  const cloud = world.variables.find((x) => x.id === "CLOUD_AMT");
  const fa = examples.validation.validation;
  const i5 = fa.phis.indexOf(0.5);
  const sat = v.alibi.could_be_instrument ?? 0;
  const hasSwitch = Object.keys(v.alibi).some((k) => k !== "no_known_change" && k !== "untested");
  const counts = { typical: v.n_typical, detective: v.n_proven, satellite: sat };
  const shown = useTween(counts[mode], 800);
  const cell = sel != null ? v.cells[sel] : null;
  const pt = sel != null ? world.points[sel] : null;
  const u = short(v.units);
  const rows = [...world.variables].sort((a, b) => b.n_fooled / b.n_points - a.n_fooled / a.n_points);

  const steps: { m: Mode; no: string; title: string; n: number; of: number; text: string }[] = [
    { m: "typical", no: "01", title: "A typical analysis", n: v.n_typical, of: v.n_points, text: "Each place tested on its own with a straight line that treats every month as independent. That's how most trend maps are made." },
    { m: "detective", no: "02", title: "The Detective", n: v.n_proven, of: v.n_points, text: "Both corrected tests must agree, with neighbouring months' stickiness counted. The rest fade to grey." },
    { m: "satellite", no: "03", title: "The satellite check", n: sat, of: v.n_proven, text: hasSwitch ? "Did the instrument change, not the climate? Red rings: one jump at a documented satellite or model switch explains the trend better." : "No documented satellite or model switch inside this record, so nothing to explain away." },
  ];

  return (
    <main className="sheet worldv">
      <section className="frame hero hero-sm">
        <div className="bar-top">
          <span className="tag">[THE WORLD ON TRIAL] {world.n_points} places · {world.variables.length} NASA variables · {tot.n.toLocaleString("en-GB")} checks</span>
          <span className="tag">[1981–2025] NASA POWER · MERRA-2</span>
        </div>
        <h1 className="hero-line">A typical analysis calls {Math.round((tot.t / tot.n) * 100)}% of these trends real. <span className="hl">After our checks, {Math.round((tot.p / tot.n) * 100)}% hold up.</span></h1>
      </section>

      <Reveal className="frame figs">
        <Big to={tot.n} label="trend checks: every variable at every place" />
        <Big to={tot.f} label="trends a typical analysis calls real that don't hold up" />
        {cloud && <Big to={cloud.alibi.could_be_instrument ?? 0} of={cloud.n_proven} label="proven cloud-cover trends that could be the 2001 satellite switch" />}
        <Big to={Math.round(fa.false_alarm_rate.ours_verdict[i5] * 100)} pct label={`our false-alarm rate on realistic noise; a typical test: ${Math.round(fa.false_alarm_rate.naive_ols_anomalies[i5] * 100)}%`} />
      </Reveal>

      <section className={`frame globe-sheet m-${mode}`}>
        <div className="globe-col">
          <div className="chips" role="radiogroup" aria-label="Variable">
            {FEATURED.map((id) => world.variables.find((x) => x.id === id)).filter(Boolean).map((x) => (
              <button key={x!.id} role="radio" aria-checked={x!.id === v.id} onClick={() => { setVarId(x!.id); setSel(null); }}>{x!.name}</button>
            ))}
            <select aria-label="More variables" value={FEATURED.includes(v.id) ? "" : v.id} onChange={(e) => { if (e.target.value) { setVarId(e.target.value); setSel(null); } }}>
              <option value="">More…</option>
              {world.variables.filter((x) => !FEATURED.includes(x.id)).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </div>
          <Globe v={v} points={world.points} mode={mode} sel={sel} focus={focus} picked={picked} onPick={(i, c) => { setSel(i); if (c) setFocus(c); }} />
          <div className="globe-foot">
            <span className="tag">[DRAG TO TURN · TAP A COUNTRY OR A SPIKE]</span>
            <span className="legend-row">
              <span><i className={`k-dot t-${dirTone(v.id, 1)}`} />rising</span>
              <span><i className={`k-dot t-${dirTone(v.id, -1)}`} />falling</span>
              <span><i className="k-dot k-grey" />not counted</span>
              {mode === "satellite" && <span><i className="k-ring" />could be the satellite</span>}
              <span className="muted">spike height = size of the trend</span>
            </span>
          </div>
        </div>

        <aside className="globe-side">
          <p className="map-n"><b>{Math.round(shown)}</b><small>/{mode === "satellite" ? v.n_proven : v.n_points}</small></p>
          <p className="tag">{v.name} · {mode === "typical" ? "places that look like change" : mode === "detective" ? "places with proven change" : "proven trends that could be the instrument"}</p>
          {focus && fs && here && (
            <div className="inspect country" aria-live="polite">
              <p className="tag">[COUNTRY] {focus} · {here.km ? `nearest place ${here.km.toLocaleString("en-GB")} km away` : `${here.idx.length} place${here.idx.length === 1 ? "" : "s"}`}</p>
              <p className="cline">
                {fs.slope == null
                  ? <>{v.name}: <b>no proven change</b>{fs.fooled ? `, though a typical test says there is at ${fs.fooled} of ${fs.n}` : ""}.</>
                  : <>{v.name}: <b className={`t-${dirTone(v.id, fs.slope)}`}>{signed(fs.slope)} {u}</b> per decade, proven at {fs.p} of {fs.n}. If it keeps going, by 2050: <b>{signed(fs.slope * TO_2050)} {u}</b> on today.</>}
              </p>
              <div className="cbtns">
                <button className="btn" onClick={() => document.getElementById("country")?.scrollIntoView({ behavior: "smooth" })}>Every variable here ↓</button>
                {!picked.includes(focus) && picked.length < 3 && <button className="btn ghost" onClick={() => setPicked([...picked, focus])}>+ Compare</button>}
                <button className="btn ghost" onClick={() => { setFocus(null); setSel(null); }}>Zoom out</button>
              </div>
              {picked.length > 0 && <p className="note">Pinned: {picked.join(", ")}. Tap another country to compare.</p>}
            </div>
          )}

          <ol className="gsteps">
            {steps.map((st) => (
              <li key={st.m}>
                <button className={mode === st.m ? "on" : undefined} aria-pressed={mode === st.m} onClick={() => { setMode(st.m); setPlaying(false); }}>
                  <span className="tag">[{st.no}] {st.title}</span>
                  <span className="gnum"><b>{st.n}</b> of {st.of}</span>
                  <span className="gbar" aria-hidden><i style={{ width: `${(st.n / Math.max(st.of, 1)) * 100}%` }} /></span>
                  <span className="gtext">{st.text}</span>
                </button>
              </li>
            ))}
          </ol>
          <button className="btn ghost" onClick={() => { setMode("typical"); setPlaying(true); }} disabled={playing}>{playing ? "Playing…" : "▶ Play the three tests"}</button>

          <div className="inspect" aria-live="polite">
            <p className="tag">[PLACE] {pt ? `${placeOf(pt)} · ${ll(pt)}` : "tap a spike on the globe"}</p>
            {pt && cell && (
              <>
                <dl className="stats">
                  <div><dt>Verdict</dt><dd><span className={`verdict v-${cell.label}`}><span className="verdict-swatch" aria-hidden />{LABELS[cell.label]}</span></dd></div>
                  <div><dt>Trend</dt><dd><b>{signed(cell.slope)}</b> {u} per decade</dd></div>
                  <div><dt>Typical says</dt><dd>{cell.typical ? "real change" : "no trend"}</dd></div>
                  {cell.alibi && cell.alibi !== "no_known_change" && <div><dt>Satellite check</dt><dd className={cell.alibi === "could_be_instrument" ? "hl" : undefined}>{cell.alibi.replace(/_/g, " ")}</dd></div>}
                </dl>
                <a className="btn" href={`#/case?var=${v.id}&box=${pt.lat - 1},${pt.lat + 1},${pt.lon - 1},${pt.lon + 1}&name=${encodeURIComponent(placeOf(pt))}`}>Open the full case →</a>
              </>
            )}
            {pt && !cell && <p className="note">No data for {v.name} here.</p>}
          </div>
        </aside>
      </section>

      {cols.length > 0 && <CountryTable world={world} cols={cols} where={where} varId={v.id}
        onVar={(id) => { setVarId(id); setSel(null); document.querySelector(".globe-sheet")?.scrollIntoView({ behavior: "smooth" }); }}
        onDrop={(c) => setPicked(picked.filter((x) => x !== c))} />}

      <Reveal className="frame sec">
        <h2 className="sec-title"><span className="tag">[02]</span>Where a typical analysis goes wrong</h2>
        <p className="sec-lede">Each row is one NASA variable at {world.n_points} places. Light bar: a typical analysis calls it real. Solid bar: proven after our checks. Sorted by the share of claims that don't hold.</p>
        <ul className="wrows">
          {rows.map((x, i) => {
            const swch = (x.alibi.could_be_instrument ?? 0);
            return (
              <li key={x.id} style={{ "--n": i } as CSSProperties}>
                <button className={x.id === v.id ? "on" : undefined} onClick={() => { setVarId(x.id); setSel(null); document.querySelector(".globe-sheet")?.scrollIntoView({ behavior: "smooth" }); }}>
                  <span className="wname">{x.name}</span>
                  <span className="wbar" aria-label={`${x.n_typical} typical, ${x.n_proven} proven of ${x.n_points}`}>
                    <i className="wt" style={{ width: `${(x.n_typical / x.n_points) * 100}%` }} />
                    <i className="wp" style={{ width: `${(x.n_proven / x.n_points) * 100}%` }} />
                  </span>
                  <span className="wfool"><b>{x.n_fooled}</b> don't hold</span>
                  {swch > 0 && <span className="chip warn">switch: {swch} of {x.n_proven} could be the instrument</span>}
                </button>
              </li>
            );
          })}
        </ul>
      </Reveal>

      <Reveal className="frame sec">
        <h2 className="sec-title"><span className="tag">[03]</span>Why trust the Detective</h2>
        <Trust variables={world.variables} />
      </Reveal>
    </main>
  );
}
