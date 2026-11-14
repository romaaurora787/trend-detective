// The scroll-story chart: one sticky figure that redraws itself as each step scrolls past.
// AI-use note: drafted with Claude (Anthropic) during the hackathon.
import type { CSSProperties } from "react";
import type { Analysis } from "./api";
import { decYear, fmtTick, niceTicks, useSize } from "./Chart";
import { dirTone, short, signed } from "./lib";

export type Stage = "raw" | "anom" | "trend" | "years" | "chance" | "replay" | "verdict";
const ORDER: Stage[] = ["raw", "anom", "trend", "years", "chance", "replay", "verdict"];

type Replay = { timeline: { end: number; p: number | null }[]; proven: number | null };

const line = (xs: number[], ys: (number | null)[], X: (v: number) => number, Y: (v: number) => number) =>
  xs.map((x, j) => (ys[j] == null ? "" : `${j && ys[j - 1] != null ? "L" : "M"}${X(x).toFixed(1)},${Y(ys[j] as number).toFixed(1)}`)).join("");

export function StoryChart({ data, stage, tone, replay }: { data: Analysis; stage: Stage; tone: "rise" | "fall"; replay: Replay | null }) {
  const [ref, w, h] = useSize<HTMLDivElement>();
  const { chart: c, result: r } = data;
  const at = ORDER.indexOf(stage);
  const past = (s: Stage) => at >= ORDER.indexOf(s);
  const on = (yes: boolean) => (yes ? "lyr on" : "lyr");
  const narrow = w < 520;
  const m = { l: narrow ? 34 : 48, r: narrow ? 12 : 96, t: 34, b: 30 };
  const iw = Math.max(w - m.l - m.r, 10), ih = Math.max(h - m.t - m.b, 10);
  const xs = c.dates.map(decYear);
  const [x0, x1] = [Math.floor(xs[0]), Math.ceil(xs[xs.length - 1])];
  const X = (v: number) => m.l + ((v - x0) / (x1 - x0 || 1)) * iw;
  const scale = (vals: number[], zero: boolean) => {
    let lo = Math.min(...vals, zero ? 0 : Infinity), hi = Math.max(...vals, zero ? 0 : -Infinity);
    const pad = (hi - lo) * 0.08 || 1;
    lo -= pad; hi += pad;
    return { lo, hi, Y: (v: number) => m.t + (1 - (v - lo) / (hi - lo)) * ih };
  };
  const raw = scale(c.values, false);
  const an = scale(c.anomalies, true);
  const units = short(r.units);

  // Trend and its 95% range, drawn as a fan pivoting on the middle of the record.
  const [ya, yb] = c.trend_line;
  const tm = (xs[0] + xs[xs.length - 1]) / 2, ym = (ya + yb) / 2;
  const fan = (s: number, t: number) => ym + (s / 10) * (t - tm);
  const [lo95, hi95] = r.sen_ci95_per_decade;
  const fanPts = [[xs[0], fan(hi95, xs[0])], [xs[xs.length - 1], fan(hi95, xs[xs.length - 1])], [xs[xs.length - 1], fan(lo95, xs[xs.length - 1])], [xs[0], fan(lo95, xs[0])]]
    .map(([x, y]) => `${X(x).toFixed(1)},${an.Y(y).toFixed(1)}`).join(" ");

  // Highest and lowest year, labelled in the "years" step.
  const ann = c.annual_years.map((y, i) => ({ y, v: c.annual_anomalies[i] })).filter((d) => d.v != null);
  const top = ann.reduce((a, b) => (b.v > a.v ? b : a), ann[0]);
  const bw = Math.max(1, (iw / Math.max(ann.length, 1)) * 0.72);

  // Replay: the p-value if the record had stopped in each year (log scale).
  const rp = replay?.timeline.filter((t) => t.p != null && t.p > 0) ?? [];
  const [r0, r1] = rp.length ? [rp[0].end, rp[rp.length - 1].end] : [0, 1];
  const RX = (v: number) => m.l + ((v - r0) / (r1 - r0 || 1)) * iw;
  const RY = (p: number) => m.t + (Math.max(Math.log10(p), -8) / -8) * ih;

  const yr = (s: { Y: (v: number) => number; lo: number; hi: number }, show: boolean, zero: boolean) => (
    <g className={on(show)}>
      {niceTicks(s.lo, s.hi, narrow ? 3 : 5).map((v) => (
        <g key={v}>
          <line className={v === 0 && zero ? "axis-zero" : "grid"} x1={m.l} x2={m.l + iw} y1={s.Y(v)} y2={s.Y(v)} />
          <text className="tick" x={m.l - 8} y={s.Y(v)} dy="0.32em" textAnchor="end">{fmtTick(v)}</text>
        </g>
      ))}
    </g>
  );
  const xt = niceTicks(x0, x1, Math.max(2, Math.floor(iw / 110))).filter(Number.isInteger);

  return (
    <div ref={ref} className="story-plot">
      {w > 0 && h > 0 && (
        <svg width={w} height={h} role="img" aria-label={`${data.variable.name}: ${r.verdict.headline}`}>
          {yr(raw, stage === "raw", false)}
          {yr(an, past("anom") && stage !== "replay", true)}
          <g className={on(stage !== "replay")}>
            {xt.map((v) => <text key={v} className="tick" x={X(v)} y={h - 8} textAnchor="middle">{v}</text>)}
            <text className="tick unit" x={m.l - 8} y={m.t - 14}>{stage === "raw" ? units : `${units} vs usual`}</text>
          </g>

          <g className={on(stage === "raw")}><path className="ln-raw draw" pathLength={1} d={line(xs, c.values, X, raw.Y)} /></g>
          <g className={on(past("anom") && stage !== "replay")}>
            <path className={`ln-an draw${past("years") ? " faint" : ""}`} pathLength={1} d={line(xs, c.anomalies, X, an.Y)} />
          </g>

          <g className={on(past("years") && stage !== "replay")}>
            {ann.map((d, i) => {
              const y = an.Y(d.v), y0 = an.Y(0);
              const up = d.v >= 0;
              return <rect key={d.y} className={`bar ${up ? "pos" : "neg"} t-${dirTone(data.variable.id, d.v)}`}
                style={{ "--i": i } as CSSProperties} x={X(d.y + 0.5) - bw / 2} y={Math.min(y, y0)} width={bw} height={Math.max(Math.abs(y - y0), 0.5)} />;
            })}
          </g>

          <g className={on(past("trend") && stage !== "replay")}>
            <polygon className={`fan t-${tone}`} points={fanPts} />
            <path className={`ln-trend draw t-${tone}`} pathLength={1} d={`M${X(xs[0])},${an.Y(ya)}L${X(xs[xs.length - 1])},${an.Y(yb)}`} />
            {r.typical_vs_detective.typical_slope_per_decade != null && (
              <g className={on(stage === "chance")}>
                <path className="ln-typical draw" pathLength={1}
                  d={`M${X(xs[0])},${an.Y(fan(r.typical_vs_detective.typical_slope_per_decade, xs[0]))}L${X(xs[xs.length - 1])},${an.Y(fan(r.typical_vs_detective.typical_slope_per_decade, xs[xs.length - 1]))}`} />
              </g>
            )}
            {!narrow && (
              <text className={`callout t-${tone}`} x={X(xs[xs.length - 1]) + 8} y={an.Y(yb)} dy="0.32em">
                <tspan x={X(xs[xs.length - 1]) + 8} className="big">{signed(r.sen_slope_per_decade)}</tspan>
                <tspan x={X(xs[xs.length - 1]) + 8} dy="1.3em">{units} / decade</tspan>
              </text>
            )}
          </g>

          {top && (
            <g className={on(stage === "years")}>
              <line className="lead" x1={X(top.y + 0.5)} x2={X(top.y + 0.5)} y1={an.Y(top.v) - 4} y2={m.t + 6} />
              <text className="callout" x={X(top.y + 0.5)} y={m.t} textAnchor={X(top.y + 0.5) > w * 0.7 ? "end" : "middle"}>{top.y}: {signed(top.v)} {units}</text>
            </g>
          )}

          {rp.length > 1 && (
            <g className={on(stage === "replay")}>
              {([[1, "p = 1, pure chance"], [0.05, "0.05, proven"], [0.01, "0.01, strong"], [1e-4, "0.0001"], [1e-8, "10⁻⁸"]] as [number, string][]).map(([p, t]) => (
                <g key={t}>
                  <line className={p === 0.05 ? "axis-zero" : "grid"} x1={m.l} x2={m.l + iw} y1={RY(p)} y2={RY(p)} />
                  <text className="tick" x={m.l + 4} y={RY(p) - 5}>{t}</text>
                </g>
              ))}
              <rect className="strong-zone" x={m.l} y={RY(0.05)} width={iw} height={m.t + ih - RY(0.05)} />
              {[r0, Math.round((r0 + r1) / 2), r1].map((v) => <text key={v} className="tick" x={RX(v)} y={h - 8} textAnchor="middle">to {v}</text>)}
              <path className="ln-replay draw" pathLength={1} d={rp.map((t, i) => `${i ? "L" : "M"}${RX(t.end).toFixed(1)},${RY(t.p as number).toFixed(1)}`).join("")} />
              {replay?.proven && (
                <>
                  <line className="mark" x1={RX(replay.proven)} x2={RX(replay.proven)} y1={m.t} y2={m.t + ih} />
                  <text className="callout t-rise" x={RX(replay.proven) + 6} y={m.t + 12}>proven by {replay.proven}</text>
                </>
              )}
            </g>
          )}
        </svg>
      )}
    </div>
  );
}

/** What the chart is showing right now, as a key under the plot. */
export function StoryKey({ stage, tone, varId }: { stage: Stage; tone: "rise" | "fall"; varId: string }) {
  const items: [string, string][] =
    stage === "raw" ? [["k-raw", "Every month as measured"]]
    : stage === "anom" ? [["k-an", "Each month minus its usual value"]]
    : stage === "trend" ? [["k-an", "Month vs usual"], [`k-trend t-${tone}`, "Trend (Sen's slope)"], [`k-fan t-${tone}`, "95% range of the rate"]]
    : stage === "chance" ? [[`k-bar t-${dirTone(varId, 1)}`, "Year above average"], [`k-trend t-${tone}`, "Our trend"], ["k-typ", "A typical analysis's line"]]
    : stage === "replay" ? [["k-replay", "Evidence if the record had stopped that year"], ["k-zone", "Proven (p < 0.05)"]]
    : [[`k-bar t-${dirTone(varId, 1)}`, "Year above average"], [`k-bar t-${dirTone(varId, -1)}`, "Year below"], [`k-trend t-${tone}`, "Trend"]];
  return <p className="story-key">{items.map(([k, t]) => <span key={t}><i className={k} />{t}</span>)}</p>;
}
