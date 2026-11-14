import { useEffect, useState } from "react";
import { api, badgeOf, examples, type Box, type Report, type ReportItem } from "./api";
import { LABELS, boxText, dirTone, placeName, sameBox, signed } from "./lib";

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
    <main className="page report" aria-busy={!ready}>
      <header className="fig-head">
        <h1><span className="fig-no">Table 1</span> Report card: {placeName(box)}</h1>
        <p className="status" role="status">
          {error ? <span className="error">{error}</span>
            : ready ? `${boxText(box)} · 15 NASA variables, 1981–2025` : `Running all 15 checks for this place: the first time takes about 20 seconds (${secs} s)…`}
        </p>
      </header>
      {ready && (
        <>
          <p className="summary">{data.summary}</p>
          {data.groups.map((g) => g.items.length > 0 && (
            <section key={g.key} className="rgroup" aria-labelledby={`g-${g.key}`}>
              <h2 id={`g-${g.key}`}>{g.title} <span className="count">{g.items.length}</span></h2>
              <div className="rtable" role="table">
                <div className="rrow rhead" role="row">
                  <span role="columnheader">Variable</span>
                  <span role="columnheader">Change per decade, 95% range</span>
                  <span role="columnheader">Verdict</span>
                  <span role="columnheader">A typical analysis</span>
                  <span role="columnheader">Second witness</span>
                </div>
                {g.items.map((it) => {
                  const b = it.second_witness ? badgeOf(it.second_witness) : null;
                  return (
                    <button key={it.id} className={`rrow v-${it.label}`} role="row" onClick={() => onOpen(it.id)} aria-label={`${it.name}: ${LABELS[it.label]}. Open the case.`}>
                      <span role="cell" className="rname">{it.name}</span>
                      <span role="cell" className="rrate">
                        <span className="n">{signed(it.slope_per_decade)} {it.units}</span>
                        <span className="rci">{signed(it.ci95[0])} to {signed(it.ci95[1])}</span>
                        <Interval it={it} />
                      </span>
                      <span role="cell" className="rverdict">
                        <span className={`verdict v-${it.label}`}><span className="verdict-swatch" aria-hidden />{LABELS[it.label]}</span>
                        {it.more_years_needed != null && <span className="rmore">about {Math.round(it.more_years_needed)} more years</span>}
                      </span>
                      <span role="cell" className={`rtyp${it.typical_outcome === "fooled" ? " fooled" : ""}`}>{it.typical_note}</span>
                      <span role="cell">{b ? <span className={`badge b-${b}`}>{{ confirmed: "Confirmed", consistent: "Consistent", caution: "Caution" }[b]}</span> : <span className="muted">—</span>}</span>
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
          {data.errors.length > 0 && <p className="note">Could not check: {data.errors.map((e) => e.name).join(", ")}.</p>}
        </>
      )}
    </main>
  );
}
