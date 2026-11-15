// First-visit guide: three moves that show the whole site. Shown once, reopenable from the header.
// AI-use note: drafted with Claude (Anthropic).
import type { CSSProperties } from "react";
import { Reveal } from "./Chart";
import { focusSearch } from "./lib";

const KEY = "td-guide";
export const guideSeen = () => { try { return localStorage.getItem(KEY) === "seen"; } catch { return false; } };
const markSeen = () => { try { localStorage.setItem(KEY, "seen"); } catch { /* private mode */ } };

export function Guide({ onClose }: { onClose: () => void }) {
  const close = () => { markSeen(); onClose(); };
  const steps: { tag: string; title: string; text: string; act: string; href?: string; run?: () => void }[] = [
    { tag: "Watch one case", title: "Is Lincolnshire really warming?",
      text: "Scroll seven steps, from 45 years of raw NASA data to a verdict. We try to break our own answer on the way.",
      act: "Start the case", href: "#/case" },
    { tag: "Try your own place", title: "Any town, any of 15 variables",
      text: "Type a town in Search, pick a demo case, or draw a box on a map. The same checks run on whatever you choose.",
      act: "Search a place", run: focusSearch },
    { tag: "Zoom out", title: "The whole planet on trial",
      text: "Every 2° land square tested for temperature and rain, plus 111 places for 19 variables. See where change is proven, where a typical test is fooled, and where it could go by 2050.",
      act: "Open the world", href: "#/world" },
  ];
  return (
    <div className="sheet guide-wrap">
      <Reveal className="frame guide" aria-label="How to use this site">
        <div className="guide-head">
          <p className="tag">[START HERE] Your first investigation<span className="guide-time"> · about 3 minutes</span></p>
          <button className="btn ghost" onClick={close}>Got it<span className="guide-time">, close</span></button>
        </div>
        <ol className="guide-steps">
          {steps.map((s, i) => (
            <li key={s.tag} style={{ "--n": i } as CSSProperties}>
              <p className="tag">[{String(i + 1).padStart(2, "0")}] {s.tag}</p>
              <strong>{s.title}</strong>
              <p>{s.text}</p>
              {s.href
                ? <a className="linkish" href={s.href} onClick={close}>{s.act} →</a>
                : <button className="linkish" onClick={() => { close(); setTimeout(s.run!, 0); }}>{s.act} →</button>}
            </li>
          ))}
        </ol>
        <p className="guide-apart"><a className="linkish" href="#/methods" onClick={close}><span className="tag">[JUDGING?]</span> What sets it apart, in six points →</a></p>
        <p className="note guide-foot">Words too technical, or not enough? Use <b>Detail</b> in the header: Plain keeps it in everyday words, Detailed shows every test and p-value. Reopen this guide any time with <b>Guide</b>.</p>
      </Reveal>
    </div>
  );
}
