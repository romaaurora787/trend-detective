"""Screen physically-motivated links between variables ("linked clues").

Protocol (fixed before looking at results):
- Every link has a mechanism and a predicted sign, written below.
- Monthly anomalies: seasonal cycle AND linear trend removed from each series,
  so two series that merely both trend cannot look linked.
- Lags respect cause -> effect where stated.
- Significance uses an effective sample size for autocorrelated series
  (n_eff = n (1 - r1x r1y) / (1 + r1x r1y), Bretherton et al. 1999).
- A link HOLDS at a place only if it has the predicted sign and p < 0.05 in
  BOTH halves of the record (split-sample replication).
- A placebo pair with no mechanism must fail.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from trend_detective import power, stats

warnings.filterwarnings("ignore")

PLACES = {  # name: (lat, lon)  -- deliberately different climates
    "Lincolnshire, UK": (53.2, -0.5),
    "Madrid, Spain": (40.4, -3.7),
    "Kansas, US Great Plains": (38.5, -98.0),
    "Niamey, Sahel": (13.5, 2.1),
    "Manaus, Amazon": (-3.1, -60.0),
    "Delhi, India": (28.6, 77.2),
    "Murray-Darling, Australia": (-34.0, 144.0),
    "Yakutsk, Siberia": (62.0, 129.7),
    "Nairobi, East Africa": (-1.3, 36.8),
    "Beijing, China": (39.9, 116.4),
}
VARS = ["T2M", "T2M_MAX", "T2M_MIN", "GWETTOP", "GWETROOT", "WS2M", "CLOUD_AMT",
        "ALLSKY_SFC_SW_DWN", "AOD_55", "QV2M", "PRECTOTCORR", "EVLAND", "FROST_DAYS"]


def anomalies(s: pd.Series) -> pd.Series:
    """Remove seasonal cycle and linear trend."""
    a, _ = stats.deseasonalise(s.dropna())
    t = stats.to_decimal_year(a.index)
    fit = sps.linregress(t, a.to_numpy())
    return a - (fit.intercept + fit.slope * t)


def corr_test(x: pd.Series, y: pd.Series):
    j = pd.concat([x, y], axis=1, join="inner").dropna()
    if len(j) < 24 or j.iloc[:, 0].std() == 0 or j.iloc[:, 1].std() == 0:
        return np.nan, np.nan, len(j)
    a, b = j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy()
    r = float(np.corrcoef(a, b)[0, 1])
    r1a, r1b = stats.lag1_autocorr(a), stats.lag1_autocorr(b)
    prod = max(min(r1a * r1b, 0.95), 0.0)
    neff = max(len(a) * (1 - prod) / (1 + prod), 4)
    tval = r * np.sqrt((neff - 2) / max(1 - r * r, 1e-12))
    return r, float(2 * sps.t.sf(abs(tval), neff - 2)), len(a)


def partial(x, y, z):
    """Correlation of x and y after removing z from both (linear)."""
    j = pd.concat([x, y, z], axis=1, join="inner").dropna()
    if len(j) < 24:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    X, Y, Z = (j.iloc[:, i] for i in range(3))
    rx = X - np.polyval(np.polyfit(Z, X, 1), Z)
    ry = Y - np.polyval(np.polyfit(Z, Y, 1), Z)
    return rx, ry


def season_mask(idx, months):
    return idx.month.isin(months)


# ---- hypotheses: (id, title, mechanism, predicted sign, builder) ----
# builder(d, warm, cold) -> (x, y) anomaly series, or None if not applicable
def H(id_, title, mech, sign, build):
    return {"id": id_, "title": title, "mechanism": mech, "sign": sign, "build": build}


def lag(s, k):  # value of s from k months earlier, aligned to current month
    return s.shift(k, freq="MS")


HYPS = [
    H("soil_heat", "Dry soil last month → hotter days this month (warm season)",
      "Wet soil spends the sun's energy on evaporation (cooling); dry soil can't, so the ground and air heat up.",
      -1, lambda d, w, c: (lag(d["GWETTOP"], 1)[season_mask(lag(d["GWETTOP"], 1).index, w)], d["T2M_MAX"])),
    H("cloud_dtr", "More cloud → smaller day–night temperature gap",
      "Clouds block sunshine by day and trap heat by night, squeezing the daily range.",
      -1, lambda d, w, c: (d["CLOUD_AMT"], d["DTR"])),
    H("wind_frost", "Windier cold months → fewer frost days",
      "Frost forms on calm, clear nights when cold air pools at the ground; wind mixes warmer air down.",
      -1, lambda d, w, c: (d["WS2M"][season_mask(d["WS2M"].index, c)], d["FROST_DAYS"])),
    H("haze_sun", "More haze → less sunshine reaching the ground (cloud held fixed)",
      "Aerosol particles reflect and absorb sunlight before it reaches the surface.",
      -1, lambda d, w, c: partial(d["AOD_55"], d["ALLSKY_SFC_SW_DWN"], d["CLOUD_AMT"])),
    H("warm_moist", "Warmer months → more water vapour in the air",
      "Warm air can hold about 7% more water vapour per °C (Clausius–Clapeyron).",
      +1, lambda d, w, c: (d["T2M"], d["QV2M"])),
    H("rain_soil", "Rain this month → wetter root zone next month",
      "Rain soaks in and the deep soil remembers it for weeks.",
      +1, lambda d, w, c: (d["PRECTOTCORR"], lag(d["GWETROOT"], -1))),
    H("soil_wind_via_heat", "YOUR CHAIN: dry soil → hotter days → windier (warm season)",
      "Hot ground stirs a deeper turbulent layer, mixing faster winds from aloft down to 2 m.",
      -1, lambda d, w, c: (d["GWETTOP"][season_mask(d["GWETTOP"].index, w)], d["WS2M"])),
    H("placebo", "PLACEBO: computer-generated random 'sticky' noise vs each place's rainfall (no mechanism)",
      "None by construction. It must fail in either direction; if it 'holds', the test is broken.",
      0, lambda d, w, c: (PLACEBO_X, d["PRECTOTCORR"])),
]


def main():
    global PLACEBO_X
    data = {}
    for name, (lat, lon) in PLACES.items():
        d = {}
        for v in VARS:
            try:
                d[v] = power.fetch_point(v, lat, lon).dropna()
            except Exception as e:
                print("fetch fail", name, v, e)
        d["DTR"] = (d["T2M_MAX"] - d["T2M_MIN"]).dropna()
        data[name] = d
        print("fetched", name, flush=True)
    rng = np.random.default_rng(2026)
    idx = pd.date_range("1981-01-01", "2025-12-01", freq="MS")
    e = np.zeros(len(idx))
    for i in range(1, len(idx)):
        e[i] = 0.5 * e[i - 1] + rng.normal()
    PLACEBO_X = pd.Series(e, index=idx)

    results = []
    for name, d in data.items():
        clim = d["T2M"].groupby(d["T2M"].index.month).mean().sort_values()
        warm, cold = list(clim.index[-3:]), list(clim.index[:3])
        A = {k: anomalies(v) for k, v in d.items() if len(v.dropna()) > 36}
        frosty = d.get("FROST_DAYS") is not None and d["FROST_DAYS"][season_mask(d["FROST_DAYS"].index, cold)].mean() >= 1
        for h in HYPS:
            if h["id"] == "wind_frost" and not frosty:
                results.append({"place": name, "hyp": h["id"], "status": "n/a (no frost)"})
                continue
            try:
                x, y = h["build"](A, warm, cold)
            except KeyError:
                results.append({"place": name, "hyp": h["id"], "status": "n/a (no data)"})
                continue
            j = pd.concat([x.rename("x"), y.rename("y")], axis=1, join="inner").dropna()
            if len(j) < 48:
                results.append({"place": name, "hyp": h["id"], "status": "n/a (too short)"})
                continue
            mid = j.index[len(j) // 2]
            r_all, p_all, n = corr_test(j.x, j.y)
            r1, p1, _ = corr_test(j.x[:mid], j.y[:mid])
            r2, p2, _ = corr_test(j.x[mid:], j.y[mid:])
            if h["sign"] == 0:  # placebo: any consistent significant link counts as a (false) hold
                holds = (np.isfinite(r1) and np.isfinite(r2) and p1 < 0.05 and p2 < 0.05
                         and np.sign(r1) == np.sign(r2))
            else:
                ok = lambda r, p: np.isfinite(r) and np.sign(r) == h["sign"] and p < 0.05
                holds = ok(r1, p1) and ok(r2, p2)
            results.append({"place": name, "hyp": h["id"], "r": r_all, "p": p_all, "n": n,
                            "r_first_half": r1, "r_second_half": r2,
                            "split": f"{j.index[0]:%Y}-{mid:%Y} | {mid:%Y}-{j.index[-1]:%Y}",
                            "status": "HOLDS" if holds else "fails"})

        # Clausius-Clapeyron size: % change in humidity per °C
        a_t, a_q = A["T2M"], A["QV2M"]
        jj = pd.concat([a_t, a_q], axis=1, join="inner").dropna()
        slope = sps.linregress(jj.iloc[:, 0], jj.iloc[:, 1]).slope
        results.append({"place": name, "hyp": "cc_rate", "pct_per_degC": 100 * slope / d["QV2M"].mean()})

    # Evaporation regime switch: what controls evaporation in the warm season?
    regime = []
    for name, d in data.items():
        clim = d["T2M"].groupby(d["T2M"].index.month).mean().sort_values()
        warm = list(clim.index[-3:])
        A = {k: anomalies(d[k]) for k in ["EVLAND", "ALLSKY_SFC_SW_DWN", "GWETROOT"]}
        ev = A["EVLAND"][season_mask(A["EVLAND"].index, warm)]
        r_sun, _, _ = corr_test(A["ALLSKY_SFC_SW_DWN"], ev)
        r_soil, _, _ = corr_test(A["GWETROOT"], ev)
        wet = float(d["GWETROOT"].mean())
        regime.append({"place": name, "mean_root_wetness": wet, "r_evap_sunshine": r_sun,
                       "r_evap_soil": r_soil,
                       "controlled_by": "sunshine (energy-limited)" if r_sun > r_soil else "soil water (water-limited)"})

    out = Path(__file__).resolve().parents[1] / "data" / "links_screen.json"
    out.write_text(json.dumps({"hypotheses": [{k: v for k, v in h.items() if k != "build"} for h in HYPS],
                               "results": results, "evaporation_regime": regime}, indent=1, default=float))

    df = pd.DataFrame([r for r in results if r["hyp"] not in ("cc_rate",)])
    print("\n=== Does each link hold (predicted sign, p<0.05 in BOTH halves)? ===")
    for h in HYPS:
        sub = df[df.hyp == h["id"]]
        tested = sub[sub.status.isin(["HOLDS", "fails"])]
        print(f"\n{h['title']}  [predicted sign {'+' if h['sign'] > 0 else '-' if h['sign'] < 0 else 'none'}]")
        print(f"  holds in {int((tested.status == 'HOLDS').sum())} of {len(tested)} places")
        for _, r in sub.iterrows():
            if r.status in ("HOLDS", "fails"):
                print(f"   {r.place:28s} r={r.r:+.2f}  halves {r.r_first_half:+.2f}/{r.r_second_half:+.2f}  {r.status}")
            else:
                print(f"   {r.place:28s} {r.status}")
    print("\n=== Warm air holds more water: humidity change per °C (theory ~7%) ===")
    for r in results:
        if r["hyp"] == "cc_rate":
            print(f"   {r['place']:28s} {r['pct_per_degC']:+.1f}% per °C")
    print("\n=== Evaporation regime (warm season): what controls evaporation? ===")
    for r in sorted(regime, key=lambda r: r["mean_root_wetness"]):
        print(f"   {r['place']:28s} root wetness {r['mean_root_wetness']:.2f}  r(sun)={r['r_evap_sunshine']:+.2f}  r(soil)={r['r_evap_soil']:+.2f}  -> {r['controlled_by']}")


if __name__ == "__main__":
    main()
