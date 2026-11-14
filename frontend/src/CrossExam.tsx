// Cross-examination block, witnesses list, "check our work". AI-use note: drafted with Claude (Anthropic).
import { useEffect, useState, type ReactNode } from "react";
import { api, badgeOf, examples, type Box, type CrossExam, type Witness, type Witnesses } from "./api";
import { useWidth } from "./Chart";
import { LABELS, dirTone, sameBox, signed } from "./lib";

const HOME: Box = [52.6, 53.7, -1.0, 0.4];

/** Live fetch with a saved example for the home case, so the demo never opens empty. */
function useLive<T>(load: () => Promise<T>, key: string, example: T | null) {
  const [s, set] = useState<{ key: string; data: T | null; error: string | null }>({ key, data: example, error: null });
  useEffect(() => {
    let live = true;
    set({ key, data: example, error: null });
    load().then((d) => live && set({ key, data: d, error: null })).catch((e: Error) => live && set((o) => ({ ...o, error: e.message })));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return s.key === key ? s : { data: example, error: null };
}

/** Replay: the p-value if the record had ended in each year. Log scale, 0.05 line. */
function Replay({ timeline, proven }: { timeline: { end: number; p: number | null }[]; proven: number | null }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const h = 96, m = { l: 52, r: 8, t: 6, b: 20 };
  const pts = timeline.filter((t) => t.p != null && t.p > 0);
  if (pts.length < 2) return null;
  const [x0, x1] = [pts[0].end, pts[pts.length - 1].end];
  const lo = -8;
  const X = (v: number) => m.l + ((v - x0) / (x1 - x0 || 1)) * (w - m.l - m.r);
  const Y = (p: number) => m.t + (Math.max(Math.log10(p), lo) / lo) * (h - m.t - m.b);
  const ticks: [number, string][] = [[1, "p = 1"], [0.05, "0.05"], [1e-4, "0.0001"], [1e-8, "10⁻⁸"]];
  return (
    <div ref={ref} className="mini" aria-label={`Replay: the evidence became strong by ${proven ?? "—"}`} role="img">
      {w > 0 && (
        <svg width={w} height={h}>
          {ticks.map(([p, t]) => (
            <g key={t}>
              <line className={p === 0.05 ? "axis-zero" : "grid"} x1={m.l} x2={w - m.r} y1={Y(p)} y2={Y(p)} />
              <text className="tick" x={m.l - 6} y={Y(p)} dy="0.32em" textAnchor="end">{t}</text>
            </g>
          ))}
          {[x0, x1].map((v) => <text key={v} className="tick" x={X(v)} y={h - 4} textAnchor={v === x0 ? "start" : "end"}>to {v}</text>)}
          {proven && <line className="mark-line" x1={X(proven)} x2={X(proven)} y1={m.t} y2={h - m.b} />}
          {proven && <text className="tick unit" x={X(proven) + 4} y={h - m.b - 4}>strong by {proven}</text>}
          <path className="s-replay" d={pts.map((t, i) => `${i ? "L" : "M"}${X(t.end).toFixed(1)},${Y(t.p as number).toFixed(1)}`).join("")} />
        </svg>
      )}
    </div>
  );
}

function MonthBars({ months, varId }: { months: { month: string; slope_per_decade: number; proven_fdr: boolean }[]; varId: string }) {
  const max = Math.max(...months.map((m) => Math.abs(m.slope_per_decade)), 1e-9);
  return (
    <div className="months" role="img" aria-label={`Change per decade by month; solid = proven: ${months.map((m) => `${m.month} ${signed(m.slope_per_decade)}${m.proven_fdr ? " proven" : ""}`).join(", ")}`}>
      {months.map((m) => (
        <div key={m.month} className="month">
          <div className="month-col">
            <i className={`t-${dirTone(varId, m.slope_per_decade)} ${m.proven_fdr ? "solid" : "faint"} ${m.slope_per_decade >= 0 ? "up" : "down"}`}
              style={{ height: `${(Math.abs(m.slope_per_decade) / max) * 50}%` }} />
          </div>
          <span>{m.month[0]}</span>
        </div>
      ))}
    </div>
  );
}

type Row = { name: string; sec: { headline?: string; error?: string } | undefined; pass?: boolean; extra?: ReactNode };

export function CrossExamBlock({ varId, box, units }: { varId: string; box: Box; units: string }) {
  const home = varId === "T2M" && sameBox(box, HOME);
  const { data: x, error } = useLive(() => api.crossExam(varId, box), `${varId}|${box}`, home ? examples.crossExam : null);

  if (!x) {
    return (
      <section className="xexam" aria-labelledby="xe-h" aria-busy={!error}>
        <h2 id="xe-h" className="fig-head-sm"><span className="fig-no">Fig. 1, continued</span> Cross-examination</h2>
        <p className="status" role="status">{error ? <span className="error">{error}</span> : "Putting this trend through our sceptic's checks…"}</p>
      </section>
    );
  }
  const scored = x.score.proven;
  // Same pass rules as backend crossexam.py score, so the marks add up to its "passed N of 5".
  const is = (s: { status?: string } | undefined, ok: string[]) => (s?.status ? ok.includes(s.status) : undefined);
  const { alibi: a, el_nino: en, leave_one_out: lo, walk_forward: wf, all_windows: aw, climate_modes: cm, seasons: se } = x;
  const tested = (a?.changes ?? []).filter((c) => c.tested && c.before && c.after);
  const rows: Row[] = [
    { name: "A change of instrument?", sec: a, pass: is(a, ["survives", "survives_weakly", "no_known_change"]),
      extra: tested.map((c) => <p key={c.date} className="pair">{c.before!.period}: <b>{signed(c.before!.slope_per_decade)}</b> · {c.after!.period}: <b>{signed(c.after!.slope_per_decade)}</b> {units}/decade</p>) },
    { name: "El Niño removed", sec: en, pass: is(en, ["survives", "none"]), extra: en?.how_linked && <p className="note">{en.how_linked}</p> },
    { name: "One year carrying it?", sec: lo, pass: lo?.flips ? !lo.flips.length : undefined },
    { name: "Found in both halves?", sec: wf, pass: is(wf, ["confirmed", "continuing", "neither"]) },
    { name: "Cherry-picked dates?", sec: aw, pass: aw?.proven_opposite != null ? !aw.proven_opposite : undefined,
      extra: aw?.timeline && <Replay timeline={aw.timeline} proven={aw.became_proven ?? null} /> },
    { name: "Other ocean cycles removed", sec: cm, extra: cm?.strongest && <p className="note">{cm.strongest}</p> },
    { name: "Which months?", sec: se, extra: se?.months && <MonthBars months={se.months} varId={varId} /> },
    { name: "Speeding up?", sec: x.decades },
    { name: "Sudden or gradual?", sec: x.change_point },
    { name: "How local is this?", sec: x.resolution },
  ];

  return (
    <section className="xexam" aria-labelledby="xe-h">
      <h2 id="xe-h" className="fig-head-sm"><span className="fig-no">Fig. 1, continued</span> Cross-examination</h2>
      <p className="xe-score">
        {scored && <strong className="n">{x.score.passed} of {x.score.of}</strong>}
        <span>{x.score.headline}</span>
      </p>
      <ol className="checks">
        {rows.filter((r) => r.sec && !r.sec.error && r.sec.headline).map((r) => {
          const mark = r.pass === undefined || !scored ? "info" : r.pass ? "ok" : "warn";
          return (
            <li key={r.name} className={`check c-${mark}`}>
              <span className="check-mark">{mark === "ok" ? "✔ Holds" : mark === "warn" ? "⚠ Caution" : "Context"}</span>
              <div className="check-body">
                <h3>{r.name}</h3>
                <p>{r.sec!.headline}</p>
                {r.extra}
              </div>
            </li>
          );
        })}
      </ol>
      {x.could_overturn && x.could_overturn.length > 0 && (
        <div className="overturn">
          <h3>What could still overturn this</h3>
          <ul>{x.could_overturn.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
      )}
    </section>
  );
}

export function WitnessList({ varId, box, fallback }: { varId: string; box: Box; fallback: Witness }) {
  const home = varId === "T2M" && sameBox(box, HOME);
  const { data } = useLive<Witnesses | null>(() => api.witnesses(varId, box), `${varId}|${box}`, home ? examples.witnesses : null);
  const list = data?.witnesses.filter((w) => w.available) ?? [];
  if (!list.length) {
    const b = badgeOf(fallback);
    return b ? (
      <>
        <p className={`badge b-${b}`}>{{ confirmed: "Confirmed", consistent: "Consistent", caution: "Caution" }[b]}<span> · {fallback.name}</span></p>
        <p className="note">{fallback.note}</p>
      </>
    ) : <p className="note">{data ? "No independent record for this variable and place yet." : "Asking the other records…"}</p>;
  }
  return (
    <>
      <p className="w-head">{data!.headline}</p>
      <ul className="witnesses">
        {list.map((w) => (
          <li key={w.name}>
            <span className={`badge b-${w.agrees ? "confirmed" : "caution"}`}>{w.agrees ? "Agrees" : "Disagrees"}</span>
            <div>
              <strong>{w.name}</strong>
              <span className="note">{w.witness_verdict ? `${LABELS[w.witness_verdict]}` : ""}{w.monthly_correlation != null ? ` · month-to-month r = ${w.monthly_correlation.toFixed(2)}` : ""}</span>
              {w.independence && w.independence !== "independent" && <span className="note">{w.independence}</span>}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

export function CheckOurWork({ links, csv }: { links: { name: string; url: string; note: string }[]; csv: string }) {
  return (
    <section className="block" aria-labelledby="cow">
      <h2 id="cow">Check our work</h2>
      <ul className="links">
        {links.map((l) => <li key={l.url}><a href={l.url} target="_blank" rel="noreferrer">{l.name}</a><span className="note">{l.note}</span></li>)}
        <li><a href={csv}>Download the evidence (CSV)</a><span className="note">Every month, the seasonal normal, the trend line and the verdict.</span></li>
        <li><a href="https://github.com/romaaurora787/trend-detective/blob/main/notebooks/reproduce_lincolnshire.ipynb" target="_blank" rel="noreferrer">Rebuild the number yourself (notebook)</a><span className="note">Uses only NASA's public API.</span></li>
      </ul>
    </section>
  );
}
