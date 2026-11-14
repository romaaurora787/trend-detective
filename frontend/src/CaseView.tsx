import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { api, examples, type Analysis, type Box } from "./api";
import { Reveal } from "./Chart";
import { CheckOurWork, CrossExamBlock, WitnessList, useCrossExam } from "./CrossExam";
import { LABELS, dirTone, pText, placeName, plain, sameBox, short, signed } from "./lib";
import { StoryChart, StoryKey, type Stage } from "./Story";

const DEFAULT_VAR = "T2M";
const DEFAULT_BOX: Box = [52.6, 53.7, -1.0, 0.4];

export function useAnalysis(varId: string, box: Box) {
  const isDefault = varId === DEFAULT_VAR && sameBox(box, DEFAULT_BOX);
  const [data, setData] = useState<Analysis | null>(isDefault ? examples.analyse : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    api.analyse(varId, box)
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [varId, box.join()]);
  const stale = !!data && (data.variable.id !== varId || !sameBox(data.box, box));
  return { data, loading, error, stale };
}

function YearsBar({ need, have }: { need: number | null; have: number }) {
  if (need == null || !Number.isFinite(need)) return null;
  const max = Math.max(need, have) * 1.04;
  const pct = (v: number) => `${(v / max) * 100}%`;
  const short = need <= have;
  return (
    <div className="years">
      <div className="years-track" role="img" aria-label={`${Math.round(have)} years of data so far; about ${Math.round(need)} needed to detect a trend this size`}>
        <div className="years-have" style={{ width: pct(have) }} />
        {!short && <div className="years-need" style={{ left: pct(have), width: pct(need - have) }} />}
        <div className="years-mark" style={{ left: pct(need) }} />
      </div>
      <div className="years-scale">
        <span>{Math.round(have)} years so far</span>
        <span>{short ? `a trend this size shows after ~${Math.round(need)} years` : `~${Math.round(need - have)} more needed`}</span>
      </div>
    </div>
  );
}

/** n months as squares; the first k filled: how many independent months the record is really worth. */
function Dots({ n, k }: { n: number; k: number }) {
  return (
    <div className="dots" role="img" aria-label={`${n} months behave like about ${k} independent ones`}>
      {Array.from({ length: n }, (_, i) => <i key={i} className={i < k ? "on" : undefined} />)}
    </div>
  );
}

type Step = { stage: Stage; kicker: string; title: string; text: ReactNode; stats?: [string, ReactNode][]; extra?: ReactNode };

/** Which step's card is crossing the middle of the screen. */
function useActiveStep(n: number) {
  const ref = useRef<HTMLOListElement>(null);
  const [i, setI] = useState(0);
  useEffect(() => {
    const els = ref.current?.querySelectorAll<HTMLElement>("[data-i]");
    if (!els) return;
    // Phones pin the chart over the top 54% of the screen, so the trigger line sits lower there.
    const line = matchMedia("(max-width: 979px)").matches ? "-74% 0px -24% 0px" : "-48% 0px -48% 0px";
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setI(+e.target.getAttribute("data-i")!)), { rootMargin: line });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [n]);
  return [ref, i] as const;
}

export function CaseView({ varId, box, onReport }: { varId: string; box: Box; onReport: () => void }) {
  const { data, loading, error, stale } = useAnalysis(varId, box);
  const x = useCrossExam(varId, box);
  const aw = x.data?.all_windows;
  const replay = aw?.timeline && aw.timeline.length > 1 ? { timeline: aw.timeline, proven: aw.became_proven ?? null } : null;

  const steps = data ? buildSteps(data, replay ? aw?.headline ?? null : null) : [];
  const [stepsRef, active] = useActiveStep(steps.length);

  if (!data) {
    return (
      <main className="sheet" aria-busy={loading}>
        <section className="frame hero hero-wait">
          <div className="bar-top"><span className="tag">[CASE] {placeName(box)}</span></div>
          <p className="hero-line">Reading 45 years <span className="hl">of NASA data…</span></p>
          <p className="lede" role="status">{error ?? "Fetching every month for this place. The first look at a new place takes a few seconds."}</p>
        </section>
      </main>
    );
  }

  const { result: r, variable: v } = data;
  const tone = dirTone(v.id, r.sen_slope_per_decade);
  const label = r.verdict.label;
  const place = placeName(data.box);
  const stage = steps[Math.min(active, steps.length - 1)]?.stage ?? "raw";

  return (
    <main className={`sheet case${stale || loading ? " is-loading" : ""}`} aria-busy={loading}>
      <section className="frame hero">
        <div className="bar-top">
          <span className="tag">[CASE] {place} · {r.start.slice(0, 4)}–{r.end.slice(0, 4)}</span>
          <span className="tag" role="status">{error ? <span className="error">{error}</span> : loading ? "[LIVE] checking NASA's record…" : `[${data.n_cells} NASA grid cell${data.n_cells === 1 ? "" : "s"}] ${v.source}`}</span>
        </div>
        <h1 className="hero-line">{v.name} in {place}. <span className="hl">Really changing?</span></h1>
        <div className="hero-foot">
          <p className="lede">
            {r.n_months ?? data.chart.dates.length} months of NASA data. The seasons swing about {plain(r.seasonal_amplitude)} {short(r.units)} every year;
            the change we're hunting for is a small slice of that. Scroll, and watch the Detective test it one step at a time.
          </p>
          <a className="cue" href="#story"><span className="tag">[{steps.length} steps]</span>Scroll the evidence <span aria-hidden className="nudge">↓</span></a>
        </div>
      </section>

      <section className="frame story" id="story" aria-label="The evidence, step by step">
        <div className="story-stage">
          <div className="story-bar">
            <span className="tag">[{String(active + 1).padStart(2, "0")}/{String(steps.length).padStart(2, "0")}] {steps[active]?.kicker}</span>
            <span className="progress" aria-hidden><i style={{ width: `${((active + 1) / steps.length) * 100}%` }} /></span>
          </div>
          <StoryChart data={data} stage={stage} tone={tone} replay={replay} />
          <div className={`stamp v-${label}${stage === "verdict" ? " on" : ""}`} aria-hidden={stage !== "verdict"}>
            <span className="tag">[VERDICT]</span>{LABELS[label]}
          </div>
          <StoryKey stage={stage} tone={tone} varId={v.id} />
        </div>
        <ol className="steps" ref={stepsRef}>
          {steps.map((s, i) => (
            <li key={s.stage} data-i={i} className={`step${i === active ? " is-on" : ""}`}>
              <div className="card">
                <p className="tag">[{String(i + 1).padStart(2, "0")}] {s.kicker}</p>
                <h2>{s.title}</h2>
                <div className="card-text">{s.text}</div>
                {s.stats && (
                  <dl className="stats">
                    {s.stats.map(([k, val], j) => <div key={k} style={{ "--n": j } as CSSProperties}><dt>{k}</dt><dd>{val}</dd></div>)}
                  </dl>
                )}
                {s.extra}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <Reveal className="frame sec">
        <h2 className="sec-title"><span className="tag">[{String(steps.length + 1).padStart(2, "0")}]</span>Cross-examination</h2>
        <p className="sec-lede">A sceptic's checks. Each one tries to explain the trend away.</p>
        <CrossExamBlock x={x.data} error={x.error} varId={v.id} units={short(r.units)} />
      </Reveal>

      <div className="pair-row">
        <Reveal className="frame sec">
          <h2 className="sec-title"><span className="tag">[{String(steps.length + 2).padStart(2, "0")}]</span>Witnesses</h2>
          <WitnessList varId={v.id} box={data.box} fallback={data.second_witness} />
        </Reveal>
        <Reveal className="frame sec">
          <h2 className="sec-title"><span className="tag">[{String(steps.length + 3).padStart(2, "0")}]</span>Check our work</h2>
          <CheckOurWork links={r.reproduce ?? []} csv={api.evidenceUrl(v.id, data.box)} />
          <details className="details pad">
            <summary>The numbers behind it</summary>
            <dl className="stats">
              <div><dt>Mann-Kendall, Hamed-Rao</dt><dd>{pText(r.mk_hamed_rao.p)}</dd></div>
              <div><dt>Least squares, n_eff</dt><dd>{pText(r.ols_neff.p)}, n_eff = {Math.round(r.ols_neff.n_eff)} of {data.chart.dates.length}</dd></div>
              <div><dt>Lag-1 stickiness</dt><dd>{r.ols_neff.lag1_autocorr.toFixed(2)}</dd></div>
              <div><dt>Slope method</dt><dd>{r.slope_method === "sen" ? "Sen's slope" : "Corrected least squares"}</dd></div>
            </dl>
          </details>
        </Reveal>
      </div>

      <p className="cite">{data.citation}. Trend is not cause: we detect change, we do not explain it.</p>
      <button className="cue wide" onClick={onReport}><span className="tag">[NEXT]</span>See everything changing in {place} <span aria-hidden>→</span></button>
    </main>
  );
}

function buildSteps(data: Analysis, replayHeadline: string | null): Step[] {
  const { result: r, chart: c, variable: v } = data;
  const u = short(r.units);
  const y0 = r.start.slice(0, 4), y1 = r.end.slice(0, 4);
  const tv = r.typical_vs_detective;
  const ann = c.annual_years.map((y, i) => ({ y, a: c.annual_anomalies[i] })).filter((d) => d.a != null);
  const hi = ann.reduce((a, b) => (b.a > a.a ? b : a), ann[0]);
  const lo = ann.reduce((a, b) => (b.a < a.a ? b : a), ann[0]);
  const last10 = ann.slice(-10).filter((d) => d.a > 0).length;
  const neff = Math.max(1, Math.round(r.ols_neff.n_eff));
  const tone = dirTone(v.id, r.sen_slope_per_decade);
  const steps: Step[] = [
    {
      stage: "raw", kicker: "The raw record", title: "Every month, as measured",
      text: <p>{c.dates.length} monthly averages, {y0} to {y1}, from {v.source}. {v.plain}</p>,
      stats: [["Months", c.dates.length], ["Seasonal swing", `about ${plain(r.seasonal_amplitude)} ${u}`], ["Average", r.mean != null ? `${plain(r.mean, 1)} ${u}` : "—"]],
    },
    {
      stage: "anom", kicker: "Remove the seasons", title: "Take the seasons away",
      text: <p>Each month minus its usual value for that time of year. What is left, the <b>anomaly</b>, is where a trend would hide. Above zero: higher than usual.</p>,
      stats: [["Stickiness (lag-1)", r.ols_neff.lag1_autocorr.toFixed(2)], ["What that means", r.ols_neff.lag1_autocorr > 0.2 ? "an unusual month tends to be followed by another" : "months are close to independent"]],
    },
    {
      stage: "trend", kicker: "Fit the trend", title: "Draw the line",
      text: <p>Sen's slope: the middle of every pair-wise slope, so a single odd year can't drag it. The shaded fan is the 95% range of the rate.</p>,
      stats: [
        ["Rate", <strong className={`num t-${tone}`}>{signed(r.sen_slope_per_decade)} {u}<small>/decade</small></strong>],
        ["95% range", `${signed(r.sen_ci95_per_decade[0])} to ${signed(r.sen_ci95_per_decade[1])}`],
        ["Change so far", `about ${signed(r.total_change)} ${u} since ${y0}`],
      ],
    },
    {
      stage: "years", kicker: "Year by year", title: "One bar per year",
      text: <p>Each bar is a whole year compared with the {Math.round(r.record_years)}-year average. Months average out; the drift is easier to see.</p>,
      stats: [
        ["Highest year", hi ? `${hi.y}, ${signed(hi.a)} ${u}` : "—"],
        ["Lowest year", lo ? `${lo.y}, ${signed(lo.a)} ${u}` : "—"],
        ["Last 10 years", `${last10} of 10 above average`],
      ],
    },
    {
      stage: "chance", kicker: "Could it be luck?", title: "Could it be chance?",
      text: <p>Natural ups and downs can draw a line too. Because neighbouring months stick together, {c.dates.length} months carry the evidence of only about <b>{neff}</b> independent ones. Both of our tests are corrected for that.</p>,
      stats: [
        ["Mann-Kendall (corrected)", pText(r.mk_hamed_rao.p)],
        ["Least squares (corrected)", pText(r.ols_neff.p)],
        ["A typical analysis says", <span className={tv.outcome === "fooled" ? "warn" : undefined}>{tv.typical_says}</span>],
      ],
      extra: <><Dots n={c.dates.length} k={neff} /><p className="note">Each square is one month; the {neff} filled ones are what the record is really worth. {tv.note}</p></>,
    },
  ];
  if (replayHeadline) {
    steps.push({
      stage: "replay", kicker: "When it became clear", title: "When did we know?",
      text: <p>We replay the record, stopping it at every year in turn. The lower the line, the less likely the trend is luck.</p>,
      stats: [["Replay", replayHeadline]],
    });
  }
  steps.push({
    stage: "verdict", kicker: "The verdict", title: LABELS[r.verdict.label],
    text: <p className="big-line">{r.verdict.headline}</p>,
    stats: [
      ...(r.robustness ? [["Years chosen", <><span className={`chip ${r.robustness.robust === false ? "warn" : ""}`}>{r.robustness.robust === false ? "Fragile" : r.robustness.robust ? "Robust" : "Untested"}</span> {r.robustness.headline.replace(/^(Robust|Fragile)[:,]?\s*(.)/i, (_, _w, ch: string) => ch.toUpperCase())}</>] as [string, ReactNode]] : []),
      ...(r.vs_world ? [["The planet", r.vs_world.headline] as [string, ReactNode]] : []),
      ...(r.coverage ? [["Record", r.coverage.headline] as [string, ReactNode]] : []),
    ],
    extra: (
      <>
        {r.years_to_detect != null && r.verdict.label !== "strong" && <YearsBar need={r.years_to_detect} have={r.record_years} />}
        {r.verdict.label === "not_yet" && <p className="note">If today's rate is real and continues. A guide to scale, not a forecast.</p>}
        {v.caveat && <p className="note caveat">{v.caveat}</p>}
      </>
    ),
  });
  return steps;
}
