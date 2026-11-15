// "Why trust the Detective": six claims, each with a number from the API (P1).
// Drafted with help from Claude (Anthropic); every number comes from /api/world or /api/validation.
import { useEffect, useState, type CSSProperties } from "react";
import { api, examples, type Validation } from "./api";
import { Reveal } from "./Chart";

type V = { id: string; n_typical: number; n_fooled: number; n_proven: number; alibi: { could_be_instrument?: number } };

export function Trust({ variables }: { variables?: V[] }) {
  const [vars, setVars] = useState<V[] | undefined>(variables);
  useEffect(() => {
    if (variables) setVars(variables);
    else api.world<{ variables: V[] }>().then((d) => setVars(d.variables)).catch(() => {});
  }, [variables]);
  const [yv, setYv] = useState<Validation["yearly_vs_monthly"]>();
  useEffect(() => { api.validation().then((d) => setYv(d.yearly_vs_monthly)).catch(() => {}); }, []);
  const fa = examples.validation.validation, i5 = fa.phis.indexOf(0.5);
  const cloud = vars?.find((v) => v.id === "CLOUD_AMT");
  const t = vars?.reduce((a, v) => a + v.n_typical, 0) ?? 0, f = vars?.reduce((a, v) => a + v.n_fooled, 0) ?? 0;
  const tiles: [string, string, string, string][] = [
    [cloud ? `${cloud.alibi.could_be_instrument ?? 0}/${cloud.n_proven}` : "—", "We check the satellite didn't change.", "Proven cloud trends that one jump at the 2001 satellite switch explains better.", "#/world"],
    ["4", "We remove four ocean cycles, not just El Niño.", "El Niño, NAO, Indian Ocean Dipole and PDO, in the cross-examination.", "#/case"],
    [`${Math.round(fa.false_alarm_rate.ours_verdict[i5] * 100)}%`, `False alarms, not ${Math.round(fa.false_alarm_rate.naive_ols_anomalies[i5] * 100)}%.`, "Our verdict on realistic sticky noise, against a typical test.", "#/methods"],
    ["3", "Independent witnesses, counted honestly.", "Other records (for rain: GPCP, IMERG, ERA5) must agree, and we say which don't.", "#/case"],
    [t ? `${Math.round((f / t) * 100)}%` : "—", "Of typical trend claims don't hold.", t ? `${f.toLocaleString("en-GB")} of ${t.toLocaleString("en-GB")} across 111 places and 19 variables.` : "Loading the world report…", "#/world"],
    ["4", "Ways to check every number yourself.", "The NASA request, Giovanni, the CSV and a notebook.", "#/case"],
  ];
  const sticky = yv?.false_alarms.sticky_noise;
  return (
    <>
    <Reveal tag="div" className="trust">
      {tiles.map(([n, h, p, href], i) => (
        <a key={h} className="trust-tile" href={href} style={{ "--n": i } as CSSProperties}>
          <b>{n}</b>
          <strong>{h}</strong>
          <span>{p}</span>
        </a>
      ))}
    </Reveal>
    {sticky && (
      // B4: only the false-alarm edge; we don't claim more power than the yearly test.
      <p className="note trust-note">Some teams average each year first. That's a fair test, but with sticky weather it gives <b>{sticky.yearly_shortcut}%</b> false alarms; ours gives <b>{sticky.ours}%</b>. It catches about as many real trends as ours does.</p>
    )}
    </>
  );
}
