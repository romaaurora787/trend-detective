"""Nearest long-running weather station as a witness: NOAA NCEI Global Summary
of the Month (GHCN stations worldwide; listed in the challenge Resources as NOAA
Climate Data Online). Search and data services need no token.

A thermometer in one spot is a different thing from a ~50 km model cell, so we
compare direction and verdict, not exact size, and show the distance.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path

import httpx
import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
SEARCH = "https://www.ncei.noaa.gov/access/services/search/v1/data"
DATA = "https://www.ncei.noaa.gov/access/services/data/v1"
# NASA variable -> GSOM data type, conversion
MAP = {"T2M": ("TAVG", None), "T2M_MAX": ("TMAX", None), "T2M_MIN": ("TMIN", None),
       "PRECTOTCORR": ("PRCP", "per_day"), "FROST_DAYS": ("DT32", None)}
_LOCK = threading.Lock()


def _get_json(url, params, cache_name):
    f = CACHE / cache_name
    if f.exists():
        return json.loads(f.read_text())
    with _LOCK:
        r = httpx.get(url, params=params, timeout=60)
        r.raise_for_status()
        d = r.json()
    f.write_text(json.dumps(d))
    return d


def _km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def find_station(var: str, lat: float, lon: float) -> dict | None:
    dtype = MAP[var][0]
    for half in (1.0, 2.0):
        key = f"ghcn_search_{dtype}_{lat:+.2f}_{lon:+.2f}_{half}.json"
        d = _get_json(SEARCH, {"dataset": "global-summary-of-the-month",
                               "bbox": f"{lat + half},{lon - half},{lat - half},{lon + half}",
                               "startDate": "1981-01-01T00:00:00", "endDate": "2025-12-31T23:59:59",
                               "dataTypes": dtype, "limit": 100}, key)
        best = None
        for r in d.get("results", []):
            st = r["stations"][0]
            dt = next((x for x in st.get("dataTypes", []) + r.get("dataTypes", []) if x["id"] == dtype), None)
            if not dt:
                continue
            y0 = max(1981, int(dt["startDate"][:4]))
            y1 = min(2025, int(dt["endDate"][:4]))
            years = y1 - y0 + 1
            if years < 20 or dt.get("coverage", 0) < 80:
                continue
            slon, slat = r["location"]["coordinates"]
            dist = _km(lat, lon, slat, slon)
            score = years * dt["coverage"] / 100 - dist / 50
            if best is None or score > best["score"]:
                best = {"id": st["id"], "name": st["name"], "lat": slat, "lon": slon, "distance_km": round(dist),
                        "years": f"{y0}–{y1}", "coverage": dt["coverage"], "score": score}
        if best:
            return best
    return None


def monthly(var: str, station_id: str) -> pd.Series:
    dtype, conv = MAP[var]
    d = _get_json(DATA, {"dataset": "global-summary-of-the-month", "stations": station_id,
                         "startDate": "1981-01-01", "endDate": "2025-12-31", "dataTypes": dtype,
                         "units": "metric", "format": "json"}, f"ghcn_{station_id}_{dtype}.json")
    rows = [(pd.Timestamp(r["DATE"] + "-01"), float(r[dtype])) for r in d if r.get(dtype) not in (None, "")]
    s = pd.Series(dict(rows), dtype=float).sort_index()
    if conv == "per_day":
        s = s / s.index.days_in_month
    return s
