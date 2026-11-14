import { useEffect, useState, type CSSProperties } from "react";
import { api, badgeOf, examples, type Box, type Report, type ReportItem } from "./api";
import { Reveal } from "./Chart";
import { LABELS, boxText, dirTone, placeName, sameBox, short, signed } from "./lib";

/** The 95% range drawn to scale around zero: a range that clears zero is a proven direction. */
function Interval({ it }: { it: ReportItem }) {
  const [lo, hi] = it.ci95;
  const m = Math.max(Math.abs(lo), Math.abs(hi), Math.abs(it.slope_per_decade)) * 1.1 || 1;
  const X = (v: number) => 50 + (v / m) * 50;
  const tone = dirTone(it.id, it.slope_per_decade);
  return (
    <svg className="interval" viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden>
      <line className="iv-zero" x1="50" x2="50" y1="0" y2="12" />
      <rect className={`iv-range t-${tone}`} x={X(lo)} width={Math.max(X(hi) - X(lo), 0.6)} y="4" height="4" />
      <rect className={`iv-mid t-${tone}`} x={X(it.slope_per_decade) - 0.6} width="1.2" y="1" height="10" />
    </svg>
  );
}

export function ReportView({ box, onOpen }: { box: Box; onOpen: (varId: string) => void }) {
  const isDefault = sameBox(box, examples.report.box);
  const [data, setData] = useState<Report | null>(isDefault ? examples.report : null);
  const [error, setError] = useState<string | null>(null);
  const [secs, setSecs] = useState(0);

  useEffect(() => {
    let live = true;
    setError(null);
    setSecs(0);
    const t = setInterval(() => setSecs((s) => s + 1), 1000);
    api.report(box)
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => clearInterval(t));
    return () => { live = false; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [box.join()]);

  const ready = data && sameBox(data.box, box);
  return (
    <main className="sheet report" aria-busy={!ready}>
      <section className="frame hero hero-sm">
        <div className="bar-top">
          <span className="tag">[REPORT CARD] {placeName(box)}</span>
          <span className="tag" role="status">
            {error ? <span className="error">{error}</span>
              : ready ? `[${data.groups.reduce((n, g) => n + g.items.length, 0)} NASA records] ${boxText(box)}` : `[LIVE] checking every NASA record for this place: the first time takes about 20 s (${secs} s)…`}
          </span>
        </div>
        <h1 className="hero-line">Everything measured in {placeName(box)}. <span className="hl">What's really changing?</span></h1>
        {ready && <p className="lede">{data.summary}</p>}
      </section>
      {ready && (
        <>
          {data.groups.map((g, gi) => g.items.length > 0 && (
            <Reveal key={g.key} className="frame sec rgroup" aria-labelledby={`g-${g.key}`}>
              <h2 id={`g-${g.key}`} className="sec-title"><span className="tag">[{String(gi + 1).padStart(2, "0")}]</span>{g.title} <span className="count">{g.items.length}</span></h2>
              <div className="rtable" role="table">
                <div className="rrow rhead" role="row">
                  <span role="columnheader">Variable</span>
                  <span role="columnheader">Change per decade, 95% range</span>
                  <span role="columnheader">Verdict</span>
                  <span role="columnheader">A typical analysis</span>
                  <span role="columnheader">Second witness</span>
                </div>
                {g.items.map((it, i) => {
                  const b = it.second_witness ? badgeOf(it.second_witness) : null;
                  return (
                    <button key={it.id} className={`rrow v-${it.label}`} style={{ "--n": i } as CSSProperties} role="row" onClick={() => onOpen(it.id)} aria-label={`${it.name}: ${LABELS[it.label]}. Open the case.`}>
                      <span role="cell" className="rname">{it.name} <span aria-hidden className="go">→</span></span>
                      <span role="cell" className="rrate">
                        <span className={`num t-${dirTone(it.id, it.slope_per_decade)}`}>{signed(it.slope_per_decade)} {short(it.units)}</span>
                        <span className="rci">{signed(it.ci95[0])} to {signed(it.ci95[1])}</span>
                        <Interval it={it} />
                      </span>
                      <span role="cell" className="rverdict">
                        <span className={`verdict v-${it.label}`}><span className="verdict-swatch" aria-hidden />{LABELS[it.label]}</span>
                        {it.more_years_needed != null && <span className="rmore">about {Math.round(it.more_years_needed)} more years</span>}
                        {["could_be_instrument", "doubt"].includes(it.instrument_check?.status ?? "") && <span className="rmore warn">⚠ {it.instrument_check!.headline}</span>}
                      </span>
                      <span role="cell" className={`rtyp${it.typical_outcome === "fooled" ? " fooled" : ""}`}>{it.typical_note}</span>
                      <span role="cell">{b ? <span className={`badge b-${b}`}>{{ confirmed: "Confirmed", consistent: "Consistent", caution: "Caution" }[b]}</span> : <span className="muted">—</span>}</span>
                    </button>
                  );
                })}
              </div>
            </Reveal>
          ))}
          {data.errors.length > 0 && <p className="note pad">Could not check: {data.errors.map((e) => e.name).join(", ")}.</p>}
        </>
      )}
    </main>
  );
}
