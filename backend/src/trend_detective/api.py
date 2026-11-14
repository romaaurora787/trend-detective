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
import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from concurrent.futures import ThreadPoolExecutor

from . import beyond, compare as cmp, context, crossexam, drought, models, reproduce, era5, events, globalref, guide, heat, places, stations, power, stats, witnesses
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
    start: int | None = Query(None, ge=1981, le=2025), end: int | None = Query(None, ge=1981, le=2025),
):
    """Area-average series for the box + full verdict + chart data.
    Optional start/end years pick a custom period (at least 10 years)."""
    meta = _var(var)
    series, n_cells = _series(var, [lat_min, lat_max, lon_min, lon_max], start, end)
    try:
        result = stats.analyse(series, units=meta["units"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    try:
        result["robustness"] = stats.robustness(series, units=meta["units"])
    except Exception as e:  # never break the main verdict
        result["robustness"] = {"robust": None, "windows": [], "headline": f"Robustness check unavailable ({type(e).__name__})."}
    try:
        result["vs_world"] = globalref.vs_world(var, result["sen_slope_per_decade"], result["start"], result["end"])
    except Exception:
        result["vs_world"] = None
    result["coverage"] = _coverage(series)
    try:
        result["reproduce"] = reproduce.links(var, [lat_min, lat_max, lon_min, lon_max],
                                              int(result["start"][:4]), int(result["end"][:4]))
    except Exception:
        result["reproduce"] = []
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
        "citation": meta.get("citation") or f"NASA POWER Project, {meta['source']} monthly data, power.larc.nasa.gov (accessed Nov 2026)",
    })


@app.get("/api/cross-examine")
@memo
def cross_examine(
    var: str,
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
    start: int | None = Query(None, ge=1981, le=2025), end: int | None = Query(None, ge=1981, le=2025),
):
    """The sceptic's questions: instrument alibi, El Niño, one year, two halves,
    every start/end year, speed-up, extremes, grid resolution."""
    meta = _var(var)
    box = [lat_min, lat_max, lon_min, lon_max]
    series, n_cells = _series(var, box, start, end)
    return _clean({"variable": meta, "box": box, "n_cells": n_cells,
                   **crossexam.cross_examine(var, series, meta["units"], box, n_cells)})


def _series(var, box, start=None, end=None):
    _bbox(*box)
    try:
        series, n_cells = power.fetch_area_series(var, *box)
    except power.PowerError as e:
        raise HTTPException(502, str(e))
    series = series.dropna()
    if start:
        series = series[series.index.year >= start]
    if end:
        series = series[series.index.year <= end]
    if len(series) < 120:
        raise HTTPException(422, "Need at least 10 years of data in the chosen period.")
    return series, n_cells


def _coverage(series) -> dict:
    """How complete is the record behind the verdict? Missing months stay missing (never filled)."""
    full = pd.date_range(series.index[0], series.index[-1], freq="MS")
    have = series.index.intersection(full)
    miss = full.difference(have)
    gap, run, prev = 0, 0, None
    for m in miss:
        run = run + 1 if prev is not None and (m.year * 12 + m.month) - (prev.year * 12 + prev.month) == 1 else 1
        gap, prev = max(gap, run), m
    pct = 100 * len(have) / len(full)
    msg = (f"Complete record: all {len(full)} months present." if not len(miss) else
           f"{len(have)} of {len(full)} months present ({pct:.0f}%); longest gap {gap} month{'s' if gap != 1 else ''}. "
           "Missing months are left out, never filled in.")
    return {"months_present": int(len(have)), "months_expected": int(len(full)), "percent": round(pct, 1),
            "longest_gap_months": int(gap), "headline": msg}


def _parse_box(txt: str) -> list[float]:
    try:
        b = [float(x) for x in txt.split(",")]
        assert len(b) == 4
    except Exception:
        raise HTTPException(422, "A box is lat_min,lat_max,lon_min,lon_max")
    return b


@app.get("/api/compare")
@memo
def compare_places(
    var: str, a: str = Query(..., description="lat_min,lat_max,lon_min,lon_max"), b: str = Query(...),
    name_a: str = Query("Place A", max_length=80), name_b: str = Query("Place B", max_length=80),
    start: int | None = Query(None, ge=1981, le=2025), end: int | None = Query(None, ge=1981, le=2025),
):
    """Are two places really changing differently? Tests the trend of A − B."""
    meta = _var(var)
    ba, bb = _parse_box(a), _parse_box(b)
    sa, na = _series(var, ba, start, end)
    sb, nb = _series(var, bb, start, end)
    try:
        out = cmp.compare(sa, sb, meta["units"], ba, bb, name_a, name_b)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _clean({"variable": meta, "n_cells": [na, nb], **out})


@app.get("/api/witnesses")
@memo
def all_witnesses(
    var: str,
    lat_min: float = Query(...), lat_max: float = Query(...),
    lon_min: float = Query(...), lon_max: float = Query(...),
):
    """Every independent record we can put next to NASA's for this place:
    the regional witnesses (Met Office, GPCP, ESA) plus ERA5 anywhere on Earth."""
    meta = _var(var)
    box = [lat_min, lat_max, lon_min, lon_max]
    series, _ = _series(var, box)
    out = []
    w = _witness(var, box, series, meta["units"])
    if w.get("available"):
        out.append(w)
    if meta.get("satellite"):
        try:
            from . import ndvi
            out.append(witnesses.compare_witness(
                "MODIS on NASA's Aqua satellite (since mid-2002)", "satellite",
                "A second satellite with its own sensor and calibration, passing over in the afternoon instead of the morning: "
                "independent of Terra's sensor drift, same kind of measurement",
                series, ndvi.monthly(box, platform="aqua", product=var), meta["units"],
                "Aqua passes 3 hours later than Terra, so daytime surface temperatures run warmer; compare direction." if var == "LST_DAY" else ""))
        except Exception as ex:
            out.append({"available": False, "name": "MODIS Aqua", "note": f"Aqua record unavailable ({type(ex).__name__})."})
    try:
        e = era5.monthly(var, (lat_min + lat_max) / 2, (lon_min + lon_max) / 2) if var in era5.MAP else None
        if e is not None:
            out.append(witnesses.compare_witness(
                "ERA5 (ECMWF reanalysis, via Open-Meteo)", "reanalysis",
                "Different centre and model, but shares many observations with MERRA-2: supporting, not fully independent",
                series, e, meta["units"], era5.MAP[var][2]))
    except Exception as ex:
        out.append({"available": False, "name": "ERA5", "note": f"ERA5 unavailable ({type(ex).__name__})."})
    if var in stations.MAP:
        try:
            st = stations.find_station(var, (lat_min + lat_max) / 2, (lon_min + lon_max) / 2)
            if st:
                w = witnesses.compare_witness(
                    f"Weather station {st['name']} ({st['distance_km']} km away)", "station",
                    "Independent: a real thermometer / rain gauge (NOAA GHCN), but one spot, not a ~50 km area",
                    series, stations.monthly(var, st["id"]), meta["units"],
                    "Station values describe one spot; compare direction and verdict.")
                w["station"] = st
                out.append(w)
            else:
                out.append({"available": False, "name": "Weather station", "note": "No long-running NOAA station within about 200 km."})
        except Exception as ex:
            out.append({"available": False, "name": "Weather station", "note": f"Station record unavailable ({type(ex).__name__})."})
    ok = [x for x in out if x.get("available")]
    agree = sum(bool(x.get("agrees")) for x in ok)
    head = (f"{agree} of {len(ok)} independent records agree with NASA's verdict." if ok
            else "No second witness available for this variable here.")
    return _clean({"variable": meta, "box": box, "witnesses": out, "n_agree": agree, "n_available": len(ok),
                   "headline": head, "credit": "ERA5: Copernicus Climate Change Service, served by Open-Meteo (CC BY 4.0). Stations: NOAA NCEI Global Summary of the Month (GHCN)."})


@app.get("/api/profile")
@memo
def place_profile(lat_min: float = Query(...), lat_max: float = Query(...),
                  lon_min: float = Query(...), lon_max: float = Query(...)):
    """What kind of place is this (from its own NASA data) and what is worth investigating here?"""
    box = [lat_min, lat_max, lon_min, lon_max]
    _bbox(*box)
    try:
        return _clean(guide.profile(box))
    except power.PowerError as e:
        raise HTTPException(502, str(e))


@app.get("/api/hunches")
def hunch_list():
    """Common beliefs about the weather that the app can test."""
    return {"hunches": [{"id": h["id"], "text": h["text"], "variable": h["var"]} for h in guide.HUNCHES]}


@app.get("/api/hunch")
@memo
def hunch_check(id: str, lat_min: float = Query(...), lat_max: float = Query(...),
                lon_min: float = Query(...), lon_max: float = Query(...)):
    """Fact-check one hunch at a place: real trend / leaning / not backed up / the opposite."""
    h = guide.BY_HUNCH.get(id)
    if not h:
        raise HTTPException(404, f"Unknown hunch '{id}'")
    box = [lat_min, lat_max, lon_min, lon_max]
    meta = _var(h["var"])
    series, _ = _series(h["var"], box)
    return _clean({"variable": meta, "box": box, **guide.hunch(h, series, meta["units"], (lat_min + lat_max) / 2)})


@app.post("/api/upload")
def upload(csv: str = Body(..., embed=True, max_length=2_000_000), units: str = Body("", embed=True, max_length=40),
           name: str = Body("Your data", embed=True, max_length=80)):
    """Your own record (e.g. a school weather station): two columns, date and value.
    Runs the same Detective, cross-examination and beyond-the-line checks."""
    try:
        series = guide.parse_csv(csv)
        result = stats.analyse(series, units)
    except ValueError as e:
        raise HTTPException(422, str(e))
    result["robustness"] = stats.robustness(series, units)
    xe = {k: f() for k, f in [("el_nino", lambda: crossexam.el_nino(series, units)),
                              ("leave_one_out", lambda: crossexam.leave_one_out(series)),
                              ("walk_forward", lambda: crossexam.walk_forward(series, units)),
                              ("all_windows", lambda: crossexam.all_windows(series)),
                              ("decades", lambda: crossexam.decades(series, units)),
                              ("extremes", lambda: crossexam.extremes(series, units))]}
    anomalies, _ = stats.deseasonalise(series)
    return _clean({"name": name, "result": result, "cross_exam": xe, "beyond": beyond.beyond(series),
                   "chart": {"dates": [d.strftime("%Y-%m") for d in series.index], "values": series.round(4).tolist(),
                             "anomalies": anomalies.round(4).tolist()}})


@app.get("/api/events")
@memo
def natural_events(lat_min: float = Query(...), lat_max: float = Query(...),
                   lon_min: float = Query(...), lon_max: float = Query(...)):
    """NASA EONET natural events (wildfires, storms, floods, volcanoes) near the place."""
    box = [lat_min, lat_max, lon_min, lon_max]
    _bbox(*box)
    try:
        return _clean(events.nearby(box))
    except Exception as e:
        raise HTTPException(502, f"NASA EONET unavailable ({type(e).__name__})")


@app.get("/api/models")
@memo
def climate_models(var: str, lat_min: float = Query(...), lat_max: float = Query(...),
                   lon_min: float = Query(...), lon_max: float = Query(...),
                   start: int | None = Query(None, ge=1981, le=2025), end: int | None = Query(None, ge=1981, le=2025)):
    """Did climate models see it coming? Observed NASA trend vs 7 CMIP6 HighResMIP models, + 2026–2050."""
    meta = _var(var)
    box = [lat_min, lat_max, lon_min, lon_max]
    series, _ = _series(var, box, start, end)
    a = stats.analyse(series, units=meta["units"])
    y0, y1 = int(a["start"][:4]), int(a["end"][:4])
    try:
        out = models.compare(var, (lat_min + lat_max) / 2, (lon_min + lon_max) / 2,
                             a["sen_slope_per_decade"], y0, y1, meta["units"])
    except Exception as e:
        raise HTTPException(502, f"Climate models unavailable: {e}"[:300])
    return _clean({"variable": meta, "box": box, "observed_label": a["verdict"]["label"], **out})


@app.get("/api/drought")
@memo
def drought_months(lat_min: float = Query(...), lat_max: float = Query(...),
                   lon_min: float = Query(...), lon_max: float = Query(...)):
    """Standardized Precipitation Index: drought months per year and the SPI-12 record."""
    box = [lat_min, lat_max, lon_min, lon_max]
    _bbox(*box)
    try:
        return _clean(drought.report(box))
    except power.PowerError as e:
        raise HTTPException(502, str(e))


@app.get("/api/extreme-days")
@memo
def extreme_days(lat_min: float = Query(...), lat_max: float = Query(...),
                 lon_min: float = Query(...), lon_max: float = Query(...)):
    """Hot days, 35 °C days, tropical nights, humid heat, frost nights, cold days per year (NASA POWER daily)."""
    box = [lat_min, lat_max, lon_min, lon_max]
    _bbox(*box)
    try:
        return _clean(heat.heat_report((lat_min + lat_max) / 2, (lon_min + lon_max) / 2))
    except power.PowerError as e:
        raise HTTPException(502, str(e))


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

    # satellite greenness is slow the first time: include it only once it has been read for this box
    from . import ndvi
    metas = [m for m in CATALOGUE if not m.get("satellite") or ndvi._cache_path(box, product=m["id"]).exists()]
    with ThreadPoolExecutor(6) as ex:
        items = list(ex.map(one, metas))
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
        "not_yet_read": [{"id": m["id"], "name": m["name"],
                          "note": "Satellite variable: open it once to read the images for this place (a few minutes)."}
                         for m in CATALOGUE if m not in metas],
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
    if meta.get("satellite"):
        raise HTTPException(422, "The grid map is for NASA POWER variables; greenness is analysed for the whole box.")
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
    try:
        control = stats.shuffled_control(df[[c["id"] for c in cells]])
    except Exception as e:  # never break the map
        control = {"headline": f"Control unavailable ({type(e).__name__})."}
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
        "shuffled_control": control,
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
