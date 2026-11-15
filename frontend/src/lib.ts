import type { Box, Label } from "./api";

export interface Place { name: string; box: Box; note?: string }

// Boxes match backend/scripts/scan_cases.py so the numbers agree with docs/demo_scan.md.
export const PLACES: Place[] = [
  { name: "Lincolnshire", box: [52.6, 53.7, -1.0, 0.4], note: "Our home case" },
  { name: "England & Wales", box: [50.0, 55.5, -6.0, 2.0] },
  { name: "Wash estuary", box: [52.7, 53.2, 0.0, 0.6] },
  { name: "London", box: [51.2, 51.8, -0.6, 0.4] },
  { name: "Svalbard (Arctic)", box: [77.0, 80.0, 10.0, 20.0] },
  { name: "East Africa", box: [-5.0, 5.0, 33.0, 43.0] },
  { name: "Sahel (Niger/Mali)", box: [12.0, 16.0, -5.0, 5.0] },
  { name: "Delhi", box: [28.0, 29.5, 76.5, 78.0] },
  { name: "Beijing", box: [39.0, 41.0, 115.5, 117.5] },
  { name: "Amazon (Rondônia)", box: [-12.0, -8.0, -66.0, -60.0] },
  { name: "Spain (Iberia)", box: [37.0, 42.0, -7.0, -1.0] },
];

export const sameBox = (a: Box, b: Box) => a.every((v, i) => Math.abs(v - b[i]) < 1e-6);

// ponytail: names of searched places, keyed by box; seeded from the URL's &name= on load.
const NAMED = new Map<string, string>();
export const nameBox = (box: Box, name: string) => NAMED.set(box.join(), name);

export function placeName(box: Box): string {
  const p = PLACES.find((p) => sameBox(p.box, box));
  if (p) return p.name;
  const n = NAMED.get(box.join());
  if (n) return n;
  const ns = (v: number) => `${Math.abs(v).toFixed(1)}°${v >= 0 ? "N" : "S"}`;
  const ew = (v: number) => `${Math.abs(v).toFixed(1)}°${v >= 0 ? "E" : "W"}`;
  return `${ns((box[0] + box[1]) / 2)}, ${ew((box[2] + box[3]) / 2)}`;
}

export function boxText(b: Box): string {
  const ns = (v: number) => `${Math.abs(v)}°${v >= 0 ? "N" : "S"}`;
  const ew = (v: number) => `${Math.abs(v)}°${v >= 0 ? "E" : "W"}`;
  return `${ns(b[0])} to ${ns(b[1])}, ${ew(b[2])} to ${ew(b[3])}`;
}

/** Two significant figures, explicit sign, real minus sign. */
export function signed(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return "—";
  const v = Number(x.toPrecision(2));
  const s = Math.abs(v).toString();
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : "0";
}

/** "fraction (0 dry – 1 saturated)" → "fraction", for axis labels. */
export const short = (u: string) => u.split(" (")[0];

export const plain = (x: number, d = 0) => x.toFixed(d).replace("-", "−");

export function pText(p: number | null | undefined): string {
  if (p == null || !Number.isFinite(p)) return "—";
  if (p < 0.0001) return "p < 0.0001";
  return `p = ${p < 0.01 ? p.toPrecision(1) : p.toFixed(2)}`;
}

/** A p-value in words: how often luck alone would give a trend at least this strong. */
export function luckText(p: number | null | undefined): string {
  if (p == null || !Number.isFinite(p)) return "—";
  if (p < 0.001) return "less than 1 in 1,000";
  if (p < 0.01) return "less than 1 in 100";
  if (p < 0.05) return "less than 1 in 20";
  return `about 1 in ${Math.max(1, Math.round(1 / p))}: could easily be luck`;
}

export const LABELS: Record<Label, string> = {
  strong: "Strong evidence",
  some: "Some evidence",
  mixed: "Mixed",
  not_yet: "Not significant yet",
  none: "No trend detected",
};

/** Wetter is "good-blue" for these, so the diverging colours flip. */
const WET = new Set(["PRECTOTCORR", "GWETTOP", "GWETROOT", "QV2M", "RH2M", "EVLAND"]);
export const risingIsBlue = (varId: string) => WET.has(varId);

/** Colour role for a change in this variable. */
export function dirTone(varId: string, slope: number): "rise" | "fall" {
  const up = slope >= 0;
  return up !== risingIsBlue(varId) ? "rise" : "fall";
}

/** Focus the place search; on phones the controls are folded, so open them first. */
export function focusSearch() {
  document.querySelector<HTMLButtonElement>('.ctrl-toggle[aria-expanded="false"]')?.click();
  requestAnimationFrame(() => { const i = document.querySelector<HTMLInputElement>(".search input"); i?.scrollIntoView({ block: "center" }); i?.focus(); });
}
