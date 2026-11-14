"""The case file: context around a single verdict.

nearby   Is the change local or regional? Every grid cell around the place is
         tested (Hamed-Rao Mann-Kendall) with Benjamini-Hochberg FDR.
impact   What does it mean? Change as a share of normal, and how often recent
         years beat what used to be a 1-in-10 extreme (1981-2010 baseline).
linked   What else is changing here, and is it connected? Only links that
         passed our out-of-sample test (docs/linked_clues.md) are used, and
         each is re-tested at this place (both halves of the record).

All numbers come from code. AI-use note: drafted with Claude (Anthropic)
during the hackathon.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

from . import power, stats
from .catalogue import BY_ID

# ------------------------------------------------------------------ helpers
HIGH_WORD = {"T2M": "warmer", "T2M_MAX": "hotter by day", "T2M_MIN": "warmer at night", "TS": "warmer at the surface",
             "PRECTOTCORR": "wetter", "GWETTOP": "wetter in the topsoil", "GWETROOT": "wetter in the root zone",
             "QV2M": "more humid", "RH2M": "more humid", "WS2M": "windier", "ALLSKY_SFC_SW_DWN": "sunnier",
             "CLOUD_AMT": "cloudier", "AOD_55": "hazier", "EVLAND": "higher in evaporation", "FROST_DAYS": "frostier"}
LOW_WORD = {"T2M": "cooler", "T2M_MAX": "cooler by day", "T2M_MIN": "colder at night", "TS": "cooler at the surface",
            "PRECTOTCORR": "drier", "GWETTOP": "drier in the topsoil", "GWETROOT": "drier in the root zone",
            "QV2M": "drier-aired", "RH2M": "drier-aired", "WS2M": "calmer", "ALLSKY_SFC_SW_DWN": "duller",
            "CLOUD_AMT": "clearer", "AOD_55": "cleaner-aired", "EVLAND": "lower in evaporation", "FROST_DAYS": "less frosty"}
ABSOLUTE_ONLY = {"T2M", "T2M_MAX", "T2M_MIN", "TS"}  # % of a temperature in °C is meaningless
SEASONS = {"winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8], "autumn": [9, 10, 11]}


def _anoms(s: pd.Series) -> pd.Series:
    """Seasons AND linear trend removed (for linking two variables)."""
    a, _ = stats.deseasonalise(s.dropna())
    t = stats.to_decimal_year(a.index)
    f = sps.linregress(t, a.to_numpy())
    return a - (f.intercept + f.slope * t)


def _corr(x: pd.Series, y: pd.Series):
    j = pd.concat([x, y], axis=1, join="inner").dropna()
    if len(j) < 24 or j.iloc[:, 0].std() == 0 or j.iloc[:, 1].std() == 0:
        return np.nan, np.nan
    a, b = j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy()
    r = float(np.corrcoef(a, b)[0, 1])
    prod = max(min(stats.lag1_autocorr(a) * stats.lag1_autocorr(b), 0.95), 0.0)
    neff = max(len(a) * (1 - prod) / (1 + prod), 4)
    t = r * np.sqrt((neff - 2) / max(1 - r * r, 1e-12))
    return r, float(2 * sps.t.sf(abs(t), neff - 2))


# ------------------------------------------------------------------ nearby
def nearby(var: str, box, own: dict, span: float = 6.0) -> dict:
    la0, la1, lo0, lo1 = box
    clat, clon = (la0 + la1) / 2, (lo0 + lo1) / 2
    half_lat = max(span / 2, (la1 - la0) / 2 + 1.0)
    half_lon = max(span / 2, (lo1 - lo0) / 2 + 1.0)
    half_lat, half_lon = min(half_lat, 5.0), min(half_lon, 5.0)
    region = [max(clat - half_lat, -90), min(clat + half_lat, 90), max(clon - half_lon, -180), min(clon + half_lon, 180)]
    df, cells = power.fetch_region(var, *region)
    out, pvals = [], []
    for c in cells:
        s = df[c["id"]].dropna()
        # Skip cells where the variable barely ever changes value (e.g. frost days
        # over the sea are always 0): they can't show a trend and would count as "quiet".
        flat = len(s) == 0 or s.value_counts(normalize=True).iloc[0] > 0.9
        if len(s) < 36 or flat:
            r = {"slope_per_decade": np.nan, "p": np.nan, "typical_p": np.nan}
        else:
            r = stats.cell_tests(s)
        out.append({**c, "slope_per_decade": r["slope_per_decade"], "p": r["p"],
                    "inside": bool(la0 <= c["lat"] <= la1 and lo0 <= c["lon"] <= lo1)})
        pvals.append(r["p"])
    sig = stats.fdr(pvals)
    for c, s_ in zip(out, sig):
        c["significant_fdr"] = bool(s_)
    valid = [c for c in out if np.isfinite(c["p"])]
    n = len(valid)
    up = sum(c["significant_fdr"] and c["slope_per_decade"] > 0 for c in valid)
    down = sum(c["significant_fdr"] and c["slope_per_decade"] < 0 for c in valid)
    own_slope = own["sen_slope_per_decade"]
    own_proven = own["verdict"]["label"] in {"strong", "some"}
    same = up if own_slope > 0 else down
    opp = down if own_slope > 0 else up
    name = BY_ID[var]["name"].lower()
    word = "rising" if own_slope > 0 else "falling"
    if n == 0:
        kind, msg = "unknown", "No surrounding data."
    elif up >= 0.1 * n and down >= 0.1 * n:
        kind, msg = "opposite", (f"Opposite trends side by side: around this place {up} cells show a proven rise in {name} "
                                 f"and {down} a proven fall. One regional average would hide both.")
    elif own_proven and same >= 0.5 * n:
        kind, msg = "regional", f"Regional, not just here: {same} of {n} surrounding cells show the same proven {word} trend."
    elif own_proven and same < 0.2 * n:
        kind, msg = "local", (f"Only {same} of {n} surrounding cells show the same proven change on their own. It may be "
                              f"concentrated here, or just harder to prove one noisy cell at a time than for an area average.")
    elif own_proven:
        kind, msg = "patchy", f"Patchy: {same} of {n} surrounding cells show the same proven {word} trend."
    elif same + opp >= 0.2 * n:
        kind, msg = "around", (f"Not proven at this spot, but the area around it is changing: "
                               f"{up} cells rising and {down} falling after the correction.")
    else:
        kind, msg = "quiet", f"Nothing proven nearby either: {same + opp} of {n} surrounding cells after the correction."
    return {"region_box": [round(v, 2) for v in region], "n_cells": n, "n_rising": int(up), "n_falling": int(down),
            "n_same_direction": int(same), "kind": kind, "headline": msg, "cells": out, "fdr_q": stats.FDR_Q}


# ------------------------------------------------------------------ impact
def _tail_count(values: pd.Series, base_years, recent_years, high: bool):
    base = values[values.index.isin(base_years)]
    rec = values[values.index.isin(recent_years)]
    if len(base) < 20 or len(rec) < 5:
        return None
    thr = float(np.quantile(base, 0.9 if high else 0.1))
    k = int((rec > thr).sum() if high else (rec < thr).sum())
    p = float(sps.binom.sf(k - 1, len(rec), 0.1))
    return {"threshold": thr, "count": k, "out_of": int(len(rec)), "expected": 0.1 * len(rec), "p": p}


def impact(var: str, series: pd.Series, own: dict) -> dict:
    s = series.dropna()
    units = BY_ID[var]["units"]
    mean = float(s.mean())
    change = float(own["total_change"])
    pct = None if var in ABSOLUTE_ONLY or abs(mean) < 1e-9 else 100 * change / abs(mean)
    years = sorted(set(s.index.year))
    complete = [y for y in years if (s.index.year == y).sum() == 12]
    base_years = [y for y in complete if 1981 <= y <= 2010] or complete[:30]
    recent_years = complete[-10:]
    high = own["sen_slope_per_decade"] >= 0
    annual = s.groupby(s.index.year).mean()
    rows = []
    t = _tail_count(annual, base_years, recent_years, high)
    if t:
        rows.append({"period": "year", **t})
    for name, months in SEASONS.items():
        sub = s[s.index.month.isin(months)]
        yr = np.where(sub.index.month == 12, sub.index.year + 1, sub.index.year)
        g = sub.groupby(yr)
        seas = g.mean()[g.count() == 3]
        t = _tail_count(seas, base_years, recent_years, high)
        if t:
            rows.append({"period": name, **t})
    word = (HIGH_WORD if high else LOW_WORD).get(var, "higher" if high else "lower")
    best = max(rows, key=lambda r: (r["count"], -r["p"])) if rows else None
    if best and best["p"] < 0.05:
        what = "years" if best["period"] == "year" else f"{best['period']}s"
        headline = (f"{best['count']} of the last {best['out_of']} {what} were {word} than what used to be a 1-in-10 "
                    f"{'year' if best['period'] == 'year' else best['period']} ({base_years[0]}–{base_years[-1]}). "
                    f"By chance we'd expect about {best['expected']:.0f}.")
    elif best:
        headline = "Recent years don't yet beat the old 1-in-10 extremes more often than chance would."
    else:
        headline = "Not enough complete years to compare extremes."
    size = (f"Change so far: {change:+.3g} {units} since {own['start'][:4]}"
            + (f", {pct:+.0f}% of the long-term average ({mean:.3g} {units})." if pct is not None else "."))
    return {"mean": mean, "total_change": change, "percent_of_mean": pct, "size_headline": size,
            "extremes": rows, "extremes_headline": headline, "baseline": f"{base_years[0]}–{base_years[-1]}",
            "recent": f"{recent_years[0]}–{recent_years[-1]}"}


# ------------------------------------------------------------------ linked clues
UK = (49.5, 61.0, -8.5, 2.0)
LINKS = [
    {"id": "rain_soil", "cause": "PRECTOTCORR", "effect": "GWETROOT", "lag": 1, "sign": +1,
     "text": "Rain this month → wetter root zone next month",
     "evidence": "Held in 110 of 111 test places worldwide",
     "applies": lambda box, t: True},
    {"id": "haze_sun", "cause": "AOD_55", "effect": "ALLSKY_SFC_SW_DWN", "control": "CLOUD_AMT", "lag": 0, "sign": -1,
     "text": "More haze → less sunshine reaching the ground (cloud held fixed)",
     "evidence": "Held in 91 of 110 test places worldwide",
     "applies": lambda box, t: True},
    {"id": "warm_moist", "cause": "T2M", "effect": "QV2M", "lag": 0, "sign": +1,
     "text": "Warmer month → more water vapour in the air",
     "evidence": "Held in 48 of 51 cool test places (below 12 °C) and every UK point; only 27% of warmer places",
     "applies": lambda box, t: t is not None and t < 12},
    {"id": "wind_frost", "cause": "WS2M", "effect": "FROST_DAYS", "lag": 0, "sign": -1, "cold_season": True,
     "text": "Windier winter month → fewer frost days",
     "evidence": "Held at 31 of 33 UK test points; not elsewhere",
     "applies": lambda box, t: UK[0] <= (box[0] + box[1]) / 2 <= UK[1] and UK[2] <= (box[2] + box[3]) / 2 <= UK[3]},
]


def linked(var: str, box, series: pd.Series, own: dict, t_mean: float | None) -> list[dict]:
    out = []
    for L in LINKS:
        if var not in (L["cause"], L["effect"]):
            continue
        partner = L["effect"] if var == L["cause"] else L["cause"]
        expected_here = L["applies"](box, t_mean)
        try:
            ps, _ = power.fetch_area_series(partner, *box)
            ps = ps.dropna()
            data = {var: series.dropna(), partner: ps}
            if "control" in L:
                cs, _ = power.fetch_area_series(L["control"], *box)
                data[L["control"]] = cs.dropna()
        except power.PowerError:
            continue
        x, y = _anoms(data[L["cause"]]), _anoms(data[L["effect"]])
        if L["lag"]:
            y = y.shift(-L["lag"], freq="MS")  # effect next month aligned to cause month
        if L.get("cold_season"):
            try:
                ts, _ = power.fetch_area_series("T2M", *box)
                tm = ts.dropna().groupby(ts.dropna().index.month).mean().sort_values()
                cold = list(tm.index[:3])
            except power.PowerError:
                cold = [12, 1, 2]
            x = x[x.index.month.isin(cold)]
        if "control" in L:
            z = _anoms(data[L["control"]])
            j = pd.concat([x, y, z], axis=1, join="inner").dropna()
            X, Y, Z = (j.iloc[:, i] for i in range(3))
            x = X - np.polyval(np.polyfit(Z, X, 1), Z)
            y = Y - np.polyval(np.polyfit(Z, Y, 1), Z)
        j = pd.concat([x.rename("x"), y.rename("y")], axis=1, join="inner").dropna()
        if len(j) < 48:
            continue
        mid = j.index[len(j) // 2]
        r_all, _ = _corr(j.x, j.y)
        r1, p1 = _corr(j.x[:mid], j.y[:mid])
        r2, p2 = _corr(j.x[mid:], j.y[mid:])
        holds = bool(np.isfinite(r1) and np.isfinite(r2) and np.sign(r1) == L["sign"] == np.sign(r2) and p1 < 0.05 and p2 < 0.05)
        pr = stats.analyse(data[partner], BY_ID[partner]["units"])
        own_dir = 1 if own["sen_slope_per_decade"] > 0 else -1
        expected_partner_dir = own_dir * L["sign"]
        partner_proven = pr["verdict"]["label"] in {"strong", "some"}
        partner_dir = 1 if pr["sen_slope_per_decade"] > 0 else -1
        own_proven = own["verdict"]["label"] in {"strong", "some"}
        pname, vname = BY_ID[partner]["name"].lower(), BY_ID[var]["name"].lower()
        is_cause = var == L["cause"]
        pr_txt = (f"{pr['verdict']['label'].replace('_', ' ')} evidence, {pr['sen_slope_per_decade']:+.3g} "
                  f"{BY_ID[partner]['units']} per decade")
        if not holds:
            story = (f"This link usually holds{' in places like this' if expected_here else ''}, but it does not pass our test here "
                     f"(r = {r_all:+.2f}), so we don't use it to explain anything at this place.")
        elif own_proven and partner_proven and partner_dir == expected_partner_dir:
            story = (f"Consistent story: the link holds here (r = {r_all:+.2f}) and {pname} is also changing in the expected "
                     f"direction ({pr_txt})."
                     + ("" if is_cause else f" So part of the change in {vname} fits the change in {pname}."))
        elif own_proven and partner_proven:
            story = (f"Puzzle: the link holds here (r = {r_all:+.2f}), yet {pname} is moving the opposite way to what the "
                     f"link would suggest ({pr_txt}). Something else must be driving one of them.")
        elif own_proven and is_cause:
            story = (f"The link holds here (r = {r_all:+.2f}), but {pname} shows no proven trend yet, so the change in "
                     f"{vname} hasn't clearly passed through to it.")
        elif own_proven:
            story = (f"The link holds here (r = {r_all:+.2f}), but {pname} shows no proven trend, so it does not explain "
                     f"the change in {vname}. Something else is driving it.")
        else:
            story = f"The link holds here (r = {r_all:+.2f}). Neither change is proven yet, so there is nothing to pass on."
        out.append({"id": L["id"], "text": L["text"], "evidence": L["evidence"], "partner": partner,
                    "partner_name": BY_ID[partner]["name"], "expected_here": bool(expected_here),
                    "holds_here": holds, "r": r_all, "r_first_half": r1, "r_second_half": r2,
                    "partner_verdict": pr["verdict"]["label"], "partner_slope_per_decade": pr["sen_slope_per_decade"],
                    "partner_units": BY_ID[partner]["units"], "role": "cause" if is_cause else "effect", "story": story})
    return out
