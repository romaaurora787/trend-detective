import { useEffect, useState } from "react";
import { api, badgeOf, examples, type Analysis, type Box } from "./api";
import { Panel, decYear } from "./Chart";
import { LABELS, dirTone, pText, placeName, plain, sameBox, signed } from "./lib";

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
        <span>{Math.round(have)} years of data so far</span>
        <span>{short ? `a trend this size shows after about ${Math.round(need)} years` : `about ${Math.round(need - have)} more needed`}</span>
      </div>
    </div>
  );
}

export function CaseView({ varId, box, onReport }: { varId: string; box: Box; onReport: () => void }) {
  const { data, loading, error, stale } = useAnalysis(varId, box);
  const [hover, setHover] = useState<string | null>(null);

  if (!data) {
    return (
      <main className="page" aria-busy={loading}>
        <p className="status" role="status">{error ?? "Fetching 45 years of NASA monthly data for this place…"}</p>
      </main>
    );
  }

  const { result: r, chart, variable: v } = data;
  const tone = dirTone(v.id, r.sen_slope_per_decade);
  const xs = chart.dates.map(decYear);
  const [t0, t1] = [xs[0], xs[xs.length - 1]];
  const label = r.verdict.label;
  const w = data.second_witness;
  const badge = badgeOf(w);
  const tv = r.typical_vs_detective;
  const lit = (k: string) => (hover == null ? null : hover === k);
  const hov = (k: string) => ({ onMouseEnter: () => setHover(k), onMouseLeave: () => setHover(null), onFocus: () => setHover(k), onBlur: () => setHover(null), tabIndex: 0 });
  const years = `${r.start.slice(0, 4)}–${r.end.slice(0, 4)}`;

  return (
    <main className={`page case${stale || loading ? " is-loading" : ""}`} aria-busy={loading}>
      <header className="fig-head">
        <h1><span className="fig-no">Fig. 1</span> {v.name}, {placeName(data.box)}, {years}</h1>
        <p className="status" role="status">
          {error ? <span className="error">{error}</span> : loading ? "Checking the live NASA record…" : `Average of ${data.n_cells} NASA grid cell${data.n_cells === 1 ? "" : "s"} · ${v.source}`}
        </p>
      </header>

      <div className="plate">
        <div className="plate-panels">
          <Panel letter="a" lit={lit("a")} yLabel={r.units} series={[{ xs, ys: chart.values, cls: "s-raw" }]} xDomain={[t0, t1]}
            title={<>Every month as measured. The seasons swing by about {plain(r.seasonal_amplitude)} {r.units}; any trend hides inside that.</>} />
          <Panel letter="b" lit={lit("b")} yLabel={r.units} zero height={200} xDomain={[t0, t1]}
            series={[
              { xs, ys: chart.anomalies, cls: "s-anom" },
              { xs: [t0, t1], ys: chart.trend_line, cls: `s-trend t-${tone}` },
            ]}
            title={<>Seasons removed: each month minus its usual value. The line is the trend (Sen's slope).</>} />
          <Panel letter="c" lit={lit("c")} yLabel={r.units} zero height={120}
            series={[{ xs: chart.annual_years, ys: chart.annual_anomalies, cls: `s-year ${dirTone(v.id, 1) === "rise" ? "up-rise" : "up-fall"}`, kind: "bar" }]}
            title={<>Each year compared with the 45-year average.</>} />
        </div>

        <aside className="legend" aria-label="Verdict">
          <p className={`verdict v-${label}`}><span className="verdict-swatch" aria-hidden />{LABELS[label]}</p>
          <p className="headline" {...hov("b")}>{r.verdict.headline}</p>
          <dl className="facts">
            <div {...hov("b")}>
              <dt>Rate</dt>
              <dd><strong className={`n t-${tone}`}>{signed(r.sen_slope_per_decade)} {r.units}</strong> per decade, 95% range {signed(r.sen_ci95_per_decade[0])} to {signed(r.sen_ci95_per_decade[1])}</dd>
            </div>
            <div {...hov("c")}>
              <dt>So far</dt>
              <dd>about <strong className="n">{signed(r.total_change)} {r.units}</strong> since {r.start.slice(0, 4)}</dd>
            </div>
            <div {...hov("b")}>
              <dt>Tests</dt>
              <dd>{r.verdict.tests_agree ? "Both tests agree" : "The two tests disagree"} ({pText(r.mk_hamed_rao.p)} and {pText(r.ols_neff.p)})</dd>
            </div>
          </dl>

          <section className="block" aria-labelledby="tvd">
            <h2 id="tvd">Typical analysis vs the Detective</h2>
            <div className={`versus o-${tv.outcome}`}>
              <div>
                <h3>A typical analysis says</h3>
                <p>{tv.typical_says}</p>
              </div>
              <div>
                <h3>The Detective says</h3>
                <p>{LABELS[label]}.</p>
              </div>
            </div>
            <p className="note">{tv.note}</p>
          </section>

          <section className="block" aria-labelledby="ytk">
            <h2 id="ytk">How long until we would know</h2>
            <YearsBar need={r.years_to_detect} have={r.record_years} />
            {label === "not_yet" && <p className="note">If today's rate is real and continues. A guide to scale, not a forecast.</p>}
          </section>

          <section className="block" aria-labelledby="sw">
            <h2 id="sw">Second witness</h2>
            {badge ? (
              <>
                <p className={`badge b-${badge}`}>{{ confirmed: "Confirmed", consistent: "Consistent", caution: "Caution" }[badge]}<span> · {w.name}</span></p>
                <p className="note">{w.note}{w.monthly_correlation != null && ` Month-to-month agreement r = ${w.monthly_correlation.toFixed(2)}.`}</p>
              </>
            ) : (
              <p className="note">No independent record for this variable and place yet.</p>
            )}
          </section>

          <details className="block details">
            <summary>The numbers behind it</summary>
            <dl className="facts small">
              <div><dt>Mann-Kendall, Hamed-Rao corrected</dt><dd>{pText(r.mk_hamed_rao.p)}</dd></div>
              <div><dt>Least squares, effective sample size</dt><dd>{pText(r.ols_neff.p)}, n_eff = {Math.round(r.ols_neff.n_eff)} of {chart.dates.length} months</dd></div>
              <div><dt>Month-to-month stickiness (lag-1)</dt><dd>{r.ols_neff.lag1_autocorr.toFixed(2)}</dd></div>
              <div><dt>Slope method</dt><dd>{r.slope_method === "sen" ? "Sen's slope" : "Corrected least squares (mostly-zero variable)"}</dd></div>
            </dl>
          </details>
          {v.caveat && <p className="note caveat">{v.caveat}</p>}
          <button className="btn" onClick={onReport}>See all 15 variables for {placeName(data.box)}</button>
        </aside>
      </div>
      <p className="cite">{data.citation}. Trend is not cause: we detect change, we do not explain it.</p>
    </main>
  );
}
