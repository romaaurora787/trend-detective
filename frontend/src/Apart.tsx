// "What sets it apart": the six things this tool puts together, each with a live number and a link to see it.
// Wording rule (shared log): "all in one place", never "only us". Numbers come from /api/world, /api/globe, /api/validation.
// AI-use note: drafted with Claude (Anthropic).
import { useEffect, useState, type CSSProperties } from "react";
import exWorld from "../../docs/examples/world.json";
import { api, type Validation } from "./api";
import { Reveal } from "./Chart";

type V = { id: string; n_typical: number; n_fooled: number; n_points: number; n_proven: number; n_proven_after_alibi: number };
type Land = { cells: number; luck_typical: number; luck_ours: number };
const pc = (x: number) => `${Math.round(x * 100)}%`;
const BASE = ["Any place", "Corrected tests", "False-discovery maps", "World globe", "Second NASA record", "Sudden-jump test", "El Niño removed", "Two places compared", "Plain & detailed", "Citations"];

export function Apart({ v }: { v: Validation }) {
  const [vars, setVars] = useState<V[]>((exWorld as unknown as { variables: V[] }).variables);
  const [land, setLand] = useState<Land | null>(null);
  useEffect(() => {
    api.world<{ variables: V[] }>().then((d) => d.variables && setVars(d.variables)).catch(() => {});
    api.globe<{ counts: { land: Land } }>("T2M").then((d) => setLand(d.counts.land)).catch(() => {});
  }, []);
  const cl = vars.find((x) => x.id === "CLOUD_AMT");
  const typ = vars.reduce((a, x) => a + x.n_typical, 0), fool = vars.reduce((a, x) => a + x.n_fooled, 0), checks = vars.reduce((a, x) => a + x.n_points, 0);
  const fa = v.validation, i5 = fa.phis.indexOf(0.5), naive = fa.false_alarm_rate.naive_ols_anomalies;
  const pw = v.validation_power, i3 = pw.trends_per_decade.indexOf(0.3);
  const six: [string, string, string, string][] = [
    ["Instrument check", cl ? `${cl.n_proven - cl.n_proven_after_alibi} of ${cl.n_proven} proven cloud trends could be the instrument, not the sky.` : "",
      "Documented changes in NASA's data sources are tested: sunlight, cloud and heat radiation at 2001, aerosols at 2014, deep soil at MERRA-2's stream joins, rain at 1987.",
      "#/case?var=CLOUD_AMT&box=44,46,-91,-89&name=Central%20Wisconsin"],
    ["False alarms measured", `${pc(fa.false_alarm_rate.ours_verdict[i5])} false alarms, against ${pc(naive[i5])}–${pc(naive[naive.length - 1])} for a typical test.`,
      `On synthetic monthly data with a known answer, while ${i3 >= 0 ? `${(pw.detection_rate.ours_verdict[i3] * 100).toFixed(1)}%` : "most"} of real 0.3-per-decade trends are still caught.`, "#/methods"],
    ["Witnesses, counted for independence", "Lincolnshire: 4 of 4 other records agree. Delhi: the thermometers disagree with the model, and we say so.",
      "Station thermometers, rain gauges, GPCP, IMERG, ESA CCI, GLDAS, GRACE and ERA5, each labelled for how independent it is of NASA's record.",
      "#/case?var=T2M&box=28,29.5,76.5,78&name=Delhi"],
    ["Four ocean cycles removed", "El Niño, NAO, Indian Ocean Dipole and PDO, together.",
      "With a careful flag when a change only appears once the cycles are removed.", "#/case"],
    ["The world on trial", typ ? `${pc(fool / typ)} of typical trend claims don't hold, across ${checks.toLocaleString("en-GB")} checks.` : "",
      land ? `A luck test on ${land.cells.toLocaleString("en-GB")} land squares: on shuffled records a typical test is fooled ${pc(land.luck_typical / land.cells)} of the time, ours ${pc(land.luck_ours / land.cells)}.` : "A luck test on every 2° land square: how often a typical test is fooled by shuffled records.",
      "#/world"],
    ["Around 2050, three what-ifs", "Our trend drawn on, 7 CMIP6 climate models and 3 IPCC emission paths, side by side.",
      "It refuses to draw a straight line when the change is one sudden jump.", "#/case"],
  ];
  return (
    <Reveal className="frame sec apart" aria-label="What sets it apart">
      <h2 className="sec-title"><span className="tag">[00]</span>What sets it apart</h2>
      <p className="apart-base"><span className="tag">In the strongest entries, and here too</span>{BASE.map((b) => <span key={b} className="apart-tick">✓ {b}</span>)}</p>
      <p className="big-line pad">On top of that, six things in one tool:</p>
      <ol className="apart-six">
        {six.map(([tag, head, text, href], i) => (
          <li key={tag} style={{ "--n": i } as CSSProperties}>
            <p className="tag">[{String(i + 1).padStart(2, "0")}] {tag}</p>
            <strong>{head}</strong>
            <p>{text}</p>
            <a className="linkish" href={href}>See it →</a>
          </li>
        ))}
      </ol>
    </Reveal>
  );
}
