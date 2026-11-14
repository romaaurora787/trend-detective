"""FastAPI backend. Run: uv run uvicorn trend_detective.api:app --reload

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import functools
import json
import math
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from concurrent.futures import ThreadPoolExecutor

from . import beyond, context, places, power, stats, witnesses
from .catalogue import BY_ID, CATALOGUE, PLACE_TYPES

DATA = Path(__file__).resolve().parents[2] / "data"



# Results of the heavy endpoints are kept in memory, so a repeat visit (or a
# judge clicking back and forth) is instant and never re-asks NASA.
_MEMO: "OrderedDict[tuple, object]" = OrderedDict()
_MEMO_MAX = 512
_MEMO_LOCK = threading.Lock()


def memo(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (fn.__name__, args, tuple(sorted(kwargs.items())))
        with _MEMO_LOCK:
            if key in _MEMO:
                _MEMO.move_to_end(key)
                return _MEMO[key]
        out = fn(*args, **kwargs)
        with _MEMO_LOCK:
            _MEMO[key] = out
            while len(_MEMO) > _MEMO_MAX:
                _MEMO.popitem(last=False)
        return out
    return wrapper

app = FastAPI(title="Earth System Trend Detective API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def _clean(x):
    """Make numpy / NaN values JSON-safe."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _var(var: str) -> dict:
    if var not in BY_ID:
        raise HTTPException(404, f"Unknown variable {var}")
    return BY_ID[var]


def _bbox(lat_min, lat_max, lon_min, lon_max):
    if not (-90 <= lat_min < lat_max <= 90 and -180 <= lon_min < lon_max <= 180):
        raise HTTPException(400, "Invalid box")
    if lat_max - lat_min > 10 or lon_max - lon_min > 10:
        raise HTTPException(400, "Box too large: at most 10 x 10 degrees")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/variables")
def variables():
    return {"variables": CATALOGUE, "place_types": PLACE_TYPES}


@app.get("/api/analyse")
@memo
def analyse(
    var: str,
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    """Area-average series for the box + full verdict + chart data."""
    meta = _var(var)
    _bbox(lat_min, lat_max, lon_min, lon_max)
    try:
        series, n_cells = power.fetch_area_series(var, lat_min, lat_max, lon_min, lon_max)
    except power.PowerError as e:
        raise HTTPException(502, str(e))
    series = series.dropna()
    try:
        result = stats.analyse(series, units=meta["units"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    try:
        result["robustness"] = stats.robustness(series, units=meta["units"])
    except Exception as e:  # never break the main verdict
        result["robustness"] = {"robust": None, "windows": [], "headline": f"Robustness check unavailable ({type(e).__name__})."}
    anomalies, _ = stats.deseasonalise(series)
    t = stats.to_decimal_year(anomalies.index)
    t_mid = (t[0] + t[-1]) / 2
    slope = result["sen_slope_per_decade"] / 10
    a_mid = float(np.median(anomalies.to_numpy() - slope * (t - t_mid)))
    annual = anomalies.groupby(anomalies.index.year).mean()
    return _clean({
        "variable": meta,
        "box": [lat_min, lat_max, lon_min, lon_max],
        "n_cells": n_cells,
        "result": result,
        "chart": {
            "dates": [d.strftime("%Y-%m") for d in series.index],
            "values": series.round(4).tolist(),
            "anomalies": anomalies.round(4).tolist(),
            "trend_line": [a_mid + slope * (t[0] - t_mid), a_mid + slope * (t[-1] - t_mid)],
            "annual_years": annual.index.tolist(),
            "annual_anomalies": annual.round(4).tolist(),
        },
        "second_witness": _witness(var, [lat_min, lat_max, lon_min, lon_max], series, meta["units"]),
        "citation": f"NASA POWER Project, {meta['source']} monthly data, power.larc.nasa.gov (accessed Nov 2026)",
    })


def _witness(var, box, series, units):
    try:
        return witnesses.second_witness(var, box, series, units)
    except Exception as e:  # a witness problem must never break the main verdict
        return {"available": False, "note": f"Second witness unavailable ({type(e).__name__})."}


GROUPS = [
    ("proven", "Proven change", {"strong", "some"}),
    ("not_yet", "Not proven yet", {"not_yet", "mixed"}),
    ("none", "No meaningful trend", {"none"}),
]


@app.get("/api/report-card")
@memo
def report_card(
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
    witness: bool = True,
):
    """Feature B: every catalogue variable for one place, sorted by verdict."""
    _bbox(lat_min, lat_max, lon_min, lon_max)
    box = [lat_min, lat_max, lon_min, lon_max]

    def one(meta):
        try:
            series, n = power.fetch_area_series(meta["id"], *box)
            series = series.dropna()
            r = stats.analyse(series, units=meta["units"])
        except Exception as e:
            return {"id": meta["id"], "name": meta["name"], "error": str(e)[:200]}
        item = {
            "id": meta["id"], "name": meta["name"], "units": meta["units"], "source": meta["source"],
            "label": r["verdict"]["label"], "headline": r["verdict"]["headline"],
            "direction": r["verdict"]["direction"],
            "slope_per_decade": r["sen_slope_per_decade"], "ci95": r["sen_ci95_per_decade"],
            "total_change": r["total_change"], "period": f"{r['start']} to {r['end']}",
            "years_to_detect": r["years_to_detect"],
            "more_years_needed": (max(r["years_to_detect"] - r["record_years"], 0)
                                  if r["verdict"]["label"] == "not_yet" and r["years_to_detect"] else None),
            "typical_outcome": r["typical_vs_detective"]["outcome"],
            "typical_note": r["typical_vs_detective"]["note"],
        }
        if witness:
            item["second_witness"] = _witness(meta["id"], box, series, meta["units"])
        return item

    with ThreadPoolExecutor(6) as ex:
        items = list(ex.map(one, CATALOGUE))
    groups = []
    for key, title, labels in GROUPS:
        members = [i for i in items if i.get("label") in labels]
        if key == "proven":
            members.sort(key=lambda i: -abs(i["slope_per_decade"] / ((i["ci95"][1] - i["ci95"][0]) or 1)))
        if key == "not_yet":
            members.sort(key=lambda i: i["more_years_needed"] if i["more_years_needed"] is not None else 1e9)
        groups.append({"key": key, "title": title, "items": members})
    fooled = [i["name"] for i in items if i.get("typical_outcome") == "fooled"]
    return _clean({
        "box": box,
        "groups": groups,
        "errors": [i for i in items if "error" in i],
        "fooled_count": len(fooled),
        "fooled_variables": fooled,
        "summary": (f"{len(groups[0]['items'])} proven changes, {len(groups[1]['items'])} not proven yet, "
                    f"{len(groups[2]['items'])} with no meaningful trend."
                    + (f" A typical analysis would also have claimed trends in: {', '.join(fooled)}." if fooled else "")),
    })


@app.get("/api/map")
@memo
def trend_map(
    var: str,
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    """Per-grid-cell trend with Benjamini-Hochberg FDR (q=0.10)."""
    meta = _var(var)
    _bbox(lat_min, lat_max, lon_min, lon_max)
    # POWER needs >= 2 degrees each way; small boxes show the surrounding area.
    lat_min, lat_max = power._widen(lat_min, lat_max, 90)
    lon_min, lon_max = power._widen(lon_min, lon_max, 180)
    try:
        df, cells = power.fetch_region(var, lat_min, lat_max, lon_min, lon_max)
    except power.PowerError as e:
        raise HTTPException(502, str(e))
    out, pvals = [], []
    for c in cells:
        s = df[c["id"]].dropna()
        if len(s) < 36:
            r = {"slope_per_decade": float("nan"), "p": float("nan"), "typical_p": float("nan")}
        else:
            r = stats.cell_tests(s)
        out.append({**c, **r})
        pvals.append(r["p"])
    sig = stats.fdr(pvals)
    for c, s_ in zip(out, sig):
        c["significant_fdr"] = bool(s_)
        c["significant_raw"] = bool(np.isfinite(c["p"]) and c["p"] < stats.ALPHA)
        c["significant_typical"] = bool(np.isfinite(c["typical_p"]) and c["typical_p"] < stats.ALPHA)
    n_valid = int(np.isfinite(pvals).sum())
    n_typ = sum(c["significant_typical"] for c in out)
    n_up = sum(c["significant_fdr"] and c["slope_per_decade"] > 0 for c in out)
    n_down = sum(c["significant_fdr"] and c["slope_per_decade"] < 0 for c in out)
    return _clean({
        "variable": meta,
        "cells": out,
        "summary": {
            "n_cells": n_valid,
            "n_significant_typical": n_typ,
            "n_significant_raw": sum(c["significant_raw"] for c in out),
            "n_significant_fdr": int(sig.sum()),
            "n_rising_fdr": n_up,
            "n_falling_fdr": n_down,
            "fdr_q": stats.FDR_Q,
            "story": stats.map_story(n_valid, n_typ, int(sig.sum()), n_up, n_down, meta["name"]),
        },
    })


@app.get("/api/beyond")
@memo
def beyond_the_line(
    var: str,
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    """Records, emergence year, seasons, erratic-ness, turning point."""
    meta = _var(var)
    _bbox(lat_min, lat_max, lon_min, lon_max)
    try:
        series, n = power.fetch_area_series(var, lat_min, lat_max, lon_min, lon_max)
    except power.PowerError as e:
        raise HTTPException(502, str(e))
    s = series.dropna()
    if len(s) < 180:
        raise HTTPException(422, "Need at least 15 years of data")
    return _clean({"variable": meta, "box": [lat_min, lat_max, lon_min, lon_max], **beyond.beyond(s)})


@app.get("/api/places")
def place_search(q: str = Query(..., min_length=2, max_length=80), limit: int = Query(8, ge=1, le=20)):
    """Search ~34,000 world cities and towns (GeoNames, CC BY 4.0). Each result has a ready `box`."""
    return {"results": places.search(q, limit), "source": "GeoNames cities15000 (CC BY 4.0)"}


@app.get("/api/context")
@memo
def case_context(
    var: str,
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    """The case file around a verdict: nearby (local vs regional), impact,
    linked clues re-tested here, and records/seasons/emergence/turning point."""
    meta = _var(var)
    _bbox(lat_min, lat_max, lon_min, lon_max)
    box = [lat_min, lat_max, lon_min, lon_max]
    try:
        series, _ = power.fetch_area_series(var, *box)
    except power.PowerError as e:
        raise HTTPException(502, str(e))
    s = series.dropna()
    try:
        own = stats.analyse(s, units=meta["units"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    out = {"variable": meta, "box": box, "verdict": own["verdict"]}
    try:
        out["nearby"] = context.nearby(var, box, own)
    except Exception as e:  # each section fails on its own, never the whole page
        out["nearby"] = {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    try:
        out["impact"] = context.impact(var, s, own)
    except Exception as e:
        out["impact"] = {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    try:
        t_mean = None
        if var == "T2M":
            t_mean = float(s.mean())
        elif var in ("QV2M",):
            ts, _ = power.fetch_area_series("T2M", *box)
            t_mean = float(ts.dropna().mean())
        out["linked"] = context.linked(var, box, s, own, t_mean)
    except Exception as e:
        out["linked"] = {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    try:
        out["beyond"] = beyond.beyond(s) if len(s) >= 180 else {"error": "Need at least 15 years"}
    except Exception as e:
        out["beyond"] = {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    return _clean(out)


@app.get("/api/evidence.csv")
def evidence_csv(
    var: str,
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    """Download the evidence: monthly values, seasons-removed values and the
    trend line, with the verdict numbers and citation as header lines."""
    meta = _var(var)
    _bbox(lat_min, lat_max, lon_min, lon_max)
    try:
        series, n = power.fetch_area_series(var, lat_min, lat_max, lon_min, lon_max)
    except power.PowerError as e:
        raise HTTPException(502, str(e))
    s = series.dropna()
    try:
        r = stats.analyse(s, units=meta["units"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    anom, clim = stats.deseasonalise(s)
    t = stats.to_decimal_year(anom.index)
    slope = r["sen_slope_per_decade"] / 10
    t_mid = (t[0] + t[-1]) / 2
    a_mid = float(np.median(anom.to_numpy() - slope * (t - t_mid)))
    trend = a_mid + slope * (t - t_mid)
    lo, hi = r["sen_ci95_per_decade"]
    head = [
        f"# Earth System Trend Detective: evidence file",
        f"# Variable: {meta['name']} ({meta['id']}), units {meta['units']}, source {meta['source']} via NASA POWER",
        f"# Box: lat {lat_min} to {lat_max}, lon {lon_min} to {lon_max} ({n} NASA grid cells, area-weighted mean)",
        f"# Period: {r['start']} to {r['end']} ({r['n_months']} months)",
        f"# Verdict: {r['verdict']['label']} | {r['verdict']['headline']}",
        f"# Sen slope per decade: {r['sen_slope_per_decade']:.6g} (95% range {lo:.6g} to {hi:.6g}), method {r['slope_method']}",
        f"# Mann-Kendall (Hamed-Rao, 12 lags) p = {r['mk_hamed_rao']['p']:.6g}; OLS with effective n p = {r['ols_neff']['p']:.6g} (n_eff {r['ols_neff']['n_eff']:.1f})",
        f"# Typical analysis (months treated as independent) p = {r['typical_vs_detective']['typical_p']:.6g}",
        f"# Years to detect (Weatherhead 1998): {r['years_to_detect']}",
        f"# Citation: NASA POWER Project, power.larc.nasa.gov; {meta['source']}. Analysis code: github (Earth System Trend Detective).",
        "month,value,seasonal_normal,anomaly,trend_line",
    ]
    lines = [f"{d:%Y-%m},{v:.6g},{clim[d.month]:.6g},{a:.6g},{tl:.6g}"
             for d, v, a, tl in zip(anom.index, s.reindex(anom.index).to_numpy(), anom.to_numpy(), trend)]
    fname = f"trend-detective_{meta['id']}_{lat_min}_{lat_max}_{lon_min}_{lon_max}.csv"
    return Response("\n".join(head + lines) + "\n", media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/api/world")
def world():
    """World report (precomputed by scripts/world_report.py)."""
    p = DATA / "world_report.json"
    if not p.exists():
        raise HTTPException(404, "World report not computed yet")
    return json.loads(p.read_text())


@app.get("/api/links")
def linked_clues():
    """Linked-clues results (precomputed by scripts/links_screen.py + links_regions.py)."""
    out = {}
    p = DATA / "links_regions.json"
    if p.exists():
        d = json.loads(p.read_text())
        out = {"rules": d["rules"], "summary": d["summary"]}
    return out


@app.get("/api/validation")
def validation():
    res = {}
    for name in ["validation", "validation_power"]:
        p = DATA / f"{name}.json"
        if p.exists():
            res[name] = json.loads(p.read_text())
    return res
