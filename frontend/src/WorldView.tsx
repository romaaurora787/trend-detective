// "The world on trial": a see-through globe of 111 places, re-coloured by each test in turn.
// AI-use note: drafted with Claude (Anthropic) during the hackathon.
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { geoArea, geoBounds, geoCentroid, geoContains, geoDistance, geoGraticule10, geoOrthographic, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { feature, mesh } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import countries from "world-atlas/countries-110m.json";
import exWorld from "../../docs/examples/world.json";
import { api, examples, type Label, type Opposites as Opp } from "./api";
import { Reveal, still, useInView, useSize, useTween } from "./Chart";
import { LABELS, dirTone, short, signed } from "./lib";
import { Trust } from "./Trust";
import { compareHref } from "./CompareView";

type Cell = { label: Label; slope: number; alibi: string | null; typical: boolean } | null;
export interface WorldVar {
  id: string; name: string; units: string; n_points: number; n_proven: number; n_rising: number; n_falling: number;
  n_typical: number; n_fooled: number; alibi: Record<string, number>; cells: Cell[];
}
export interface World { n_points: number; points: { lat: number; lon: number }[]; variables: WorldVar[] }
type Mode = "typical" | "detective" | "satellite" | "luck";

// The dense layer: every 2° land square from NASA MERRA-2 (Akshita's /api/globe), rows [lat, lon, slope, flags].
type GridRow = [number, number, number, string];
interface Grid { variable: string; cells: GridRow[]; counts: { land: { cells: number; typical: number; proven: number; luck_typical: number; luck_ours: number } } }
const GRID_VARS = ["T2M", "PRECTOTCORR"];
const RAD = Math.PI / 180;
const gProven = (f: string) => f.includes("S") || f.includes("s");
const G_LABEL: Record<string, Label> = { S: "strong", s: "some", m: "mixed", n: "none" };

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
function Globe({ v, points, mode, sel, focus, picked, grid, gsel, onPick }: { v: WorldVar; points: World["points"]; mode: Mode; sel: number | null; focus: string | null; picked: string[]; grid?: Grid; gsel: number | null; onPick: (i: number | null, country: string | null, g: number | null) => void }) {
  const [box, w, h] = useSize<HTMLDivElement>();
  const cv = useRef<HTMLCanvasElement>(null);
  const live = useRef({ v, mode, sel, focus, picked, grid, gsel, onPick });
  live.current = { v, mode, sel, focus, picked, grid, gsel, onPick };
  const s = useRef({ rot: [-10, -22] as [number, number], drag: null as null | { x: number; y: number; r: [number, number]; moved: boolean }, last: 0, cur: new Float32Array(points.length), tips: new Float32Array(points.length * 2), hover: -1, zoom: 1, goal: null as null | { rot: [number, number]; zoom: number },
    gref: null as Grid | null, gcur: new Float32Array(0), grate: new Float32Array(0), gtop: 1, gidx: new Map<string, number>() });
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
    const col = { ink: css("--ink"), ink3: css("--ink-3"), rule: css("--rule"), rule2: css("--rule-2"), paper: css("--paper-3"), paper2: css("--paper-2"), rise: css("--signal"), fall: css("--fall"), ochre: css("--ochre") };
    const R = Math.min(w, h) / 2 / 1.22, cx = w / 2, cy = h / 2 - R * 0.04;
    const front = geoOrthographic().scale(R).translate([cx, cy]).clipAngle(90).precision(0.6);
    const back = geoOrthographic().scale(R).translate([cx, cy]).clipAngle(90).reflectX(true).precision(0.6);
    const pf = geoPath(front, ctx), pb = geoPath(back, ctx);
    let raf = 0;
    const calm = still();

    const frame = (t: number) => {
      const st = s.current, { v, mode, sel, focus, picked, grid, gsel } = live.current;
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
      // The 2° grid: one small square per land cell, batched into a few paths per colour.
      if (grid) {
        if (st.gref !== grid) {
          st.gref = grid;
          st.gcur = new Float32Array(grid.cells.length);
          st.grate = Float32Array.from(grid.cells, () => 0.03 + Math.random() * 0.09); // staggered, so squares flip in a ripple
          const m = grid.cells.map((c) => Math.abs(c[2])).sort((a, b) => a - b);
          st.gtop = m[Math.floor(m.length * 0.95)] || 1;
          st.gidx = new Map(grid.cells.map((c, i) => [`${c[0]},${c[1]}`, i]));
        }
        const l0 = centre[0] * RAD, sp0 = Math.sin(centre[1] * RAD), cp0 = Math.cos(centre[1] * RAD);
        const half = Math.max(1.1, R * st.zoom * 0.0155);
        const paths = new Map<string, Path2D>();
        const P = (k: string) => { let q = paths.get(k); if (!q) paths.set(k, (q = new Path2D())); return q; };
        for (let i = 0; i < grid.cells.length; i++) {
          const [la, lo, sl, f] = grid.cells[i];
          const lit = mode === "typical" ? f.includes("t") : mode === "luck" ? f.includes("l") || f.includes("o") : gProven(f);
          st.gcur[i] += (+lit - st.gcur[i]) * (calm ? 1 : st.grate[i]);
          const cosc = sp0 * Math.sin(la * RAD) + cp0 * Math.cos(la * RAD) * Math.cos(lo * RAD - l0);
          if (cosc <= 0.02) continue;
          const xy = front([lo, la]);
          if (!xy) continue;
          const key = st.gcur[i] <= 0.5 ? "g" : mode === "luck" ? (f.includes("o") ? "o" : "l")
            : (dirTone(v.id, sl) === "rise" ? "r" : "f") + Math.min(2, Math.floor((Math.abs(sl) / st.gtop) * 3));
          const hh = half * (0.5 + 0.5 * cosc);
          P(key).rect(xy[0] - hh, xy[1] - hh, 2 * hh, 2 * hh);
        }
        const A = [0.4, 0.68, 0.95];
        for (const [k, q] of paths) {
          ctx.fillStyle = k === "g" ? col.ink3 : k === "l" ? col.ochre : k === "o" ? col.ink : k[0] === "r" ? col.rise : col.fall;
          ctx.globalAlpha = k === "g" ? 0.16 : k === "l" || k === "o" ? 0.9 : A[+k[1]];
          ctx.fill(q);
        }
        ctx.globalAlpha = 1;
        if (gsel != null && grid.cells[gsel]) {
          const xy = front([grid.cells[gsel][1], grid.cells[gsel][0]]);
          if (xy) { ctx.strokeStyle = col.ink; ctx.lineWidth = 2.5; ctx.strokeRect(xy[0] - half - 4, xy[1] - half - 4, 2 * half + 8, 2 * half + 8); }
        }
      }
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

      // Spikes, far ones first (only when there is no grid for this variable).
      const order = grid ? [] : points.map((p, i) => ({ i, d: geoDistance([p.lon, p.lat], centre) })).sort((a, b) => b.d - a.d);
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
      if (live.current.grid) return -1;
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
        let gi: number | null = null;
        if (ll && live.current.grid) {
          const la = Math.max(-86, Math.min(88, Math.round((ll[1] + 88) / 2) * 2 - 88));
          const lo = (((Math.round((ll[0] + 180) / 2.5) % 144) + 144) % 144) * 2.5 - 180;
          gi = s.current.gidx.get(`${la},${lo}`) ?? null;
        }
        live.current.onPick(i >= 0 ? i : null, hit ? hit.properties.name : null, gi);
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
/** Grid squares inside a country (cached); if none, the nearest square to its middle. */
const GIN = new Map<string, { idx: number[]; km: number }>();
function gridHere(g: Grid, name: string) {
  const key = g.variable + "|" + name;
  let r = GIN.get(key);
  if (!r) {
    const f = BYNAME.get(name);
    const idx = f ? g.cells.flatMap((c, i) => (geoContainsSafe(f.geometry, [c[1], c[0]]) ? [i] : [])) : [];
    r = { idx, km: 0 };
    const m = !idx.length && mainland(name);
    if (m) {
      const c = geoCentroid(m);
      let best = 0, bd = Infinity;
      g.cells.forEach((x, i) => { const d = geoDistance([x[1], x[0]], c); if (d < bd) { bd = d; best = i; } });
      r = { idx: [best], km: Math.round((bd * 6371) / 10) * 10 };
    }
    GIN.set(key, r);
  }
  return r;
}
function gsum(g: Grid, idx: number[]) {
  const cs = idx.map((i) => g.cells[i]);
  const pr = cs.filter((c) => gProven(c[3]));
  return {
    n: cs.length, p: pr.length, slope: pr.length ? pr.reduce((a, c) => a + c[2], 0) / pr.length : null,
    fooled: cs.filter((c) => c[3].includes("t") && !gProven(c[3])).length, sat: 0, luck: cs.filter((c) => c[3].includes("l")).length,
  };
}

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

// Same baseline as /api/outlook: the 2016–2025 average (centred 2020) to around 2050 = 3 decades.
const TO_2050 = 3;

/** One variable at a set of places: how many proven, the average proven trend, how many fooled the typical test. */
function sum(v: WorldVar, idx: number[]) {
  const cs = idx.map((i) => v.cells[i]).filter((c): c is NonNullable<Cell> => !!c);
  const pr = cs.filter(proven);
  // ponytail: plain mean of the proven slopes; mixed directions inside one country just average out.
  const slope = pr.length ? pr.reduce((a, c) => a + c.slope, 0) / pr.length : null;
  return { n: cs.length, p: pr.length, slope, fooled: cs.filter((c) => c.typical && !proven(c)).length, sat: pr.filter((c) => c.alibi === "could_be_instrument").length };
}

function CountryTable({ world, grids, cols, where, varId, onVar, onDrop }: { world: World; grids: Record<string, Grid>; cols: string[]; where: string[]; varId: string; onVar: (id: string) => void; onDrop: (c: string) => void }) {
  const at = cols.map((c) => ({ name: c, ...placesIn(world, c, where) }));
  const vars = [...FEATURED.map((id) => world.variables.find((x) => x.id === id)).filter((x): x is WorldVar => !!x), ...world.variables.filter((x) => !FEATURED.includes(x.id))];
  return (
    <section className="frame sec" id="country">
      <h2 className="sec-title"><span className="tag">[{cols.length > 1 ? "COMPARE" : "COUNTRY"}]</span>{cols.join(" vs ")}</h2>
      <p className="sec-lede">
        Every variable we tested, at the places inside {cols.length > 1 ? "each country" : cols[0]}. A trend counts only if it is proven after our checks.
        Air temperature and rainfall use every 2° grid square inside the country. "By 2050" draws today's proven trend straight on: a what-if, not a climate-model forecast.
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
                    const g = grids[v.id];
                    const r = g ? gsum(g, gridHere(g, c.name).idx) : sum(v, c.idx);
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
                        <span className="tag">proven at {r.p} of {r.n}{g ? " grid squares" : ""}{r.sat ? ` · ${r.sat} could be the satellite` : ""}</span>
                        <span className="c2050">If it keeps going, around 2050: {signed(r.slope * TO_2050)} {u} vs the last 10 years</span>
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

const OPP: Record<string, [string, string]> = { T2M: ["warmer", "cooler"], PRECTOTCORR: ["wetter", "drier"] };

/** Proven-rising vs proven-falling land squares, from /api/opposites (B8). */
function Opposites({ varId }: { varId: string }) {
  const [d, setD] = useState<{ v: string; o: Opp } | null>(null);
  useEffect(() => {
    let live = true;
    api.opposites(varId).then((o) => live && setD({ v: varId, o })).catch(() => {});
    return () => { live = false; };
  }, [varId]);
  if (!d || d.v !== varId) return null;
  const { o } = d, [up, down] = OPP[varId] ?? ["rising", "falling"];
  const col = (dir: string, list: Opp["rising"]) => (
    <div>
      <p className="tag">[PROVEN {dir.toUpperCase()}]</p>
      <ul className="opp-list">
        {list.map((x) => (
          <li key={x.case}><a href={`${x.case}&name=${encodeURIComponent(x.name)}`}><span>{x.name}</span><b className={`t-${dirTone(varId, x.slope_per_decade)}`}>{signed(x.slope_per_decade)} {short(x.units).replace(/ per decade$/, "")}/decade</b></a></li>
        ))}
      </ul>
    </div>
  );
  return (
    <Reveal className="frame sec">
      <h2 className="sec-title"><span className="tag n" />Opposite places</h2>
      <p className="sec-lede">On land, <b>{o.n_rising.toLocaleString("en-GB")}</b> places are proven {up} and <b>{o.n_falling.toLocaleString("en-GB")}</b> proven {down}, out of {o.n_land_cells.toLocaleString("en-GB")}. These are the steepest of each, at least 15° apart. Open one to see its full case.</p>
      <div className="opp">{col(up, o.rising)}{col(down, o.falling)}</div>
      {o.rising[0] && o.falling[0] && (() => {
        const side = (x: Opp["rising"][number]) => ({ name: x.name, box: new URLSearchParams(x.case.split("?")[1]).get("box")!.split(",").map(Number) as [number, number, number, number] });
        return <a className="cue wide" href={compareHref(varId, side(o.rising[0]), side(o.falling[0]))}><span className="tag">[COMPARE]</span>Put the steepest {up} and {down} places side by side <span aria-hidden>→</span></a>;
      })()}
    </Reveal>
  );
}

export default function WorldView() {
  const [world, setWorld] = useState<World>(exWorld as unknown as World);
  const [varId, setVarId] = useState("T2M"); // opens on the 2° grid + luck test
  const [mode, setMode] = useState<Mode>("typical");
  const [sel, setSel] = useState<number | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [playing, setPlaying] = useState(false);
  const [grids, setGrids] = useState<Record<string, Grid>>({});
  const [gsel, setGsel] = useState<number | null>(null);
  useEffect(() => { api.world<World>().then((d) => d.variables && setWorld(d)).catch(() => {}); }, []);
  useEffect(() => { GRID_VARS.forEach((id) => api.globe<Grid>(id).then((d) => d.cells && setGrids((g) => ({ ...g, [id]: d }))).catch(() => {})); }, []);
  const grid = grids[varId];
  const third: Mode = grid ? "luck" : "satellite";
  useEffect(() => { if ((mode === "luck" || mode === "satellite") && mode !== third) setMode(third); }, [mode, third]);
  useEffect(() => { setGsel(null); }, [varId]);
  useEffect(() => {
    if (!playing) return;
    const order: Mode[] = ["typical", "detective", third];
    const t = setInterval(() => setMode((m) => { const n = order[(order.indexOf(m) + 1) % 3]; if (n === "typical") setPlaying(false); return n; }), 2600);
    return () => clearInterval(t);
  }, [playing, third]);

  const v = world.variables.find((x) => x.id === varId) ?? world.variables[0];
  const where = useMemo(() => world.points.map(placeOf), [world.points]);
  const cols = [...new Set([focus, ...picked].filter((c): c is string => !!c))];
  const here = focus ? (grid ? gridHere(grid, focus) : placesIn(world, focus, where)) : null;
  const fs = here ? (grid ? gsum(grid, here.idx) : sum(v, here.idx)) : null;
  const unit = grid ? "grid square" : "place";
  const gl = grid?.counts.land;
  const gc = grid && gsel != null ? grid.cells[gsel] : null;
  const tot = world.variables.reduce((a, x) => ({ n: a.n + x.n_points, t: a.t + x.n_typical, p: a.p + x.n_proven, f: a.f + x.n_fooled }), { n: 0, t: 0, p: 0, f: 0 });
  const cloud = world.variables.find((x) => x.id === "CLOUD_AMT");
  const fa = examples.validation.validation;
  const i5 = fa.phis.indexOf(0.5);
  const sat = v.alibi.could_be_instrument ?? 0;
  const hasSwitch = Object.keys(v.alibi).some((k) => k !== "no_known_change" && k !== "untested");
  const counts = gl ? { typical: gl.typical, detective: gl.proven, satellite: 0, luck: gl.luck_typical } : { typical: v.n_typical, detective: v.n_proven, satellite: sat, luck: 0 };
  const total = gl ? gl.cells : v.n_points;
  const pc = (n: number) => `${Math.round((n / total) * 100)}%`;
  const shown = useTween(counts[mode], 800);
  const cell = sel != null ? v.cells[sel] : null;
  const pt = sel != null ? world.points[sel] : null;
  const u = short(v.units);
  const rows = [...world.variables].sort((a, b) => b.n_fooled / b.n_points - a.n_fooled / a.n_points);

  const steps: { m: Mode; no: string; title: string; n: number; of: number; text: string }[] = [
    { m: "typical", no: "01", title: "A typical analysis", n: counts.typical, of: total, text: `Each ${unit} tested on its own with a straight line that treats every month as independent. That's how most trend maps are made.` },
    { m: "detective", no: "02", title: "The Detective", n: counts.detective, of: total, text: "Both corrected tests must agree, with neighbouring months' stickiness counted. The rest fade to grey." },
    gl ? { m: "luck", no: "03", title: "The luck test", n: gl.luck_typical, of: total, text: `We shuffle each square's years, so no real trend can exist, and test again. Ochre: the typical test still "finds" one (${pc(gl.luck_typical)}). Ink: ours does (${gl.luck_ours}, ${pc(gl.luck_ours)}).` } :
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
          <Globe v={v} points={world.points} mode={mode} sel={sel} focus={focus} picked={picked} grid={grid} gsel={gsel} onPick={(i, c, g) => { setSel(i); setGsel(g); if (c) setFocus(c); }} />
          <div className="globe-foot">
            <span className="tag">[DRAG TO TURN · TAP A COUNTRY OR A {grid ? "SQUARE" : "SPIKE"}]</span>
            <span className="legend-row">
              {mode !== "luck" && <>
                <span><i className={`k-dot t-${dirTone(v.id, 1)}`} />rising</span>
                <span><i className={`k-dot t-${dirTone(v.id, -1)}`} />falling</span>
              </>}
              <span><i className="k-dot k-grey" />not counted</span>
              {mode === "satellite" && <span><i className="k-ring" />could be the satellite</span>}
              {mode === "luck" && <><span><i className="k-dot k-ochre" />typical test fooled</span><span><i className="k-dot k-ink" />our test fooled</span></>}
              <span className="muted">{grid ? `each square = one 2° NASA MERRA-2 cell (${gl!.cells.toLocaleString("en-GB")} on land); darker = bigger trend` : "spike height = size of the trend"}</span>
            </span>
          </div>
        </div>

        <aside className="globe-side">
          <p className="map-n"><b>{Math.round(shown).toLocaleString("en-GB")}</b><small>/{(mode === "satellite" ? v.n_proven : total).toLocaleString("en-GB")}</small></p>
          <p className="tag">{v.name} · {mode === "typical" ? `${unit}s that look like change` : mode === "detective" ? `${unit}s with proven change` : mode === "luck" ? "shuffled records where a typical test still finds a trend" : "proven trends that could be the instrument"}</p>
          {focus && fs && here && (
            <div className="inspect country" aria-live="polite">
              <p className="tag">[COUNTRY] {focus} · {here.km ? `nearest ${unit} ${here.km.toLocaleString("en-GB")} km away` : `${here.idx.length} ${unit}${here.idx.length === 1 ? "" : "s"}`}</p>
              <p className="cline">
                {fs.slope == null
                  ? <>{v.name}: <b>no proven change</b>{fs.fooled ? `, though a typical test says there is at ${fs.fooled} of ${fs.n}` : ""}.</>
                  : <>{v.name}: <b className={`t-${dirTone(v.id, fs.slope)}`}>{signed(fs.slope)} {u}</b> per decade{grid ? " on average" : ""}, proven at {fs.p} of {fs.n}{grid ? " squares" : ""}. If it keeps going, around 2050: <b>{signed(fs.slope * TO_2050)} {u}</b> vs the last 10 years.</>}
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
                  <span className="gnum"><b>{st.n.toLocaleString("en-GB")}</b> of {st.of.toLocaleString("en-GB")}</span>
                  <span className="gbar" aria-hidden><i style={{ width: `${(st.n / Math.max(st.of, 1)) * 100}%` }} /></span>
                  <span className="gtext">{st.text}</span>
                </button>
              </li>
            ))}
          </ol>
          <button className="btn ghost" onClick={() => { setMode("typical"); setPlaying(true); }} disabled={playing}>{playing ? "Playing…" : "▶ Play the three tests"}</button>

          {gc && (
            <div className="inspect" aria-live="polite">
              <p className="tag">[GRID SQUARE] {placeOf({ lat: gc[0], lon: gc[1] })} · {ll({ lat: gc[0], lon: gc[1] })}</p>
              <dl className="stats">
                <div><dt>Verdict</dt><dd><span className={`verdict v-${G_LABEL[gc[3][0]] ?? "none"}`}><span className="verdict-swatch" aria-hidden />{LABELS[G_LABEL[gc[3][0]] ?? "none"]}</span></dd></div>
                <div><dt>Trend</dt><dd><b>{signed(gc[2])}</b> {u} per decade</dd></div>
                <div><dt>Typical says</dt><dd>{gc[3].includes("t") ? "real change" : "no trend"}</dd></div>
                <div><dt>Luck test</dt><dd className={gc[3].includes("l") ? "hl" : undefined}>{gc[3].includes("l") ? "typical test fooled by shuffled years here" : "not fooled"}{gc[3].includes("o") ? "; ours fooled too" : ""}</dd></div>
              </dl>
              <a className="btn" href={`#/case?var=${v.id}&box=${gc[0] - 1},${gc[0] + 1},${gc[1] - 1.25},${gc[1] + 1.25}&name=${encodeURIComponent(placeOf({ lat: gc[0], lon: gc[1] }))}`}>Open the full case →</a>
            </div>
          )}

          {!grid && <div className="inspect" aria-live="polite">
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
          </div>}
        </aside>
      </section>

      {cols.length > 0 && <CountryTable world={world} grids={grids} cols={cols} where={where} varId={v.id}
        onVar={(id) => { setVarId(id); setSel(null); document.querySelector(".globe-sheet")?.scrollIntoView({ behavior: "smooth" }); }}
        onDrop={(c) => setPicked(picked.filter((x) => x !== c))} />}

      {grid && <Opposites varId={v.id} />}

      <Reveal className="frame sec">
        <h2 className="sec-title"><span className="tag n" />Where a typical analysis goes wrong</h2>
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
        <h2 className="sec-title"><span className="tag n" />Why trust the Detective</h2>
        <Trust variables={world.variables} />
      </Reveal>
    </main>
  );
}
