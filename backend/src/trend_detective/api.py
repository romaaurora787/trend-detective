"""FastAPI backend. Run: uv run uvicorn trend_detective.api:app --reload

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from concurrent.futures import ThreadPoolExecutor

from . import beyond, power, stats, witnesses
from .catalogue import BY_ID, CATALOGUE, PLACE_TYPES

DATA = Path(__file__).resolve().parents[2] / "data"

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
