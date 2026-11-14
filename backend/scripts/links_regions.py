"""Out-of-sample test of region-specific links.

Stage 1 (done, scripts/links_screen.py): 10 hand-picked places, used ONLY to
form hypotheses.
Stage 2 (this script): region rules are written down HERE, from physics,
before running. They are then tested on places never looked at before:
  - GLOBAL: a regular land grid (every 10 deg lat x 15 deg lon, 45S-65N)
  - UK: a regular 1-degree grid over UK land
Same link test as stage 1 (seasons + trends removed, effective sample size,
must hold with the predicted sign in BOTH halves of the record).

A rule "works" if the link holds in most new places INSIDE its region and
clearly less often OUTSIDE.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import json
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import links_screen as L  # noqa: E402
from trend_detective import power  # noqa: E402

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ RULES
# Written before testing. Thresholds come from physics, not tuning.
RULES = {
    "warm_moist": {
        "region": "Cool climates (annual mean temperature below 12 °C)",
        "why": "In cool climates, warm months come from mild, moist ocean air. In hot climates, the hottest months are the dry, sunny ones.",
        "inside": lambda m: m["t_annual"] < 12,
    },
    "soil_heat": {
        "region": "Water-limited climates (in the warm season, evaporation follows soil water more than sunshine)",
        "why": "Soil can only cool the air by evaporating where soil water is what limits evaporation.",
        "inside": lambda m: m["water_limited"],
    },
    "wind_frost": {
        "region": "Mild-winter frost climates (coldest months average −2 to +6 °C, with frost)",
        "why": "Where winters are mild, frost needs a calm, clear night; wind prevents it. In deep-cold climates frost comes with cold air masses, so wind doesn't help.",
        "inside": lambda m: (-2 <= m["t_cold"] <= 6) and m["frosty"],
    },
    "haze_sun": {
        "region": "All land",
        "why": "Particles dim sunlight everywhere.",
        "inside": lambda m: True,
    },
    "rain_soil": {
        "region": "All land",
        "why": "Soil stores rain everywhere.",
        "inside": lambda m: True,
    },
    "soil_wind_via_heat": {
        "region": "Water-limited climates",
        "why": "Only where dry soil makes days hotter could it stir up wind.",
        "inside": lambda m: m["water_limited"],
    },
    "placebo": {
        "region": "All land",
        "why": "Random noise must never hold.",
        "inside": lambda m: True,
    },
}


def grids():
    pts = []
    for lat in range(-45, 66, 10):
        for lon in range(-165, 180, 15):
            pts.append(("global", float(lat), float(lon)))
    for lat in np.arange(50.5, 58.6, 1.0):
        for lon in np.arange(-7.5, 1.6, 1.0):
            pts.append(("uk", float(lat), float(lon)))
    return pts


def fetch_place(p):
    grid, lat, lon = p
    try:
        g = power.fetch_point("GWETROOT", lat, lon).dropna()
    except Exception as e:
        print("  FETCH FAILED", grid, lat, lon, str(e)[:80], flush=True)
        return None
    if len(g) < 200:  # ocean / ice: no soil
        return None
    d = {"GWETROOT": g}
    for v in L.VARS:
        if v == "GWETROOT":
            continue
        try:
            d[v] = power.fetch_point(v, lat, lon).dropna()
        except Exception as e:
            print("  FETCH FAILED", grid, lat, lon, v, str(e)[:80], flush=True)
    return grid, lat, lon, d


def evaluate(grid, lat, lon, d):
    if not all(k in d for k in ["T2M", "T2M_MAX", "T2M_MIN", "EVLAND", "ALLSKY_SFC_SW_DWN"]):
        return []
    d["DTR"] = (d["T2M_MAX"] - d["T2M_MIN"]).dropna()
    clim = d["T2M"].groupby(d["T2M"].index.month).mean().sort_values()
    warm, cold = list(clim.index[-3:]), list(clim.index[:3])
    A = {k: L.anomalies(v) for k, v in d.items() if len(v.dropna()) > 36 and v.std() > 0}
    ev = A["EVLAND"][L.season_mask(A["EVLAND"].index, warm)]
    r_sun, _, _ = L.corr_test(A["ALLSKY_SFC_SW_DWN"], ev)
    r_soil, _, _ = L.corr_test(A["GWETROOT"], ev)
    frost = d.get("FROST_DAYS")
    meta = {
        "t_annual": float(d["T2M"].mean()),
        "t_cold": float(clim.iloc[:3].mean()),
        "water_limited": bool(np.nan_to_num(r_soil, nan=-9) > np.nan_to_num(r_sun, nan=-9)),
        "frosty": bool(frost is not None and frost[L.season_mask(frost.index, cold)].mean() >= 1),
    }
    out = []
    for h in L.HYPS:
        if h["id"] not in RULES:
            continue
        if h["id"] == "wind_frost" and not meta["frosty"]:
            continue
        try:
            x, y = h["build"](A, warm, cold)
        except KeyError:
            continue
        j = pd.concat([x.rename("x"), y.rename("y")], axis=1, join="inner").dropna()
        if len(j) < 48 or j.x.std() == 0 or j.y.std() == 0:
            continue
        mid = j.index[len(j) // 2]
        r1, p1, _ = L.corr_test(j.x[:mid], j.y[:mid])
        r2, p2, _ = L.corr_test(j.x[mid:], j.y[mid:])
        r, _, _ = L.corr_test(j.x, j.y)
        if h["sign"] == 0:
            holds = p1 < 0.05 and p2 < 0.05 and np.sign(r1) == np.sign(r2)
        else:
            holds = all(np.isfinite(v) for v in (r1, r2)) and np.sign(r1) == h["sign"] == np.sign(r2) and p1 < 0.05 and p2 < 0.05
        out.append({"grid": grid, "lat": lat, "lon": lon, "hyp": h["id"], "r": r, "holds": bool(holds),
                    "inside": bool(RULES[h["id"]]["inside"](meta)), **meta})
    return out


def main():
    rng = np.random.default_rng(2026)
    idx = pd.date_range("1981-01-01", "2025-12-01", freq="MS")
    e = np.zeros(len(idx))
    for i in range(1, len(idx)):
        e[i] = 0.5 * e[i - 1] + rng.normal()
    L.PLACEBO_X = pd.Series(e, index=idx)

    pts = grids()
    print(len(pts), "candidate points", flush=True)
    rows, n_land = [], 0
    with ThreadPoolExecutor(2) as ex:
        for i, res in enumerate(ex.map(fetch_place, pts), 1):
            if res:
                n_land += 1
                rows += evaluate(*res)
            if i % 40 == 0:
                print(f"  {i}/{len(pts)} points, {n_land} on land", flush=True)
    df = pd.DataFrame(rows)
    out = Path(__file__).resolve().parents[1] / "data" / "links_regions.json"
    summary = []
    for hid, rule in RULES.items():
        for grid in ["global", "uk"]:
            s = df[(df.hyp == hid) & (df.grid == grid)]
            ins, outs = s[s.inside], s[~s.inside]
            summary.append({
                "link": hid, "grid": grid, "region": rule["region"],
                "inside_n": int(len(ins)), "inside_holds": int(ins.holds.sum()),
                "outside_n": int(len(outs)), "outside_holds": int(outs.holds.sum()),
                "inside_median_r": float(ins.r.median()) if len(ins) else None,
            })
    out.write_text(json.dumps({"rules": {k: {kk: vv for kk, vv in v.items() if kk != "inside"} for k, v in RULES.items()},
                               "summary": summary, "rows": rows}, indent=1, default=float))
    print(f"\nland points: global {df[df.grid=='global'][['lat','lon']].drop_duplicates().shape[0]}, uk {df[df.grid=='uk'][['lat','lon']].drop_duplicates().shape[0]}")
    for s in summary:
        pi = f"{s['inside_holds']}/{s['inside_n']}" + (f" ({100*s['inside_holds']/s['inside_n']:.0f}%)" if s["inside_n"] else "")
        po = f"{s['outside_holds']}/{s['outside_n']}" + (f" ({100*s['outside_holds']/s['outside_n']:.0f}%)" if s["outside_n"] else "")
        mr = f"{s['inside_median_r']:+.2f}" if s["inside_median_r"] is not None else "–"
        print(f"{s['link']:20s} {s['grid']:6s} inside {pi:16s} outside {po:16s} median r inside {mr}")


if __name__ == "__main__":
    main()
