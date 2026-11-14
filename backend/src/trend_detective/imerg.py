"""NASA GPM IMERG Final Run V07 monthly rainfall (GPM_3IMERGM v07, 0.1°, 1998 onward)
as an independent satellite rainfall witness for any box on Earth.

Only the box is downloaded: NASA's cloud OPeNDAP returns the 0.1° cells inside it for
each month (a few kB). Needs a NASA Earthdata token in backend/.env (EARTHDATA_TOKEN)
and the "NASA GESDISC DATA ARCHIVE" app approved on that account.

IMERG merges microwave and infrared satellite rain estimates and calibrates them with
GPCC rain gauges. MERRA-2's corrected rain also uses gauge data, so agreement is strong
but not fully independent evidence. Units: IMERG gives mm/hour; we report mm/day.

Reference: Huffman, G. J. et al. (2023). GPM IMERG Final Precipitation L3 1 month 0.1°
V07, NASA GES DISC, doi:10.5067/GPM/IMERG/3B-MONTH/07.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from . import creds

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
NAME = "NASA GPM IMERG satellite rainfall (V07, since 1998)"
CREDIT = "Huffman et al. (2023), GPM IMERG Final V07 monthly, NASA GES DISC, doi:10.5067/GPM/IMERG/3B-MONTH/07"
_lock = threading.Lock()


class ImergError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def granules() -> dict[str, str]:
    """'YYYY-MM' -> OPeNDAP URL for every monthly file (from NASA's CMR catalogue, no login)."""
    out, page = {}, 1
    while True:
        r = httpx.get(CMR, params={"short_name": "GPM_3IMERGM", "version": "07", "page_size": 500,
                                   "page_num": page, "sort_key": "start_date"}, timeout=60)
        r.raise_for_status()
        entries = r.json()["feed"]["entry"]
        for e in entries:
            od = next((l["href"] for l in e["links"] if "opendap.earthdata.nasa.gov" in l["href"]), None)
            if od:
                out[e["time_start"][:7]] = od
        if len(entries) < 500:
            return out
        page += 1


def _indices(box):
    la0, la1, lo0, lo1 = box
    eps = 1e-6  # 52.6 / 0.1 is 525.99999… in floating point
    i0 = max(0, int(math.floor((lo0 + 180) / 0.1 + eps)))
    i1 = min(3599, max(i0, int(math.ceil((lo1 + 180) / 0.1 - eps)) - 1))
    j0 = max(0, int(math.floor((la0 + 90) / 0.1 + eps)))
    j1 = min(1799, max(j0, int(math.ceil((la1 + 90) / 0.1 - eps)) - 1))
    return i0, i1, j0, j1


def _parse(csv_text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lon, lat, rows = None, None, []
    for line in csv_text.splitlines():
        if line.startswith("/Grid/lon,"):
            lon = np.array([float(x) for x in line.split(",")[1:]])
        elif line.startswith("/Grid/lat,"):
            lat = np.array([float(x) for x in line.split(",")[1:]])
        elif line.startswith("/Grid/precipitation["):
            rows.append([float(x) for x in line.split(",")[1:]])
        elif line.startswith("Error"):
            raise ImergError(csv_text[:300])
    if lon is None or lat is None or not rows:
        raise ImergError("Unexpected OPeNDAP reply")
    return lon, lat, np.array(rows)  # rows: lon x lat


def _box_mean(url: str, box, client: httpx.Client) -> float | None:
    i0, i1, j0, j1 = _indices(box)
    ce = f"/Grid/precipitation[0][{i0}:{i1}][{j0}:{j1}];/Grid/lon[{i0}:{i1}];/Grid/lat[{j0}:{j1}]"
    last = None
    for attempt in range(4):
        try:
            r = client.get(url + ".dap.csv", params={"dap4.ce": ce})
            if r.status_code == 200:
                lon, lat, p = _parse(r.text)
                p = np.where(p < 0, np.nan, p)  # fill value -9999.9
                w = np.cos(np.radians(lat))[None, :] * np.ones_like(p)
                ok = np.isfinite(p)
                return float((p[ok] * w[ok]).sum() / w[ok].sum()) * 24 if ok.any() else None  # mm/h -> mm/day
            last = f"HTTP {r.status_code}: {r.text[:160]}"
            if r.status_code in (401, 403):
                break
        except (httpx.HTTPError, ImergError) as e:
            last = str(e)[:160]
        time.sleep(1 + 2 * attempt)
    raise ImergError(f"IMERG read failed: {last}")


def _cache_path(box) -> Path:
    return CACHE / ("imerg_" + "_".join(f"{v:+.2f}" for v in box) + ".json")


def monthly(box: list[float], workers: int = 8) -> pd.Series:
    """Box-mean IMERG rainfall, mm/day, one value per month (cached; only new months are read)."""
    path = _cache_path(box)
    cached = json.loads(path.read_text()) if path.exists() else {}
    todo = {}
    if not cached or max(cached) < "2025-09":  # IMERG Final runs ~3 months behind; Sep 2025 is the last month here
        todo = {m: u for m, u in granules().items() if m not in cached and m <= "2025-12"}
    if todo:
        if not creds.earthdata_token():
            raise ImergError("No Earthdata token: put EARTHDATA_TOKEN in backend/.env")
        with httpx.Client(headers=creds.earthdata_headers(), follow_redirects=True, timeout=90) as c, \
                ThreadPoolExecutor(workers) as ex:
            months = sorted(todo)
            for m, v in zip(months, ex.map(lambda k: _box_mean(todo[k], box, c), months)):
                cached[m] = v
        with _lock:
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(dict(sorted(cached.items()))))
    s = pd.Series({pd.Timestamp(k + "-01"): v for k, v in cached.items()}, dtype=float).sort_index()
    return s.dropna().rename("IMERG")
