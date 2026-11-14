"""Satellite variables from NASA MODIS (Collection 6.1), read per box:

  NDVI       vegetation greenness, MOD13Q1 (250 m, 16-day)
  LST_DAY    land surface temperature by day, MOD11A2 (1 km, 8-day, ~10:30 local)
  LST_NIGHT  land surface temperature at night, MOD11A2 (~22:30 local)

(Aqua's MYD13Q1 / MYD11A2 serve as an independent second satellite.)

Greenness details:

16-day composites at 250 m, February 2000 onward. We read the Cloud-Optimised
GeoTIFF copies on Microsoft Planetary Computer (open access; a free anonymous
read token is fetched automatically), average the good-quality land pixels in
the box (pixel_reliability 0 = good or 1 = marginal; water and snow left out),
and turn the composites into a monthly series that the same stats engine tests.

Why Collection 6.1 matters: older MODIS Terra NDVI (Collection 5) showed a fake
"browning" because the sensor's blue band was slowly degrading (Lyapustin et
al. 2014, Atmos. Meas. Tech.). C6/6.1 corrected the calibration, so a trend in
this record is not that artefact.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import httpx

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/modiseuwest/modis-061-cogs"  # token for the COG container
COLLECTION = "modis-13Q1-061"
R = 6371007.181  # MODIS sinusoidal sphere radius (m)
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
MAX_PIXELS = 160  # read at most ~160 x 160 pixels per composite (overviews do the rest)
SOURCE = "NASA MODIS Terra MOD13Q1 v6.1 (250 m, 16-day), via Microsoft Planetary Computer"


def _ndvi_good(v, q):
    return ((q == 0) | (q == 1)) & (v > 0)  # good/marginal land pixels, no water/snow/cloud


def _lst_good(v, q):
    return ((q & 3) <= 1) & (v > 0)  # QC bits 0-1: 00 good, 01 produced (other quality); 0 = fill


PRODUCTS = {
    "NDVI": {"collection": "modis-13Q1-061", "prefix": {"terra": "MOD13Q1.", "aqua": "MYD13Q1."},
             "value": "250m_16_days_NDVI", "qa": "250m_16_days_pixel_reliability", "good": _ndvi_good,
             "scale": 1e-4, "offset": 0.0, "tag": "ndvi3_"},
    "LST_DAY": {"collection": "modis-11A2-061", "prefix": {"terra": "MOD11A2.", "aqua": "MYD11A2."},
                "value": "LST_Day_1km", "qa": "QC_Day", "good": _lst_good, "scale": 0.02, "offset": -273.15,
                "tag": "lstday_"},
    "LST_NIGHT": {"collection": "modis-11A2-061", "prefix": {"terra": "MOD11A2.", "aqua": "MYD11A2."},
                  "value": "LST_Night_1km", "qa": "QC_Night", "good": _lst_good, "scale": 0.02, "offset": -273.15,
                  "tag": "lstnight_"},
}

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("GDAL_INGESTED_BYTES_AT_OPEN", "65536")
os.environ.setdefault("GDAL_HTTP_MULTIPLEX", "YES")
os.environ.setdefault("GDAL_HTTP_VERSION", "2")

_lock = threading.Lock()
_token: dict = {}


class NdviError(RuntimeError):
    pass


def _sas() -> str:
    with _lock:
        if _token.get("exp", 0) - time.time() > 300:
            return _token["t"]
        r = httpx.get(TOKEN, timeout=30)
        r.raise_for_status()
        d = r.json()
        _token["t"] = d["token"]
        _token["exp"] = time.time() + 45 * 60
        return _token["t"]


def _post(body: dict) -> dict:
    last = None
    for attempt in range(4):
        try:
            with httpx.Client(timeout=httpx.Timeout(45, connect=15)) as c:
                r = c.post(STAC, json=body)
                r.raise_for_status()
                return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 3 * attempt)
    raise NdviError(f"Satellite catalogue unreachable: {last}")


def _items(box: list[float], start: str = "2000-01-01", end: str = "2025-12-31", platform: str = "terra",
           product: str = "NDVI") -> list[dict]:
    """All Terra (or Aqua) composites touching the box (one per tile per date), oldest first."""
    la0, la1, lo0, lo1 = box
    poly = {"type": "Polygon", "coordinates": [[[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]]}
    P = PRODUCTS[product]
    body = {"collections": [P["collection"]], "intersects": poly,
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 1000}
    # newer items have no "platform" field, so filter on the product name (MOD = Terra, MYD = Aqua)
    prefix = P["prefix"][platform]
    out = {}
    while body:
        d = _post(body)
        for f in d["features"]:
            if not f["id"].startswith(prefix):
                continue
            tile = f["id"].split(".")[2]  # e.g. h17v03
            key = (f["id"].split(".")[1], tile)  # acquisition date code + tile
            if key in out and out[key]["id"] > f["id"]:  # keep the latest reprocessing only
                continue
            out[key] = {"id": f["id"], "date": (f["properties"].get("start_datetime") or f["properties"]["datetime"])[:10],
                        "ndvi": f["assets"][P["value"]]["href"],
                        "rel": f["assets"][P["qa"]]["href"],
                        "transform": f["properties"]["proj:transform"],
                        "shape": f["properties"]["proj:shape"]}
        nxt = next((l for l in d.get("links", []) if l.get("rel") == "next"), None)
        body = nxt.get("body") if nxt else None
    return sorted(out.values(), key=lambda x: (x["date"], x["id"]))


def _sinu(lat: float, lon: float) -> tuple[float, float]:
    return R * math.radians(lon) * math.cos(math.radians(lat)), R * math.radians(lat)


def _window(box, item):
    """Pixel window (rows, cols) of the box's bounding rectangle inside this tile, or None."""
    a, _, x0, _, e, y0 = item["transform"][:6]
    h, w = item["shape"]
    xs, ys = [], []
    for la in np.linspace(box[0], box[1], 7):
        for lo in (box[2], box[3]):
            x, y = _sinu(la, lo)
            xs.append(x)
            ys.append(y)
    c0 = max(0, int((min(xs) - x0) / a))
    c1 = min(w, int(math.ceil((max(xs) - x0) / a)))
    r0 = max(0, int((max(ys) - y0) / e))
    r1 = min(h, int(math.ceil((min(ys) - y0) / e)))
    if c1 - c0 < 1 or r1 - r0 < 1:
        return None
    return r0, r1, c0, c1


def _in_box(box, item, win, shape) -> np.ndarray:
    """Which sampled pixels have their centre inside the lat/lon box (the sinusoidal grid is skewed)."""
    a, _, x0, _, e, y0 = item["transform"][:6]
    r0, r1, c0, c1 = win
    nr, nc = shape
    y = y0 + e * (r0 + (np.arange(nr) + 0.5) * (r1 - r0) / nr)
    x = x0 + a * (c0 + (np.arange(nc) + 0.5) * (c1 - c0) / nc)
    lat = np.degrees(y / R)[:, None]
    lon = np.degrees(x[None, :] / (R * np.cos(np.radians(lat))))
    return (lat >= box[0]) & (lat <= box[1]) & (lon >= box[2]) & (lon <= box[3])


def _read_one(box, item, product: str = "NDVI") -> tuple[str, float, int, int]:
    """(date, sum of good values in physical units, good pixel count, pixels in the box) for one tile-date."""
    P = PRODUCTS[product]
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import Window

    win = _window(box, item)
    if win is None:
        return item["date"], 0.0, 0, 0
    r0, r1, c0, c1 = win
    step = max(1, math.ceil(max(r1 - r0, c1 - c0) / MAX_PIXELS))
    shape = (max(1, (r1 - r0) // step), max(1, (c1 - c0) // step))
    inside = _in_box(box, item, win, shape)
    if not inside.any():
        return item["date"], 0.0, 0, 0
    w = Window(c0, r0, c1 - c0, r1 - r0)
    tok = _sas()
    last = None
    for attempt in range(3):
        try:
            with rasterio.open(f"{item['ndvi']}?{tok}") as src:
                v = src.read(1, window=w, out_shape=shape, resampling=Resampling.nearest)
            with rasterio.open(f"{item['rel']}?{tok}") as src:
                q = src.read(1, window=w, out_shape=shape, resampling=Resampling.nearest)
            good = inside & P["good"](v, q)
            vals = v[good].astype(float) * P["scale"] + P["offset"]
            return item["date"], float(vals.sum()), int(good.sum()), int(inside.sum())
        except Exception as e:  # noqa: BLE001 — network hiccups on a public bucket
            last = e
            time.sleep(1 + attempt * 2)
    raise NdviError(f"Could not read {item['id']}: {last}")


def _cache_path(box, platform: str = "terra", product: str = "NDVI") -> Path:
    base = PRODUCTS[product]["tag"]
    tag = base if platform == "terra" else f"{base}{platform}_"
    return CACHE / (tag + "_".join(f"{v:+.2f}" for v in box) + ".json")


def composites(box: list[float], workers: int = 16, platform: str = "terra", product: str = "NDVI") -> dict[str, float | None]:
    """Box-mean NDVI for every 16-day composite, all tiles combined (cached; only missing dates are read).
    A date counts only if at least 5% of the box's pixels were clear land."""
    path = _cache_path(box, platform, product)
    cached = json.loads(path.read_text()) if path.exists() else {}
    items = _items(box, platform=platform, product=product)
    if not items:
        raise NdviError("No MODIS composites found here.")
    todo = [it for it in items if it["date"] not in cached]
    if todo:
        acc: dict[str, list] = {}
        with ThreadPoolExecutor(workers) as ex:
            for date, tot, n, n_in in ex.map(lambda it: _read_one(box, it, product), todo):
                a = acc.setdefault(date, [0.0, 0, 0])
                a[0] += tot
                a[1] += n
                a[2] += n_in
        for date, (tot, n, n_in) in acc.items():
            cached[date] = tot / n if n_in and n >= max(1, 0.05 * n_in) else None
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(sorted(cached.items()))))
    return cached


def monthly(box: list[float], platform: str = "terra", product: str = "NDVI") -> pd.Series:
    """Monthly mean (composites assigned to the month they start in)."""
    c = composites(box, platform=platform, product=product)
    s = pd.Series({pd.Timestamp(k): v for k, v in c.items()}, dtype=float).sort_index()
    m = s.resample("MS").mean()
    m = m[(m.index >= "2000-03-01") & (m.index <= "2025-12-01")]
    if m.notna().sum() < 120:
        raise NdviError("Too few clear MODIS views here (clouds, snow or sea) for a 10-year record.")
    return m.rename(product)


def cached_monthly(box: list[float]) -> pd.Series | None:
    """The monthly series only if it is already cached (for slow-path guards)."""
    return monthly(box) if _cache_path(box).exists() else None


def equivalent_cells(box: list[float]) -> int:
    """MODIS resolves 250 m, so any box is well resolved; report how many ~50 km POWER cells it spans
    (at least 4, so the resolution check reads 'resolved')."""
    return max(4, round((box[1] - box[0]) / 0.5 * (box[3] - box[2]) / 0.625))
