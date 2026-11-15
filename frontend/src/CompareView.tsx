// Compare two places (P2): is the gap between them itself a proven trend? Uses /api/compare.
// AI-use note: drafted with Claude (Anthropic).
import { useEffect, useState, type CSSProperties } from "react";
import { api, type Box, type Compare, type Label, type Variable } from "./api";
import { Reveal } from "./Chart";
import { LABELS, PLACES, dirTone, short, signed } from "./lib";

type Side = { name: string; box: Box };
// Pre-warmed on the server (backend/scripts/prewarm_sunday.py COMPARE).
const PRESETS: { tag: string; title: string; v: string; a: Side; b: Side }[] = [
  { tag: "Opposite rain", title: "Amazon drier, Sahel wetter", v: "PRECTOTCORR", a: { name: "Amazon (Rondonia)", box: [-12, -8, -66, -60] }, b: { name: "Sahel", box: [12, 16, -5, 5] } },
  { tag: "Arctic speed", title: "Svalbard vs Lincolnshire warming", v: "T2M", a: { name: "Svalbard", box: [77, 80, 10, 20] }, b: { name: "Lincolnshire", box: [52.6, 53.7, -1, 0.4] } },
  { tag: "City vs country", title: "Lincolnshire vs London", v: "T2M", a: { name: "Lincolnshire", box: [52.6, 53.7, -1, 0.4] }, b: { name: "London", box: [51.2, 51.8, -0.6, 0.4] } },
];

function read() {
  const p = new URLSearchParams(location.hash.split("?")[1]);
  const bx = (s: string | null) => { const b = s?.split(",").map(Number); return b?.length === 4 && b.every(Number.isFinite) ? (b as Box) : null; };
  const a = bx(p.get("a")), b = bx(p.get("b"));
  if (!a || !b) return { v: PRESETS[0].v, a: PRESETS[0].a, b: PRESETS[0].b };
  return { v: p.get("var") ?? "T2M", a: { name: p.get("na") ?? "Place A", box: a }, b: { name: p.get("nb") ?? "Place B", box: b } };
}
export const compareHref = (v: string, a: Side, b: Side) =>
  `#/compare?var=${v}&a=${a.box.join(",")}&b=${b.box.join(",")}&na=${encodeURIComponent(a.name)}&nb=${encodeURIComponent(b.name)}`;
const caseHref = (v: string, s: Side) => `#/case?var=${v}&box=${s.box.join(",")}&name=${encodeURIComponent(s.name)}`;

export function CompareView({ vars }: { vars: Variable[] }) {
  const [q, setQ] = useState(read);
  const [d, setD] = useState<{ key: string; c: Compare } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secs, setSecs] = useState(0);
  const key = `${q.v}|${q.a.box}|${q.b.box}`;
  useEffect(() => { const on = () => setQ(read()); addEventListener("hashchange", on); return () => removeEventListener("hashchange", on); }, []);
  useEffect(() => {
    let live = true;
    setError(null); setSecs(0);
    const t = setInterval(() => setSecs((s) => s + 1), 1000);
    api.compare(q.v, q.a.box, q.b.box, q.a.name, q.b.name)
      .then((c) => live && setD({ key, c })).catch((e: Error) => live && setError(e.message)).finally(() => clearInterval(t));
    return () => { live = false; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const go = (v: string, a: Side, b: Side) => { location.hash = compareHref(v, a, b); };
  const placeIdx = (s: Side) => PLACES.findIndex((p) => p.box.every((x, i) => Math.abs(x - s.box[i]) < 1e-6));
  const c = d?.key === key ? d.c : null;
  const u = c ? short(c.variable.units) : "";

  // One scale for A, B and the gap, so the bars compare by eye.
  const span = c ? Math.max(...[c.a.ci95, c.b.ci95, c.difference.ci95].flat().map(Math.abs), 1e-9) * 1.1 : 1;
  const X = (x: number) => 50 + (x / span) * 50;
  const bar = (slope: number, ci: [number, number], tone: string) => (
    <svg className="interval" viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden>
      <line className="iv-zero" x1="50" x2="50" y1="0" y2="12" />
      <rect className={`iv-range t-${tone}`} x={X(ci[0])} width={Math.max(X(ci[1]) - X(ci[0]), 0.6)} y="4" height="4" />
      <rect className={`iv-mid t-${tone}`} x={X(slope) - 0.6} width="1.2" y="1" height="10" />
    </svg>
  );
  const side = (s: Compare["a"], href: string) => (
    <div className="y-card">
      <p className="tag">[{s.name.toUpperCase()}]</p>
      <b className={`t-${dirTone(q.v, s.slope_per_decade)}`}>{signed(s.slope_per_decade)} {u}<small>/decade</small></b>
      {bar(s.slope_per_decade, s.ci95, dirTone(q.v, s.slope_per_decade))}
      <span className={`verdict v-${s.label}`}><span className="verdict-swatch" aria-hidden />{LABELS[s.label as Label]}</span>
      <a className="linkish" href={href}>Open the full case →</a>
    </div>
  );

  return (
    <main className="sheet comparev" aria-busy={!c}>
      <section className="frame hero hero-sm">
        <div className="bar-top">
          <span className="tag">[COMPARE] two places, one variable</span>
          <span className="tag" role="status">{error ? <span className="error">{error}</span> : c ? `[${c.n_cells[0]} + ${c.n_cells[1]} NASA grid cells] ${c.period}` : `[LIVE] reading both places (${secs} s)…`}</span>
        </div>
        <h1 className="hero-line">Are two places <span className="hl">really changing differently?</span></h1>
        <p className="lede">Two trends can look opposite by luck. We test the gap itself: place A minus place B, month by month, with the same corrected tests.</p>
      </section>

      <Reveal className="frame cases" aria-label="Ready-made comparisons">
        {PRESETS.map((p, i) => (
          <button key={p.title} className="case-card" aria-pressed={key === `${p.v}|${p.a.box}|${p.b.box}`} onClick={() => go(p.v, p.a, p.b)} style={{ "--n": i } as CSSProperties}>
            <span className="chip">{p.tag}</span>
            <b>{p.title}</b>
            <span className="tag">Compare →</span>
          </button>
        ))}
      </Reveal>

      <section className="frame cmp-pick" aria-label="Choose your own pair">
        <label><span>Variable</span>
          <select value={q.v} onChange={(e) => go(e.target.value, q.a, q.b)}>
            {vars.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </label>
        {(["a", "b"] as const).map((k) => (
          <label key={k}><span>Place {k.toUpperCase()}</span>
            <select value={placeIdx(q[k])} onChange={(e) => { const p = PLACES[+e.target.value]; const s = { name: p.name, box: p.box }; go(q.v, k === "a" ? s : q.a, k === "b" ? s : q.b); }}>
              {placeIdx(q[k]) < 0 && <option value={-1}>{q[k].name}</option>}
              {PLACES.map((p, i) => <option key={p.name} value={i}>{p.name}</option>)}
            </select>
          </label>
        ))}
      </section>

      {c && (
        <>
          <Reveal className="frame sec">
            <h2 className="sec-title"><span className="tag">[01]</span>{c.variable.name}, {c.period}</h2>
            <p className="big-line pad">{c.headline.replace(/\.?$/, ".")}</p>
            {c.trap && <p className="y-caution pad-x">{c.trap}</p>}
            <div className="y2050">
              {side(c.a, caseHref(q.v, q.a))}
              {side(c.b, caseHref(q.v, q.b))}
              <div className="y-card y-wide">
                <p className="tag">[THE GAP: {c.a.name.toUpperCase()} MINUS {c.b.name.toUpperCase()}]</p>
                <b>{signed(c.difference.slope_per_decade)} {u}<small>/decade</small></b>
                {bar(c.difference.slope_per_decade, c.difference.ci95, "ink")}
                <span className={`verdict v-${c.difference.label}`}><span className="verdict-swatch" aria-hidden />{LABELS[c.difference.label as Label]}</span>
                <p>{c.labels.rates_differ ? "The two places are proven to be changing at different rates." : "We can't prove the two places are changing at different rates: the gap could be luck."}
                  {c.labels.supported_opposite_trends ? " And they move in opposite directions, both proven." : ""}</p>
                <Gap c={c} />
                {c.note && <p className="note">{c.note}</p>}
              </div>
              <p className="note y-note">{c.method}. Monthly correlation between the two places: {c.correlation.toFixed(2)}.{c.boxes_overlap ? " The two boxes overlap, so they share some data." : ""}</p>
            </div>
          </Reveal>
        </>
      )}
    </main>
  );
}

/** The gap, month by month (seasons removed), with zero marked. */
function Gap({ c }: { c: Compare }) {
  const ys = c.chart.difference_anomaly, n = ys.length;
  const m = Math.max(...ys.map((y) => Math.abs(y ?? 0)), 1e-9);
  const pts = ys.map((y, i) => (y == null ? null : `${((i / (n - 1)) * 100).toFixed(2)},${(20 - (y / m) * 18).toFixed(2)}`)).filter(Boolean).join(" ");
  return (
    <figure className="gap">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={`Gap between the two places, ${c.chart.dates[0]} to ${c.chart.dates[n - 1]}`}>
        <line x1="0" x2="100" y1="20" y2="20" className="iv-zero" />
        <polyline points={pts} className="gap-line" />
      </svg>
      <figcaption className="note">{c.chart.dates[0].slice(0, 4)}–{c.chart.dates[n - 1].slice(0, 4)}: the gap each month, seasons removed. Above the line: {c.a.name} higher than usual relative to {c.b.name}.</figcaption>
    </figure>
  );
}
