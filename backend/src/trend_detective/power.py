"""NASA POWER client (https://power.larc.nasa.gov), monthly data, no login needed.

POWER serves NASA MERRA-2 (meteorology) and CERES / GEWEX SRB (solar) data
at the source grid (0.5 deg lat x 0.625 deg lon for MERRA-2).

API limits found on 14 Nov 2026: regional requests take 1 parameter at a time
and at most 10 x 10 degrees. Fill value is -999. Monthly responses include a
13th "month" per year (the annual mean), which we drop.

Responses are cached on disk so demos never depend on a live server.

AI-use note: drafted with Claude (Anthropic) during the hackathon; checked by
the team against live API responses.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

BASE = "https://power.larc.nasa.gov/api/temporal/monthly"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
FILL = -999.0
START_YEAR, END_YEAR = 1981, 2025
MAX_SPAN = 10.0
# Seconds to wait after each 429. The web app keeps this short; batch scripts
# can set POWER_RETRY_WAITS="5,15,30,60,120".
RETRY_WAITS = [float(x) for x in os.environ.get("POWER_RETRY_WAITS", "2,5,10").split(",")]
# Live requests go out one at a time, at least MIN_GAP seconds apart (cached
# responses are instant and skip this).
MIN_GAP = float(os.environ.get("POWER_MIN_GAP", "0.4"))
_PACE = threading.Lock()
_last = [0.0]


class PowerError(RuntimeError):
    pass


def _get(kind: str, params: dict, base: str = BASE) -> dict:
    key = hashlib.sha1(json.dumps([kind, params] + ([base] if base != BASE else []), sort_keys=True).encode()).hexdigest()[:16]
    path = CACHE / f"{kind}_{params['parameters']}_{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    q = {**params, "community": "AG", "format": "JSON"}
    # NASA POWER rate-limits bursts (HTTP 429): wait and retry with backoff.
    for wait in RETRY_WAITS:
        with _PACE:  # one live request at a time, spaced out, so we never burst
            gap = MIN_GAP - (time.monotonic() - _last[0])
            if gap > 0:
                time.sleep(gap)
            r = httpx.get(f"{base}/{kind}", params=q, timeout=180)
            _last[0] = time.monotonic()
        if r.status_code != 429:
            break
        time.sleep(wait)
    if r.status_code != 200:
        try:
            msg = "; ".join(r.json().get("messages", [])) or r.text[:300]
        except Exception:
            msg = r.text[:300]
        raise PowerError(f"NASA POWER {r.status_code}: {msg}")
    data = r.json()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def _to_series(values: dict) -> pd.Series:
    """{'198101': 3.1, ..., '198113': annual} -> monthly Series, NaN for fill."""
    rows = [(k, v) for k, v in values.items() if 1 <= int(k[4:]) <= 12]
    idx = pd.to_datetime([k + "01" for k, _ in rows], format="%Y%m%d")
    s = pd.Series([v for _, v in rows], index=idx, dtype=float)
    return s.where(s != FILL).sort_index()


def fetch_point(param: str, lat: float, lon: float, start=START_YEAR, end=END_YEAR) -> pd.Series:
    d = _get(
        "point",
        {"parameters": param, "latitude": round(lat, 3), "longitude": round(lon, 3), "start": start, "end": end},
    )
    return _to_series(d["properties"]["parameter"][param]).rename(param)


def fetch_region(param: str, lat_min, lat_max, lon_min, lon_max, start=START_YEAR, end=END_YEAR):
    """Gridded monthly data for a box. Returns (DataFrame time x cell, cells list)."""
    if lat_max - lat_min > MAX_SPAN or lon_max - lon_min > MAX_SPAN:
        raise PowerError("Region too large: NASA POWER allows at most 10 x 10 degrees")
    d = _get(
        "regional",
        {
            "parameters": param,
            "latitude-min": round(lat_min, 2),
            "latitude-max": round(lat_max, 2),
            "longitude-min": round(lon_min, 2),
            "longitude-max": round(lon_max, 2),
            "start": start,
            "end": end,
        },
    )
    cols, cells = {}, []
    for i, f in enumerate(d["features"]):
        lon, lat = f["geometry"]["coordinates"][:2]
        cols[i] = _to_series(f["properties"]["parameter"][param])
        cells.append({"id": i, "lat": lat, "lon": lon})
    return pd.DataFrame(cols), cells


def area_mean(df: pd.DataFrame, cells: list[dict]) -> pd.Series:
    """Area-weighted (cos latitude) mean over grid cells."""
    w = np.array([np.cos(np.radians(c["lat"])) for c in cells])
    vals = df[[c["id"] for c in cells]].to_numpy()
    mask = np.isfinite(vals)
    num = np.where(mask, vals, 0) @ w
    den = mask @ w
    return pd.Series(np.where(den > 0, num / np.where(den > 0, den, 1), np.nan), index=df.index)


MIN_SPAN = 2.0  # POWER regional endpoint needs >= 2 degrees each way


def _widen(lo: float, hi: float, lim: float) -> tuple[float, float]:
    if hi - lo >= MIN_SPAN:
        return lo, hi
    mid = (lo + hi) / 2
    lo, hi = mid - MIN_SPAN / 2, mid + MIN_SPAN / 2
    if lo < -lim:
        lo, hi = -lim, -lim + MIN_SPAN
    if hi > lim:
        lo, hi = lim - MIN_SPAN, lim
    return lo, hi


def fetch_area_series(param: str, lat_min, lat_max, lon_min, lon_max) -> tuple[pd.Series, int]:
    """Regional mean series over grid cells whose centres fall inside the box.

    Small boxes are fetched as a 2-degree box and then trimmed back. If no cell
    centre is inside, the nearest cell to the box centre is used.
    """
    if lat_max - lat_min > MAX_SPAN or lon_max - lon_min > MAX_SPAN:
        raise PowerError("Region too large: NASA POWER allows at most 10 x 10 degrees")
    if param == "NDVI":  # satellite greenness, not a POWER parameter
        from . import ndvi
        try:
            s = ndvi.monthly([lat_min, lat_max, lon_min, lon_max])
        except Exception as e:
            raise PowerError(f"MODIS greenness unavailable: {e}") from e
        return s, ndvi.equivalent_cells([lat_min, lat_max, lon_min, lon_max])
    qlat = _widen(lat_min, lat_max, 90)
    qlon = _widen(lon_min, lon_max, 180)
    df, cells = fetch_region(param, qlat[0], qlat[1], qlon[0], qlon[1])
    inside = [c for c in cells if lat_min <= c["lat"] <= lat_max and lon_min <= c["lon"] <= lon_max]
    if not inside:
        clat, clon = (lat_min + lat_max) / 2, (lon_min + lon_max) / 2
        inside = [min(cells, key=lambda c: (c["lat"] - clat) ** 2 + (c["lon"] - clon) ** 2)]
    return area_mean(df, inside), len(inside)


DAILY_BASE = "https://power.larc.nasa.gov/api/temporal/daily"


def fetch_daily_point(params: list[str], lat: float, lon: float, start: int = START_YEAR, end: int = END_YEAR) -> pd.DataFrame:
    """Daily values at one point (one request for several parameters)."""
    d = _get("point", {"parameters": ",".join(params), "latitude": round(lat, 3), "longitude": round(lon, 3),
                       "start": f"{start}0101", "end": f"{end}1231"}, base=DAILY_BASE)
    cols = {}
    for p in params:
        raw = d["properties"]["parameter"][p]
        s = pd.Series({pd.Timestamp(k): v for k, v in raw.items()}, dtype=float)
        cols[p] = s.where(s != FILL)
    return pd.DataFrame(cols).sort_index()
