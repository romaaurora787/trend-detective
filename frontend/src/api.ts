// API client. AI-use note: drafted with Claude (Anthropic) during the hackathon.
import exAnalyse from "../../docs/examples/analyse_T2M_lincolnshire.json";
import exReport from "../../docs/examples/report_card_lincolnshire.json";
import exMap from "../../docs/examples/map_GWETROOT_england.json";
import exValidation from "../../docs/examples/validation.json";
import exVariables from "../../docs/examples/variables.json";
import exCross from "../../docs/examples/crossexam_T2M_lincolnshire.json";
import exWitnesses from "../../docs/examples/witnesses_T2M_lincolnshire.json";

export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export type Box = [number, number, number, number]; // lat_min, lat_max, lon_min, lon_max
export type Label = "strong" | "some" | "mixed" | "not_yet" | "none";
export type Badge = "confirmed" | "consistent" | "caution";

export interface Variable {
  id: string; name: string; units: string; source: string; plain: string; tags: string[]; caveat: string;
  ready?: boolean; wait?: string;
}
export interface Witness {
  available: boolean; name?: string; badge?: Badge; agrees?: boolean; independence?: string; note: string;
  monthly_correlation?: number; period?: string; nasa_verdict?: Label; witness_verdict?: Label;
}
export interface Analysis {
  variable: Variable; box: Box; n_cells: number; citation: string; second_witness: Witness;
  result: {
    start: string; end: string; units: string; seasonal_amplitude: number; n_months?: number; mean?: number;
    sen_slope_per_decade: number; sen_ci95_per_decade: [number, number]; slope_method: string;
    total_change: number; years_to_detect: number | null; record_years: number;
    mk_hamed_rao: { p: number }; ols_neff: { p: number; lag1_autocorr: number; n_eff: number };
    typical_vs_detective: { typical_says: string; typical_slope_per_decade?: number; outcome: "fooled" | "agree_trend" | "missed" | "agree_none"; note: string };
    verdict: { label: Label; headline: string; direction: string; tests_agree: boolean };
    robustness?: { robust: boolean | null; headline: string };
    coverage?: { headline: string };
    vs_world?: { headline: string } | null;
    reproduce?: { name: string; url: string; note: string }[];
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
  instrument_check?: { status: string; headline: string };
}
export interface Report {
  box: Box; summary: string; fooled_count: number;
  groups: { key: string; title: string; items: ReportItem[] }[];
  errors: { id: string; name: string; error: string }[];
  clearest_headline?: string;
  clearest?: { id: string; name: string; clarity: number; direction: string; slope_per_decade: number; units: string; emerged_year?: number | null }[];
}
export interface MapCell {
  id: number; lat: number; lon: number; slope_per_decade: number | null; p: number | null;
  significant_fdr: boolean; significant_raw: boolean; significant_typical: boolean;
}
export interface TrendMap {
  variable: Variable; cells: MapCell[]; shuffled_control?: { headline: string };
  summary: {
    n_cells: number; n_significant_typical: number; n_significant_raw: number; n_significant_fdr: number;
    n_rising_fdr: number; n_falling_fdr: number; fdr_q: number; story: string;
  };
}
// Cross-examination: every section can come back as {error} on its own.
type Sec<T> = Partial<T> & { headline?: string; error?: string };
type Slope = { slope_per_decade: number; label: Label };
export interface CrossExam {
  score: { passed: number | null; of: number; proven: boolean; headline: string; checks?: string[]; rule_note?: string };
  alibi?: Sec<{ status: string; changes: { date: string; what: string; tested?: boolean; before?: Slope & { period: string }; after?: Slope & { period: string } }[] }>;
  el_nino?: Sec<{ status: string; how_linked?: string; before?: Slope; after?: Slope }>;
  climate_modes?: Sec<{ status: string; strongest?: string; before?: Slope; after?: Slope }>;
  leave_one_out?: Sec<{ flips: number[] }>;
  walk_forward?: Sec<{ status: string }>;
  all_windows?: Sec<{ proven_opposite: number; timeline: { end: number; p: number | null }[]; became_proven: number | null }>;
  decades?: Sec<{ state: string }>;
  seasons?: Sec<{ months: { month: string; slope_per_decade: number; proven_fdr: boolean }[] }>;
  change_point?: Sec<{ status: string; year: number | null }>;
  resolution?: Sec<{ label: string }>;
  could_overturn?: string[];
}
export interface Witnesses {
  witnesses: (Witness & { kind?: string; witness_verdict?: Label; station?: { distance_km: number } })[];
  n_agree: number; n_available: number; headline: string; credit?: string;
}
export interface PlaceHit { label: string; population: number; box: Box }
export interface Validation {
  validation: { phis: number[]; false_alarm_rate: Record<string, number[]>; n_sims: number };
  validation_power: { trends_per_decade: number[]; detection_rate: Record<string, number[]>; n_sims: number };
  yearly_vs_monthly?: { headline: string; false_alarms: Record<"mild_noise" | "sticky_noise", { yearly_shortcut: number; yearly_hamed_rao: number; ours: number }> };
}
export interface Models {
  available: boolean; headline: string; verdict?: "inside" | "above" | "below";
  models?: { model: string; slope_observed_period: number; slope_2026_2050: number }[];
  observed_slope?: number; model_range?: [number, number]; units_note?: string; caveat?: string; credit?: string;
}
type Off = { available: false; reason?: string };
type Span = { change_by_2050: number; range: [number, number]; units: string };
export interface Outlook {
  disclaimer: string;
  trend: Off | (Span & { available: true; note?: string });
  models: Off | (Span & { available: true; n_models: number; agree_on_direction: number; units_note?: string; credit?: string });
  scenarios: Off | { available: true; units: string; headline: string; choice_matters: string; note: string; source: string; caution?: string;
    scenarios: (Span & { id: string; name: string; global_warming_2050: number })[] };
}
type CmpSide = { name: string; box: Box; slope_per_decade: number; ci95: [number, number]; label: string; verdict: string };
export interface Compare {
  variable: Variable; n_cells: [number, number]; a: CmpSide; b: CmpSide;
  difference: { slope_per_decade: number; ci95: [number, number]; label: string };
  labels: { opposite_fitted_directions: boolean; supported_opposite_trends: boolean; rates_differ: boolean };
  correlation: number; boxes_overlap: boolean; headline: string; trap: string | null; note: string | null;
  chart: { dates: string[]; difference_anomaly: (number | null)[] }; period: string; method: string;
}
export interface Cite { items: { key: string; apa: string; harvard: string; bibtex: string; acknowledgement?: string }[] }
export type Spot = { name: string; slope_per_decade: number; units: string; case: string };
export interface Opposites { n_land_cells: number; n_rising: number; n_falling: number; headline: string; rising: Spot[]; falling: Spot[] }

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
    // 5xx = an upstream source (NASA POWER, Open-Meteo…) failed or is rate-limited: say so plainly, the UI offers a retry.
    if (r.status >= 500) throw new Error("NASA's data server is busy right now, so this part couldn't load. Try again in a minute.");
    throw new Error(body?.detail ?? `The server answered ${r.status}.`);
  }
  return r.json();
}

export const api = {
  variables: (b: Box) => get<{ variables: Variable[] }>(`/api/variables?${q(b)}`),
  analyse: (v: string, b: Box) => get<Analysis>(`/api/analyse?var=${v}&${q(b)}`),
  report: (b: Box) => get<Report>(`/api/report-card?${q(b)}`),
  map: (v: string, b: Box) => get<TrendMap>(`/api/map?var=${v}&${q(b)}`),
  validation: () => get<Validation>("/api/validation"),
  crossExam: (v: string, b: Box) => get<CrossExam>(`/api/cross-examine?var=${v}&${q(b)}`),
  witnesses: (v: string, b: Box) => get<Witnesses>(`/api/witnesses?var=${v}&${q(b)}`),
  places: (s: string) => get<{ results: PlaceHit[] }>(`/api/places?q=${encodeURIComponent(s)}&limit=8`),
  world: <T>() => get<T>("/api/world"),
  globe: <T>(v: string) => get<T>(`/api/globe?var=${v}&land_only=true`),
  cite: (v: string, name: string, url: string) => get<Cite>(`/api/cite?var=${v}&name=${encodeURIComponent(name)}&url=${encodeURIComponent(url)}`),
  opposites: (v: string) => get<Opposites>(`/api/opposites?var=${v}&n=4`),
  models: (v: string, b: Box) => get<Models>(`/api/models?var=${v}&${q(b)}`),
  outlook: (v: string, b: Box) => get<Outlook>(`/api/outlook?var=${v}&${q(b)}`),
  compare: (v: string, a: Box, b: Box, na: string, nb: string) =>
    get<Compare>(`/api/compare?var=${v}&a=${a.join(",")}&b=${b.join(",")}&name_a=${encodeURIComponent(na)}&name_b=${encodeURIComponent(nb)}`),
  evidenceUrl: (v: string, b: Box) => `${API}/api/evidence.csv?var=${v}&${q(b)}`,
};

// ponytail: real saved API responses, shown instantly while the live server answers (or sleeps).
export const examples = {
  analyse: exAnalyse as unknown as Analysis,
  report: exReport as unknown as Report,
  map: exMap as unknown as TrendMap,
  validation: exValidation as unknown as Validation,
  variables: (exVariables as unknown as { variables: Variable[] }).variables,
  crossExam: exCross as unknown as CrossExam,
  witnesses: exWitnesses as unknown as Witnesses,
};

/** Second-witness badge; older servers send only `agrees`. */
export function badgeOf(w: Witness): Badge | null {
  if (!w.available) return null;
  if (w.badge) return w.badge;
  if (!w.agrees) return "caution";
  const proven = (l?: Label) => l === "strong" || l === "some";
  return w.independence === "independent" && proven(w.nasa_verdict) && proven(w.witness_verdict) ? "confirmed" : "consistent";
}
