// Problem → what we do → why it matters, on the home case. Numbers come from /api/world (saved copy first).
// AI-use note: drafted with Claude (Anthropic).
import { useEffect, useState, type CSSProperties } from "react";
import exWorld from "../../docs/examples/world.json";
import { api } from "./api";
import { Reveal } from "./Chart";

type V = { n_points: number; n_typical: number; n_fooled: number; n_proven: number };
const sum = (vs: V[], k: keyof V) => vs.reduce((a, v) => a + v[k], 0);
const n = (x: number) => x.toLocaleString("en-GB");

export function Impact() {
  const [vars, setVars] = useState<V[]>((exWorld as unknown as { variables: V[] }).variables);
  useEffect(() => { api.world<{ variables: V[] }>().then((d) => d.variables && setVars(d.variables)).catch(() => {}); }, []);
  const all = sum(vars, "n_points"), typ = sum(vars, "n_typical"), fool = sum(vars, "n_fooled"), proven = sum(vars, "n_proven");
  const cols: [string, string, string][] = [
    ["The problem", `A typical trend test calls ${n(typ)} of ${n(all)} NASA trends real.`,
      `${n(fool)} of them (${Math.round((fool / typ) * 100)}%) don't hold up. The test treats every month as independent, and weather is sticky: one warm month is often followed by another, so luck looks like a trend.`],
    ["What we do", `${n(proven)} survive our checks.`,
      "Two corrected tests must agree. Then a cross-examination (the 2001 satellite switch, four ocean cycles, one odd year) and other records as witnesses. Every number links back to NASA's own data."],
    ["Why it matters", "Real change, or noise someone will act on?",
      "Farmers, planners and reporters read trend maps. A false \"drying\" claim sends money and attention the wrong way; a missed one leaves people unready. We say which changes are real, how sure we are, and what 2050 could bring."],
  ];
  return (
    <Reveal className="frame impact" aria-label="Why this matters">
      {cols.map(([tag, head, text], i) => (
        <div key={tag} className="impact-col" style={{ "--n": i } as CSSProperties}>
          <p className="tag">[{String(i + 1).padStart(2, "0")}] {tag}</p>
          <strong>{head}</strong>
          <p>{text}</p>
        </div>
      ))}
    </Reveal>
  );
}
