import { useEffect, useRef, useState, type ReactNode } from "react";

/** Width of an element, tracked. Charts draw at real pixels so text never stretches. */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export const decYear = (d: string) => {
  const [y, m] = d.split("-").map(Number);
  return y + (m - 0.5) / 12;
};

function niceTicks(lo: number, hi: number, n = 4): number[] {
  const span = hi - lo || 1;
  const step0 = span / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= step0) ?? mag * 10;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toPrecision(6)));
  return out;
}

const fmtTick = (v: number) => (Math.abs(v) < 1e-9 ? "0" : String(v).replace("-", "−"));

export interface Series { xs: number[]; ys: (number | null)[]; cls: string; kind?: "line" | "bar" }

/**
 * One lettered figure panel: hairline axes, tabular ticks, any number of series.
 * ponytail: hand-drawn SVG instead of a chart library; four chart shapes don't earn 100 kB.
 */
export function Panel({
  letter, title, series, height = 180, yLabel, zero = false, xDomain, yDomain, lit, children, xTicks: xT, xFmt,
}: {
  letter?: string; title: ReactNode; series: Series[]; height?: number; yLabel?: string; zero?: boolean;
  xDomain?: [number, number]; yDomain?: [number, number]; lit?: boolean | null; children?: ReactNode;
  xTicks?: number[]; xFmt?: (v: number) => string;
}) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const m = { l: 44, r: 10, t: yLabel ? 20 : 8, b: 24 };
  const iw = Math.max(w - m.l - m.r, 10), ih = height - m.t - m.b;
  const allX = series.flatMap((s) => s.xs);
  const allY = series.flatMap((s) => s.ys.filter((y): y is number => y != null && Number.isFinite(y)));
  const [x0, x1] = xDomain ?? [Math.min(...allX), Math.max(...allX)];
  let [y0, y1] = yDomain ?? [Math.min(...allY, zero ? 0 : Infinity), Math.max(...allY, zero ? 0 : -Infinity)];
  const pad = (y1 - y0) * 0.06 || 1;
  if (!yDomain) { y0 -= pad; y1 += pad; }
  const X = (v: number) => m.l + ((v - x0) / (x1 - x0 || 1)) * iw;
  const Y = (v: number) => m.t + (1 - (v - y0) / (y1 - y0 || 1)) * ih;
  const yt = niceTicks(y0, y1, 4);
  const xt = xT ?? niceTicks(x0, x1, Math.max(2, Math.floor(iw / 90))).filter((v) => Number.isInteger(v));
  const barW = (s: Series) => Math.max(1, (iw / Math.max(s.xs.length, 1)) * 0.8);

  return (
    <figure className={`panel${lit === true ? " is-lit" : lit === false ? " is-dim" : ""}`}>
      <figcaption>
        {letter && <span className="panel-letter">{letter}</span>}
        <span>{title}</span>
      </figcaption>
      <div ref={ref} className="panel-plot">
        {w > 0 && (
          <svg width={w} height={height} role="img" aria-label={typeof title === "string" ? title : undefined}>
            {yt.map((v) => (
              <g key={v}>
                <line className={v === 0 && zero ? "axis-zero" : "grid"} x1={m.l} x2={m.l + iw} y1={Y(v)} y2={Y(v)} />
                <text className="tick" x={m.l - 6} y={Y(v)} dy="0.32em" textAnchor="end">{fmtTick(v)}</text>
              </g>
            ))}
            {xt.map((v) => (
              <text key={v} className="tick" x={X(v)} y={height - 6} textAnchor="middle">{xFmt ? xFmt(v) : fmtTick(v)}</text>
            ))}
            <line className="axis" x1={m.l} x2={m.l + iw} y1={m.t + ih} y2={m.t + ih} />
            {series.map((s, i) =>
              s.kind === "bar" ? (
                <g key={i}>
                  {s.xs.map((x, j) => {
                    const y = s.ys[j];
                    if (y == null) return null;
                    const top = Math.min(Y(y), Y(0)), hgt = Math.abs(Y(y) - Y(0));
                    return <rect key={j} className={`${s.cls} ${y >= 0 ? "pos" : "neg"}`} x={X(x) - barW(s) / 2} y={top} width={barW(s)} height={Math.max(hgt, 0.5)} />;
                  })}
                </g>
              ) : (
                <path
                  key={i}
                  className={s.cls}
                  d={s.xs.map((x, j) => (s.ys[j] == null ? "" : `${j && s.ys[j - 1] != null ? "L" : "M"}${X(x).toFixed(1)},${Y(s.ys[j] as number).toFixed(1)}`)).join("")}
                />
              ),
            )}
            {yLabel && <text className="tick unit" x={m.l - 6} y={8} textAnchor="end">{yLabel}</text>}
          </svg>
        )}
      </div>
      {children}
    </figure>
  );
}
