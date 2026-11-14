// API client. AI-use note: drafted with Claude (Anthropic) during the hackathon.
import exAnalyse from "../../docs/examples/analyse_T2M_lincolnshire.json";
import exReport from "../../docs/examples/report_card_lincolnshire.json";
import exMap from "../../docs/examples/map_GWETROOT_england.json";
import exValidation from "../../docs/examples/validation.json";
import exVariables from "../../docs/examples/variables.json";

export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export type Box = [number, number, number, number]; // lat_min, lat_max, lon_min, lon_max
export type Label = "strong" | "some" | "mixed" | "not_yet" | "none";
export type Badge = "confirmed" | "consistent" | "caution";

export interface Variable {
  id: string; name: string; units: string; source: string; plain: string; tags: string[]; caveat: string;
}
export interface Witness {
  available: boolean; name?: string; badge?: Badge; agrees?: boolean; independence?: string; note: string;
  monthly_correlation?: number; period?: string; nasa_verdict?: Label; witness_verdict?: Label;
}
export interface Analysis {
  variable: Variable; box: Box; n_cells: number; citation: string; second_witness: Witness;
  result: {
    start: string; end: string; units: string; seasonal_amplitude: number;
    sen_slope_per_decade: number; sen_ci95_per_decade: [number, number]; slope_method: string;
    total_change: number; years_to_detect: number | null; record_years: number;
    mk_hamed_rao: { p: number }; ols_neff: { p: number; lag1_autocorr: number; n_eff: number };
    typical_vs_detective: { typical_says: string; outcome: "fooled" | "agree_trend" | "missed" | "agree_none"; note: string };
    verdict: { label: Label; headline: string; direction: string; tests_agree: boolean };
  };
  chart: {
    dates: string[]; values: number[]; anomalies: number[]; trend_line: [number, number];
    annual_years: number[]; annual_anomalies: number[];
  };
}
export interface ReportItem {
  id: string; name: string; units: string; source: string; label: Label; headline: string; direction: string;
  slope_per_decade: number; ci95: [number, number]; total_change: number; period: string;
  years_to_detect: number | null; more_years_needed: number | null;
  typical_outcome: string; typical_note: string; second_witness?: Witness;
}
export interface Report {
  box: Box; summary: string; fooled_count: number;
  groups: { key: string; title: string; items: ReportItem[] }[];
  errors: { id: string; name: string; error: string }[];
}
export interface MapCell {
  id: number; lat: number; lon: number; slope_per_decade: number | null; p: number | null;
  significant_fdr: boolean; significant_raw: boolean; significant_typical: boolean;
}
export interface TrendMap {
  variable: Variable; cells: MapCell[];
  summary: {
    n_cells: number; n_significant_typical: number; n_significant_raw: number; n_significant_fdr: number;
    n_rising_fdr: number; n_falling_fdr: number; fdr_q: number; story: string;
  };
}
export interface Validation {
  validation: { phis: number[]; false_alarm_rate: Record<string, number[]>; n_sims: number };
  validation_power: { trends_per_decade: number[]; detection_rate: Record<string, number[]>; n_sims: number };
}

const q = (b: Box) => `lat_min=${b[0]}&lat_max=${b[1]}&lon_min=${b[2]}&lon_max=${b[3]}`;

async function get<T>(path: string): Promise<T> {
  let r: Response;
  try {
    r = await fetch(API + path);
  } catch {
    throw new Error("Can't reach the Detective's server. It may be waking up: try again in 30 seconds.");
  }
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    throw new Error(body?.detail ?? `The server answered ${r.status}.`);
  }
  return r.json();
}

export const api = {
  variables: () => get<{ variables: Variable[] }>("/api/variables"),
  analyse: (v: string, b: Box) => get<Analysis>(`/api/analyse?var=${v}&${q(b)}`),
  report: (b: Box) => get<Report>(`/api/report-card?${q(b)}`),
  map: (v: string, b: Box) => get<TrendMap>(`/api/map?var=${v}&${q(b)}`),
  validation: () => get<Validation>("/api/validation"),
};

// ponytail: real saved API responses, shown instantly while the live server answers (or sleeps).
export const examples = {
  analyse: exAnalyse as unknown as Analysis,
  report: exReport as unknown as Report,
  map: exMap as unknown as TrendMap,
  validation: exValidation as unknown as Validation,
  variables: (exVariables as unknown as { variables: Variable[] }).variables,
};

/** Second-witness badge; older servers send only `agrees`. */
export function badgeOf(w: Witness): Badge | null {
  if (!w.available) return null;
  if (w.badge) return w.badge;
  if (!w.agrees) return "caution";
  const proven = (l?: Label) => l === "strong" || l === "some";
  return w.independence === "independent" && proven(w.nasa_verdict) && proven(w.witness_verdict) ? "confirmed" : "consistent";
}
