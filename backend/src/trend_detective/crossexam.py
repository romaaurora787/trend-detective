"""Cross-examination: the questions a sceptic asks of a trend before believing it.

Each check takes the monthly series (and sometimes the variable id / box) and
answers one question in plain words:

  alibi          Could a change of satellite or model input explain it?
                 (documented source changes only, each with its reference)
  el_nino        Is it still there once El Niño / La Niña is removed?
                 (NOAA Oceanic Niño Index, lagged regression, Foster & Rahmstorf 2011)
  leave_one_out  Is one single year carrying the whole case?
  walk_forward   Found in the first half of the record: does it hold in the second?
  all_windows    Did we just pick good dates? Every start/end year, 15+ years long.
  decades        Is it speeding up? Rate per decade + an acceleration test.
  extremes       Early vs recent years, and the most extreme years.
  resolution     How many NASA grid cells really sit behind the number?

`overturn()` then lists what could still overturn the verdict.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats as sps

from . import stats

DATA = Path(__file__).resolve().parents[2] / "data"
ALPHA = stats.ALPHA
PROVEN = {"strong", "some"}


def _annual(series: pd.Series, need: int = 12) -> pd.Series:
    a, _ = stats.deseasonalise(series.dropna())
    g = a.groupby(a.index.year)
    return g.mean()[g.count() >= need]


def _bic(y: np.ndarray, X: np.ndarray) -> float:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    rss = float(((y - X @ beta) ** 2).sum())
    n = len(y)
    return n * np.log(max(rss, 1e-300) / n) + X.shape[1] * np.log(n)


def _proven(r: dict) -> bool:
    return r["verdict"]["label"] in PROVEN


# --------------------------------------------------------------------------- 1. instrument alibi
# Only documented changes, each with a source a judge can open.
SOURCE_CHANGES = {
    "ALLSKY_SFC_SW_DWN": [("2001-01", "NASA POWER switches sunshine from GEWEX SRB release 4 (1984–2000) to CERES SYN1deg (2001 on)",
                           "NASA POWER Data Access Viewer documentation")],
    "CLOUD_AMT": [("2001-01", "NASA POWER switches cloud cover from GEWEX SRB release 4 (1984–2000) to CERES SYN1deg (2001 on)",
                   "NASA POWER Data Access Viewer documentation")],
    "ALLSKY_SFC_LW_DWN": [("2001-01", "NASA POWER switches downward heat radiation from GEWEX SRB release 4 (1984–2000) to CERES SYN1deg (2001 on)",
                           "NASA POWER Data Access Viewer documentation")],
    "AOD_55": [("2014-07", "MERRA-2 stops assimilating MISR (June 2014) and AERONET (October 2014) aerosol observations",
                "Randles et al. 2017, J. Climate 30, 6823, Table 2")],
    "GWETROOT": [("1991-01", "MERRA-2 was produced in separate streams; stream joins cause jumps in deep soil layers",
                  "NCAR Climate Data Guide, MERRA-2 (Cullather & Bosilovich)"),
                 ("2001-01", "MERRA-2 production stream join (deep soil layers)", "NCAR Climate Data Guide, MERRA-2"),
                 ("2011-01", "MERRA-2 production stream join (deep soil layers)", "NCAR Climate Data Guide, MERRA-2")],
}
# Model rain jumps when the SSM/I F08 satellite arrives (GMAO); it matters where
# the gauge-corrected rain falls back on model rain (poleward of 42.5 degrees).
RAIN_F08 = ("1987-07", "SSM/I on DMSP F08 enters MERRA-2: a known jump in model rainfall, which is used poleward of 42.5° latitude",
            "GMAO science snapshot, MERRA-2 global precipitation time series")


def rain_provenance(lat: float) -> str:
    a = abs(lat)
    if a < 42.5:
        return "Here the rain is mainly from rain gauges (MERRA-2's gauge-corrected precipitation)."
    if a < 62.5:
        return ("Here the rain is a blend: gauge-based nearer the equator, tapering to MERRA-2 model rain "
                "between 42.5° and 62.5° latitude.")
    return "Here the rain is MERRA-2 model rain only (no gauge correction poleward of 62.5°)."


def alibi(var: str, series: pd.Series, units: str, lat_centre: float | None = None) -> dict:
    """Step-vs-trend at each documented source change, and the trend re-tested
    on each single-source segment."""
    s = series.dropna().sort_index()
    changes = list(SOURCE_CHANGES.get(var, []))
    if var == "PRECTOTCORR" and lat_centre is not None and abs(lat_centre) >= 42.5:
        changes.append(RAIN_F08)
    note = rain_provenance(lat_centre) if var == "PRECTOTCORR" and lat_centre is not None else None
    if not changes:
        return {"status": "no_known_change", "changes": [], "provenance": note,
                "headline": "No documented change of instrument or model input inside this record."}
    full = stats.analyse(s, units)
    ann = _annual(s)
    t = ann.index.to_numpy(float)
    y = ann.to_numpy()
    out = []
    for date, what, ref in changes:
        yr = int(date[:4])
        pre, post = s[s.index < date], s[s.index >= date]
        if len(pre) < 96 or len(post) < 96:  # need 8 years each side
            out.append({"date": date, "what": what, "source": ref, "tested": False,
                        "why": "Not enough years on one side of the change to test it."})
            continue
        rp, rq = stats.analyse(pre, units), stats.analyse(post, units)
        one = np.ones_like(t)
        tt = t - t.mean()
        step = (t >= yr).astype(float)
        b_trend, b_step = _bic(y, np.c_[one, tt]), _bic(y, np.c_[one, step])
        sign = np.sign(full["sen_slope_per_decade"])
        same_pre = np.sign(rp["sen_slope_per_decade"]) == sign
        same_post = np.sign(rq["sen_slope_per_decade"]) == sign
        step_better = b_step < b_trend - 2  # BIC difference > 2: positive evidence
        if not _proven(full):
            status = "nothing_to_explain"
        elif same_pre and same_post and (_proven(rq) or _proven(rp)) and not step_better:
            status = "survives"
        elif step_better and not (same_pre and same_post):
            status = "could_be_instrument"
        elif step_better or not (same_pre and same_post):
            status = "doubt"
        else:
            status = "survives_weakly"
        out.append({
            "date": date, "what": what, "source": ref, "tested": True, "status": status,
            "before": {"period": f"{rp['start'][:4]}–{rp['end'][:4]}", "slope_per_decade": rp["sen_slope_per_decade"],
                       "p": rp["mk_hamed_rao"]["p"], "label": rp["verdict"]["label"]},
            "after": {"period": f"{rq['start'][:4]}–{rq['end'][:4]}", "slope_per_decade": rq["sen_slope_per_decade"],
                      "p": rq["mk_hamed_rao"]["p"], "label": rq["verdict"]["label"]},
            "bic_trend": b_trend, "bic_step": b_step, "step_explains_better": bool(step_better),
        })
    tested = [o for o in out if o.get("tested")]
    order = ["could_be_instrument", "doubt", "survives_weakly", "survives", "nothing_to_explain"]
    worst = min((o["status"] for o in tested), key=order.index) if tested else "untested"
    u = units
    if worst == "could_be_instrument":
        o = next(o for o in tested if o["status"] == worst)
        fs = full["sen_slope_per_decade"]
        both_opp = (np.sign(o["before"]["slope_per_decade"]) == np.sign(o["after"]["slope_per_decade"]) != np.sign(fs))
        tail = (" Both sides actually go the other way: the whole-record 'trend' is made by the jump."
                if both_opp else "")
        msg = (f"Could be the instrument: the whole record says {fs:+.3g} {u}/decade, but a single jump at "
               f"{o['date'][:4]} ({o['what'].split(':')[0]}) explains the data better than a steady trend. "
               f"Before: {o['before']['slope_per_decade']:+.3g}; after: {o['after']['slope_per_decade']:+.3g} {u}/decade.{tail}")
    elif worst == "doubt":
        o = next(o for o in tested if o["status"] == worst)
        msg = (f"Some doubt: around the {o['date'][:4]} data change the picture is unclear "
               f"({o['before']['slope_per_decade']:+.3g} before, {o['after']['slope_per_decade']:+.3g} {u}/decade after).")
    elif worst in ("survives", "survives_weakly"):
        o = tested[0]
        msg = (f"Survives the instrument alibi: the trend runs the same way before and after the {o['date'][:4]} data change "
               f"({o['before']['slope_per_decade']:+.3g} and {o['after']['slope_per_decade']:+.3g} {u}/decade).")
    elif worst == "nothing_to_explain":
        msg = "No proven trend, so there is nothing for a data change to explain."
    else:
        msg = "A documented data change falls too close to the start or end of the record to test."
    return {"status": worst, "changes": out, "provenance": note, "headline": msg}


# --------------------------------------------------------------------------- 2. El Niño
@lru_cache(maxsize=1)
def oni() -> pd.Series:
    """NOAA CPC Oceanic Niño Index: 3-month running mean, labelled by its centre month."""
    centre = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8,
              "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
    rows = []
    for line in (DATA / "external" / "oni.ascii.txt").read_text().splitlines()[1:]:
        p = line.split()
        if len(p) == 4 and p[0] in centre:
            rows.append((pd.Timestamp(int(p[1]), centre[p[0]], 1), float(p[3])))
    return pd.Series(dict(rows)).sort_index()


def el_nino(series: pd.Series, units: str) -> dict:
    """Regress monthly anomalies on trend + ONI at the best lag (0-6 months),
    then re-test the ENSO-removed series (Foster & Rahmstorf 2011)."""
    s = series.dropna().sort_index()
    a, clim = stats.deseasonalise(s)
    o = oni()
    best = None
    for lag in range(0, 7):
        x = o.shift(lag, freq="MS").reindex(a.index)
        ok = x.notna()
        if ok.sum() < 120:
            continue
        t = stats.to_decimal_year(a.index[ok])
        X = np.c_[np.ones(ok.sum()), t - t.mean(), x[ok].to_numpy()]
        beta, *_ = np.linalg.lstsq(X, a[ok].to_numpy(), rcond=None)
        rss = float(((a[ok].to_numpy() - X @ beta) ** 2).sum())
        if best is None or rss < best[0]:
            best = (rss, lag, beta[2], x)
    if best is None:
        return {"status": "unavailable", "headline": "El Niño index does not cover this record."}
    _, lag, coef, x = best
    keep = x.notna()
    adj = (a[keep] - coef * x[keep]) + clim.reindex(a[keep].index.month).to_numpy()
    before = stats.analyse(s[keep], units)
    after = stats.analyse(adj, units)
    r_enso = float(np.corrcoef(a[keep], x[keep])[0, 1])
    # Composite: calendar-year mean anomaly in El Niño vs La Niña years (DJF ONI)
    djf = o[o.index.month == 1]
    ann = a.groupby(a.index.year).mean()
    nino = [ann[y] for y in ann.index if pd.Timestamp(y, 1, 1) in djf.index and djf[pd.Timestamp(y, 1, 1)] >= 0.5]
    nina = [ann[y] for y in ann.index if pd.Timestamp(y, 1, 1) in djf.index and djf[pd.Timestamp(y, 1, 1)] <= -0.5]
    comp = None
    if len(nino) >= 3 and len(nina) >= 3:
        tt = sps.ttest_ind(nino, nina, equal_var=False)
        comp = {"el_nino_years_mean": float(np.mean(nino)), "la_nina_years_mean": float(np.mean(nina)),
                "n_el_nino": len(nino), "n_la_nina": len(nina), "difference": float(np.mean(nino) - np.mean(nina)),
                "p": float(tt.pvalue)}
    pb, pa = _proven(before), _proven(after)
    sb, sa = before["sen_slope_per_decade"], after["sen_slope_per_decade"]
    if pb and pa:
        msg = f"Still there with El Niño removed: {sa:+.3g} {units}/decade (was {sb:+.3g})."
        status = "survives"
    elif pb and not pa:
        msg = (f"Weakens with El Niño removed: {sb:+.3g} → {sa:+.3g} {units}/decade and no longer proven. "
               "Part of the 'trend' may be the timing of El Niño and La Niña years.")
        status = "weakens"
    elif not pb and pa:
        msg = (f"El Niño was hiding it: removing El Niño's ups and downs reveals a proven trend "
               f"({sa:+.3g} {units}/decade).")
        status = "revealed"
    else:
        msg = "No proven trend with or without El Niño."
        status = "none"
    strength = "strongly" if abs(r_enso) >= 0.4 else "somewhat" if abs(r_enso) >= 0.2 else "hardly"
    return {"status": status, "headline": msg, "lag_months": int(lag), "effect_per_degree_oni": float(coef),
            "correlation": r_enso, "how_linked": f"This place {strength} follows El Niño (r = {r_enso:+.2f}, {lag}-month delay).",
            "before": {"slope_per_decade": sb, "ci95": before["sen_ci95_per_decade"], "label": before["verdict"]["label"]},
            "after": {"slope_per_decade": sa, "ci95": after["sen_ci95_per_decade"], "label": after["verdict"]["label"]},
            "composite": comp, "index": "NOAA CPC Oceanic Niño Index (ONI)",
            "method": "Foster & Rahmstorf (2011): regression on trend + ENSO index at the best-fitting lag"}


# --------------------------------------------------------------------------- 3. leave one year out
def leave_one_out(series: pd.Series) -> dict:
    s = series.dropna().sort_index()
    a, _ = stats.deseasonalise(s)
    base = mk.hamed_rao_modification_test(a.to_numpy(), lag=stats.HR_LAG)
    years = sorted(set(a.index.year))
    rows = []
    for yr in years:
        sub = a[a.index.year != yr].to_numpy()
        r = mk.hamed_rao_modification_test(sub, lag=stats.HR_LAG)
        rows.append({"year": int(yr), "p": float(r.p), "slope_per_decade": float(r.slope * 120)})
    worst = max(rows, key=lambda r: r["p"])
    sig = base.p < ALPHA
    flips = [r for r in rows if (r["p"] < ALPHA) != sig]
    ann = a.groupby(a.index.year).mean()
    extreme = int(ann.abs().idxmax())
    if sig and flips:
        msg = (f"Leans on one year: without {worst['year']} the evidence drops to p = {worst['p']:.2g}. "
               "Treat the trend with care.")
    elif sig:
        msg = (f"No single year carries it: removing any one year keeps it proven "
               f"(weakest without {worst['year']}, p = {worst['p']:.2g}).")
    elif flips:
        best = min(rows, key=lambda r: r["p"])
        msg = f"Not proven, but close: removing {best['year']} alone would make it significant (p = {best['p']:.2g})."
    else:
        msg = "Not proven, and no single year changes that."
    return {"p_all_years": float(base.p), "most_influential_year": worst["year"], "p_without_it": worst["p"],
            "most_extreme_year": extreme, "flips": [r["year"] for r in flips], "years": rows, "headline": msg}


# --------------------------------------------------------------------------- 4. walk forward
def walk_forward(series: pd.Series, units: str) -> dict:
    s = series.dropna().sort_index()
    y0, y1 = s.index[0].year, s.index[-1].year
    mid = (y0 + y1 + 1) // 2
    a, b = s[s.index.year < mid], s[s.index.year >= mid]
    if len(a) < 120 or len(b) < 120:
        return {"status": "too_short", "headline": "Record too short to split in two."}
    ra, rb = stats.analyse(a, units), stats.analyse(b, units)
    sa, sb = ra["sen_slope_per_decade"], rb["sen_slope_per_decade"]
    pa, pb = _proven(ra), _proven(rb)
    same = np.sign(sa) == np.sign(sb)
    if pa and pb and same:
        st, msg = "confirmed", f"Confirmed: found in {y0}–{mid - 1} and found again, the same way, in {mid}–{y1}."
    elif pa and same:
        st, msg = "continuing", f"Continuing: found in {y0}–{mid - 1}; {mid}–{y1} keeps going the same way but is not proven on its own."
    elif pa and pb and not same:
        st, msg = "reversed", f"Reversed: {sa:+.3g} {units}/decade in {y0}–{mid - 1}, then {sb:+.3g} in {mid}–{y1}."
    elif pa:
        st, msg = "faded", f"Faded: the {y0}–{mid - 1} trend does not continue in {mid}–{y1}."
    elif pb:
        st, msg = "emerging", f"Emerging: nothing proven in {y0}–{mid - 1}, but {mid}–{y1} shows a proven change ({sb:+.3g} {units}/decade)."
    else:
        st, msg = "neither", "Neither half shows a proven trend on its own."
    row = lambda r, lo, hi: {"period": f"{lo}–{hi}", "slope_per_decade": r["sen_slope_per_decade"],  # noqa: E731
                             "ci95": r["sen_ci95_per_decade"], "label": r["verdict"]["label"]}
    return {"status": st, "headline": msg, "first": row(ra, y0, mid - 1), "second": row(rb, mid, y1)}


# --------------------------------------------------------------------------- 5. every window
def all_windows(series: pd.Series, min_years: int = 15) -> dict:
    ann = _annual(series)
    yrs = ann.index.to_numpy(int)
    v = ann.to_numpy()
    full = mk.yue_wang_modification_test(v, lag=1)
    cells = []
    for i in range(len(yrs)):
        for j in range(i + min_years - 1, len(yrs)):
            x = v[i:j + 1]
            r = mk.yue_wang_modification_test(x, lag=1) if np.ptp(x) > 0 else None
            if r is None:
                continue
            cells.append({"start": int(yrs[i]), "end": int(yrs[j]), "slope_per_decade": float(r.slope * 10),
                          "p": float(r.p)})
    if not cells:
        return {"headline": "Record too short.", "cells": []}
    sign = np.sign(full.slope)
    same = sum(np.sign(c["slope_per_decade"]) == sign for c in cells)
    sig_same = sum(np.sign(c["slope_per_decade"]) == sign and c["p"] < ALPHA for c in cells)
    sig_opp = sum(np.sign(c["slope_per_decade"]) == -sign and c["p"] < ALPHA for c in cells)
    n = len(cells)
    word = "rising" if sign > 0 else "falling"
    if sig_opp == 0 and same / n >= 0.9:
        msg = f"Not cherry-picked: {same} of {n} possible start/end choices ({same / n:.0%}) show it {word}."
    elif sig_opp > 0:
        msg = (f"Depends on the dates: {sig_opp} of {n} start/end choices show a proven change the *other* way. "
               "Be careful which years you quote.")
    else:
        msg = f"Mostly consistent: {same} of {n} start/end choices ({same / n:.0%}) show it {word}."
    return {"n_windows": n, "same_direction": int(same), "proven_same_direction": int(sig_same),
            "proven_opposite": int(sig_opp), "min_years": min_years, "cells": cells, "headline": msg,
            "method": "Yue–Wang modified Mann–Kendall on yearly means, every window of 15 years or more"}


# --------------------------------------------------------------------------- 6. decades / acceleration
def decades(series: pd.Series, units: str) -> dict:
    ann = _annual(series)
    rows = []
    for d0 in range(1980, 2030, 10):
        sub = ann[(ann.index >= d0) & (ann.index < d0 + 10)]
        if len(sub) < 5:
            continue
        r = mk.original_test(sub.to_numpy())
        rows.append({"decade": f"{max(d0, int(ann.index[0]))}–{min(d0 + 9, int(ann.index[-1]))}",
                     "slope_per_decade": float(r.slope * 10), "p": float(r.p), "n_years": int(len(sub)),
                     "mean_anomaly": float(sub.mean())})
    # Acceleration: quadratic term on yearly means, SE widened for persistence
    t = ann.index.to_numpy(float)
    tt = (t - t.mean()) / 10
    y = ann.to_numpy()
    X = np.c_[np.ones_like(tt), tt, tt ** 2]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    r1 = stats.lag1_autocorr(res)
    n = len(y)
    neff = max(n * (1 - r1) / (1 + r1), 4) if r1 > 0 else n
    sigma2 = float((res ** 2).sum() / (neff - 3))
    cov = sigma2 * np.linalg.inv(X.T @ X)
    z = beta[2] / np.sqrt(cov[2, 2])
    p = float(2 * sps.t.sf(abs(z), max(neff - 3, 1)))
    lin = np.polyfit(t, y, 1)[0] * 10
    recent = ann[ann.index >= ann.index[-1] - 14]
    recent_rate = float(np.polyfit(recent.index.to_numpy(float), recent.to_numpy(), 1)[0] * 10)
    speeding = np.sign(beta[2]) == np.sign(lin) and lin != 0
    if p < ALPHA and speeding:
        state = "speeding_up"
        msg = (f"Speeding up (p = {p:.2g}): the last 15 years changed at "
               f"{recent_rate:+.3g} {units}/decade against {lin:+.3g} over the whole record.")
    elif p < ALPHA and np.sign(recent_rate) != np.sign(lin):
        state = "turning_around"
        msg = (f"Turning around (p = {p:.2g}): the record bends the other way lately. Last 15 years "
               f"{recent_rate:+.3g} {units}/decade against {lin:+.3g} over the whole record.")
    elif p < ALPHA:
        state = "slowing_down"
        msg = (f"Slowing down (p = {p:.2g}): the last 15 years changed at "
               f"{recent_rate:+.3g} {units}/decade against {lin:+.3g} over the whole record.")
    else:
        state = "steady"
        msg = (f"No proven speed-up or slow-down (p = {p:.2g}). Last 15 years: {recent_rate:+.3g} {units}/decade; "
               f"whole record: {lin:+.3g}.")
    return {"decades": rows, "acceleration_p": p, "state": state, "recent_15y_rate_per_decade": recent_rate,
            "whole_record_rate_per_decade": float(lin), "headline": msg}


# --------------------------------------------------------------------------- 7. extremes
def extremes(series: pd.Series, units: str) -> dict:
    ann = _annual(series)
    k = min(10, len(ann) // 3)
    early, late = ann.iloc[:k], ann.iloc[-k:]
    w = sps.ttest_ind(late, early, equal_var=False)
    u = sps.mannwhitneyu(late, early, alternative="two-sided")
    hi = ann.sort_values(ascending=False).head(3)
    lo = ann.sort_values().head(3)
    d = float(late.mean() - early.mean())
    recent_hi = sum(y >= ann.index[-k] for y in hi.index)
    msg = (f"The last {k} years averaged {d:+.3g} {units} compared with the first {k} "
           f"(p = {w.pvalue:.2g}). {recent_hi} of the 3 highest years are in the last {k}.")
    return {"early": f"{early.index[0]}–{early.index[-1]}", "late": f"{late.index[0]}–{late.index[-1]}",
            "difference": d, "welch_p": float(w.pvalue), "mann_whitney_p": float(u.pvalue),
            "highest_years": [{"year": int(y), "anomaly": float(v)} for y, v in hi.items()],
            "lowest_years": [{"year": int(y), "anomaly": float(v)} for y, v in lo.items()], "headline": msg}


# --------------------------------------------------------------------------- 8. resolution
def resolution(n_cells: int, box: list[float]) -> dict:
    km = 111 * (box[1] - box[0])
    if n_cells >= 4:
        lab, msg = "resolved", f"{n_cells} NASA grid cells (~50 km each) inside this area: a regional picture."
    elif n_cells >= 2:
        lab, msg = "marginal", f"Only {n_cells} NASA grid cells: treat it as the wider area, not one town."
    else:
        lab, msg = "sub_cell", "Smaller than one NASA grid cell (~50 km): this is the cell's value, not the street's."
    return {"label": lab, "n_cells": n_cells, "box_km": round(km), "headline": msg}


# --------------------------------------------------------------------------- what could overturn it
def overturn(res: dict) -> list[str]:
    out = []
    al = res.get("alibi", {})
    if al.get("status") in ("could_be_instrument", "doubt"):
        out.append(al["headline"])
    en = res.get("el_nino", {})
    if en.get("status") in ("weakens", "revealed"):
        out.append(en["headline"])
    lo = res.get("leave_one_out", {})
    if lo.get("flips"):
        out.append(lo["headline"])
    aw = res.get("all_windows", {})
    if aw.get("proven_opposite"):
        out.append(aw["headline"])
    wf = res.get("walk_forward", {})
    if wf.get("status") in ("faded", "reversed"):
        out.append(wf["headline"])
    rs = res.get("resolution", {})
    if rs.get("label") == "sub_cell":
        out.append(rs["headline"])
    out.append("MERRA-2 is a reanalysis (a weather model steered by observations), not a thermometer: "
               "an independent witness agreeing makes the case much stronger.")
    return out


def cross_examine(var: str, series: pd.Series, units: str, box: list[float], n_cells: int) -> dict:
    res = {}
    lat_c = (box[0] + box[1]) / 2
    for name, fn in [("alibi", lambda: alibi(var, series, units, lat_c)),
                     ("el_nino", lambda: el_nino(series, units)),
                     ("leave_one_out", lambda: leave_one_out(series)),
                     ("walk_forward", lambda: walk_forward(series, units)),
                     ("all_windows", lambda: all_windows(series)),
                     ("decades", lambda: decades(series, units)),
                     ("extremes", lambda: extremes(series, units)),
                     ("resolution", lambda: resolution(n_cells, box))]:
        try:
            res[name] = fn()
        except Exception as e:  # one failed check never sinks the others
            res[name] = {"error": f"{type(e).__name__}: {e}"[:200]}
    res["could_overturn"] = overturn(res)
    main = stats.analyse(series, units)
    if not _proven(main):
        lo = res.get("leave_one_out", {})
        hint = f" {lo['headline']}" if lo.get("flips") else ""
        res["score"] = {"passed": None, "of": 5, "proven": False,
                        "headline": "No proven trend to cross-examine. The checks below show how close it is." + hint}
        return res
    passed = sum([res.get("alibi", {}).get("status") in ("survives", "survives_weakly", "no_known_change"),
                  res.get("el_nino", {}).get("status") in ("survives", "none"),
                  not res.get("leave_one_out", {}).get("flips"),
                  res.get("walk_forward", {}).get("status") in ("confirmed", "continuing", "neither"),
                  not res.get("all_windows", {}).get("proven_opposite")])
    res["score"] = {"passed": int(passed), "of": 5, "proven": True,
                    "headline": f"Passed {passed} of 5 cross-examination checks (instrument, El Niño, one year, two halves, dates)."}
    return res
