"""NASA GLDAS-2.1 Noah land model (0.25°, monthly, 2000 onward) as a second soil-moisture witness.

GLDAS is a different NASA land model from MERRA-2's, driven by different weather inputs
(NOAA GDAS analysis, GPCP rainfall, AGRMET sunshine). If both models show the same soil
trend, the trend is less likely to be a quirk of one model. Both are models, though, so
this is a consistency check, not independent proof; ESA CCI satellite soil moisture is our
independent soil witness where we have it.

Only the box is read: NASA's cloud OPeNDAP returns the 0.25° cells inside it for each
month. Needs a NASA Earthdata token in backend/.env (EARTHDATA_TOKEN) with the
"NASA GESDISC DATA ARCHIVE" app approved (the same one IMERG uses).

GWETTOP  <- SoilMoi0_10cm_inst  (water in the top 10 cm, kg/m²)
GWETROOT <- RootMoist_inst       (root-zone water, kg/m²)

Reference: Beaudoing, H. and M. Rodell (2020), GLDAS Noah Land Surface Model L4 monthly
0.25 x 0.25 degree V2.1, NASA GES DISC, doi:10.5067/SXAVCZFAQLNO. Rodell, M. et al. (2004),
The Global Land Data Assimilation System, BAMS 85, 381–394.

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
NAME = "NASA GLDAS-2.1 Noah land model (since 2000)"
CREDIT = "Beaudoing & Rodell (2020), GLDAS Noah L4 monthly 0.25° V2.1, NASA GES DISC, doi:10.5067/SXAVCZFAQLNO"
INDEPENDENCE = ("Partly independent: a different NASA land model with different weather and rain inputs, "
                "but still a model, not a measurement, so not fully independent")
FIELDS = {"GWETTOP": "SoilMoi0_10cm_inst", "GWETROOT": "RootMoist_inst"}
UNITS_NOTE = "GLDAS reports kg/m² of water; NASA POWER a 0–1 wetness fraction, so compare direction, not size."
_lock = threading.Lock()


class GldasError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def granules() -> dict[str, str]:
    """'YYYY-MM' -> OPeNDAP URL for every monthly file (NASA CMR, no login)."""
    out, page = {}, 1
    while True:
        r = httpx.get(CMR, params={"short_name": "GLDAS_NOAH025_M", "version": "2.1", "page_size": 500,
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
    """lat -59.875..89.875 (600), lon -179.875..179.875 (1440), 0.25° cells overlapping the box."""
    la0, la1, lo0, lo1 = box
    eps = 1e-6
    i0 = max(0, int(math.floor((lo0 + 180) / 0.25 + eps)))
    i1 = min(1439, max(i0, int(math.ceil((lo1 + 180) / 0.25 - eps)) - 1))
    j0 = max(0, int(math.floor((la0 + 60) / 0.25 + eps)))
    j1 = min(599, max(j0, int(math.ceil((la1 + 60) / 0.25 - eps)) - 1))
    return i0, i1, j0, j1


def _parse(text: str):
    lat, rows = None, {f: [] for f in FIELDS.values()}
    for line in text.splitlines():
        if line.startswith("/lat,"):
            lat = np.array([float(x) for x in line.split(",")[1:]])
        for f in FIELDS.values():
            if line.startswith(f"/{f}["):
                rows[f].append([float(x) for x in line.split(",")[1:]])
        if line.startswith("Error"):
            raise GldasError(text[:300])
    if lat is None or not all(rows.values()):
        raise GldasError("Unexpected OPeNDAP reply")
    return lat, {f: np.array(v) for f, v in rows.items()}  # each: lat x lon


def _box_means(url: str, box, client: httpx.Client) -> dict:
    i0, i1, j0, j1 = _indices(box)
    ce = ";".join([f"/{f}[0][{j0}:{j1}][{i0}:{i1}]" for f in FIELDS.values()] + [f"/lat[{j0}:{j1}]"])
    last = None
    for attempt in range(4):
        try:
            r = client.get(url + ".dap.csv", params={"dap4.ce": ce})
            if r.status_code == 200:
                lat, arrs = _parse(r.text)
                out = {}
                for var, f in FIELDS.items():
                    p = arrs[f]
                    p = np.where(p < -9000, np.nan, p)  # fill value -9999 (sea, ice)
                    w = np.cos(np.radians(lat))[:, None] * np.ones_like(p)
                    ok = np.isfinite(p)
                    out[var] = float((p[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else None
                return out
            last = f"HTTP {r.status_code}: {r.text[:160]}"
            if r.status_code in (401, 403):
                break
        except (httpx.HTTPError, GldasError) as e:
            last = str(e)[:160]
        time.sleep(1 + 2 * attempt)
    raise GldasError(f"GLDAS read failed: {last}")


def _cache_path(box) -> Path:
    return CACHE / ("gldas_" + "_".join(f"{v:+.2f}" for v in box) + ".json")


def monthly(var: str, box, workers: int = 8) -> pd.Series:
    """Box-mean GLDAS soil water for GWETTOP / GWETROOT, one value per month (cached; both layers read together)."""
    if var not in FIELDS:
        raise GldasError(f"No GLDAS field for {var}")
    box = [float(v) for v in box]
    path = _cache_path(box)
    cached = json.loads(path.read_text()) if path.exists() else {}
    if not cached or max(cached) < "2025-06":
        todo = {m: u for m, u in granules().items() if m not in cached and m <= "2025-12"}
        if todo:
            if not creds.earthdata_token():
                raise GldasError("No Earthdata token: put EARTHDATA_TOKEN in backend/.env")
            with httpx.Client(headers=creds.earthdata_headers(), follow_redirects=True, timeout=90) as c, \
                    ThreadPoolExecutor(workers) as ex:
                months = sorted(todo)
                for m, v in zip(months, ex.map(lambda k: _box_means(todo[k], box, c), months)):
                    cached[m] = v
            with _lock:
                CACHE.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(dict(sorted(cached.items()))))
    s = pd.Series({pd.Timestamp(k + "-01"): (v or {}).get(var) for k, v in cached.items()}, dtype=float).sort_index()
    return s.dropna().rename("GLDAS")
