// Cross-examination grid, witnesses list, "check our work". AI-use note: drafted with Claude (Anthropic).
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { api, badgeOf, examples, type Box, type CrossExam, type Witness, type Witnesses } from "./api";
import { useInView, useTween } from "./Chart";
import { LABELS, dirTone, sameBox, signed } from "./lib";

export const HOME: Box = [52.6, 53.7, -1.0, 0.4];
export const isHome = (varId: string, box: Box) => varId === "T2M" && sameBox(box, HOME);

/** Live fetch with a saved example for the home case, so the demo never opens empty. */
export function useLive<T>(load: () => Promise<T>, key: string, example: T | null) {
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

export const useCrossExam = (varId: string, box: Box) =>
  useLive(() => api.crossExam(varId, box), `${varId}|${box}`, isHome(varId, box) ? examples.crossExam : null);

function MonthBars({ months, varId }: { months: { month: string; slope_per_decade: number; proven_fdr: boolean }[]; varId: string }) {
  const max = Math.max(...months.map((m) => Math.abs(m.slope_per_decade)), 1e-9);
  return (
    <div className="months" role="img" aria-label={`Change per decade by month; solid = proven: ${months.map((m) => `${m.month} ${signed(m.slope_per_decade)}${m.proven_fdr ? " proven" : ""}`).join(", ")}`}>
      {months.map((m, i) => (
        <div key={m.month} className="month">
          <div className="month-col">
            <i className={`t-${dirTone(varId, m.slope_per_decade)} ${m.proven_fdr ? "solid" : "faint"} ${m.slope_per_decade >= 0 ? "up" : "down"}`}
              style={{ height: `${(Math.abs(m.slope_per_decade) / max) * 50}%`, "--i": i } as CSSProperties} />
          </div>
          <span>{m.month[0]}</span>
        </div>
      ))}
    </div>
  );
}

type Row = { name: string; sec: { headline?: string; error?: string } | undefined; pass?: boolean; extra?: ReactNode };

export function CrossExamBlock({ x, error, varId, units }: { x: CrossExam | null; error: string | null; varId: string; units: string }) {
  const [ref, seen] = useInView<HTMLDivElement>();
  const passed = useTween(seen && x?.score.proven ? x.score.passed ?? 0 : 0, 1200);
  if (!x) return <p className="status pad" role="status">{error ? <span className="error">{error}</span> : "Putting this trend through the sceptic's checks…"}</p>;

  const scored = x.score.proven;
  // Same pass rules as backend crossexam.py score, so the marks add up to its "passed N of 5".
  const is = (s: { status?: string } | undefined, ok: string[]) => (s?.status ? ok.includes(s.status) : undefined);
  const { alibi: a, el_nino: en, leave_one_out: lo, walk_forward: wf, all_windows: aw, climate_modes: cm, seasons: se } = x;
  const tested = (a?.changes ?? []).filter((c) => c.tested && c.before && c.after);
  const rows: Row[] = [
    { name: "A change of instrument?", sec: a, pass: is(a, ["survives", "survives_weakly", "no_known_change"]),
      extra: tested.map((c) => <p key={c.date} className="pair">{c.before!.period}: <b>{signed(c.before!.slope_per_decade)}</b> · {c.after!.period}: <b>{signed(c.after!.slope_per_decade)}</b> {units}/decade</p>) },
    { name: "El Niño removed", sec: en, pass: is(en, ["survives", "none"]), extra: en?.how_linked && <p className="pair">{en.how_linked}</p> },
    { name: "One year carrying it?", sec: lo, pass: lo?.flips ? !lo.flips.length : undefined },
    { name: "Found in both halves?", sec: wf, pass: is(wf, ["confirmed", "continuing", "neither"]) },
    { name: "Cherry-picked dates?", sec: aw, pass: aw?.proven_opposite != null ? !aw.proven_opposite : undefined },
    { name: "Other ocean cycles removed", sec: cm, extra: cm?.strongest && <p className="pair">{cm.strongest}</p> },
    { name: "Which months?", sec: se, extra: se?.months && <MonthBars months={se.months} varId={varId} /> },
    { name: "Speeding up?", sec: x.decades },
    { name: "Sudden or gradual?", sec: x.change_point },
    { name: "How local is this?", sec: x.resolution },
  ];

  return (
    <>
      <div ref={ref} className="score">
        <p className="score-n" aria-label={scored ? `${x.score.passed} of ${x.score.of} checks passed` : undefined}>
          {scored ? <>{Math.round(passed)}<small>/{x.score.of}</small></> : <small>—</small>}
        </p>
        <div className="score-text">
          <p className="tag">[SCORE] {scored ? "checks passed" : "not scored: nothing proven to test"}</p>
          <p className="big-line">{x.score.headline}</p>
          {x.score.checks && (
            <details className="details">
              <summary>How the {x.score.of} checks are scored</summary>
              <ol>{x.score.checks.map((c) => <li key={c}>{c}</li>)}</ol>
              {x.score.rule_note && <p className="note">{x.score.rule_note}</p>}
            </details>
          )}
        </div>
      </div>
      <ol className="checks">
        {rows.filter((r) => r.sec && !r.sec.error && r.sec.headline).map((r, i) => {
          const mark = r.pass === undefined || !scored ? "info" : r.pass ? "ok" : "warn";
          return (
            <li key={r.name} className={`check c-${mark}`} style={{ "--n": i } as CSSProperties}>
              <p className="tag">[{String(i + 1).padStart(2, "0")}] <span className="check-mark">{mark === "ok" ? "✔ Holds" : mark === "warn" ? "⚠ Caution" : "Context"}</span></p>
              <h3>{r.name}</h3>
              <p>{r.sec!.headline}</p>
              {r.extra}
            </li>
          );
        })}
      </ol>
      {x.could_overturn && x.could_overturn.length > 0 && (
        <div className="overturn">
          <p className="tag">[STILL OPEN] What could overturn this</p>
          <ul>{x.could_overturn.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
      )}
    </>
  );
}

const BADGE = { confirmed: "Confirmed", consistent: "Consistent", caution: "Caution" };

export function WitnessList({ varId, box, fallback }: { varId: string; box: Box; fallback: Witness }) {
  const { data } = useLive<Witnesses | null>(() => api.witnesses(varId, box), `${varId}|${box}`, isHome(varId, box) ? examples.witnesses : null);
  const list = data?.witnesses.filter((w) => w.available) ?? [];
  if (!list.length) {
    const b = badgeOf(fallback);
    return b ? (
      <ul className="witnesses"><li style={{ "--n": 0 } as CSSProperties}><span className={`badge b-${b}`}>{BADGE[b]}</span><div><strong>{fallback.name}</strong><span className="note">{fallback.note}</span></div></li></ul>
    ) : <p className="note pad">{data ? "No independent record for this variable and place yet." : "Asking the other records…"}</p>;
  }
  return (
    <>
      <p className="big-line pad">{data!.headline}</p>
      <ul className="witnesses">
        {list.map((w, i) => {
          const b = badgeOf(w) ?? "caution";
          return (
            <li key={w.name} style={{ "--n": i } as CSSProperties}>
              <span className={`badge b-${b}`}>{BADGE[b]}</span>
              <div>
                <strong>{w.name}</strong>
                <span className="note">{w.witness_verdict ? `${LABELS[w.witness_verdict]}` : ""}{w.monthly_correlation != null ? ` · month-to-month r = ${w.monthly_correlation.toFixed(2)}` : ""}</span>
                {w.independence && w.independence !== "independent" && <span className="note">{w.independence}</span>}
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function CheckOurWork({ links, csv }: { links: { name: string; url: string; note: string }[]; csv: string }) {
  const all = [
    ...links,
    { name: "Download the evidence (CSV)", url: csv, note: "Every month, the seasonal normal, the trend line and the verdict." },
    { name: "Rebuild the number yourself (notebook)", url: "https://github.com/romaaurora787/trend-detective/blob/main/notebooks/reproduce_lincolnshire.ipynb", note: "Uses only NASA's public API." },
  ];
  return (
    <ul className="links">
      {all.map((l, i) => (
        <li key={l.url} style={{ "--n": i } as CSSProperties}>
          <a href={l.url} target={l.url === csv ? undefined : "_blank"} rel="noreferrer">{l.name} <span aria-hidden>↗</span></a>
          <span className="note">{l.note}</span>
        </li>
      ))}
    </ul>
  );
}
