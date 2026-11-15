"""B3: the whole-world dataset for the globe (every ~2° cell, land and sea).

Reads NASA MERRA-2 monthly means (the same source NASA POWER uses for these variables)
straight from NASA's cloud OPeNDAP, one global file per month, keeping every 4th grid
point: 2° latitude x 2.5° longitude = 91 x 144 = 13,104 cells, Jan 1981 to Dec 2025.

For every cell it runs the same tests as the rest of the site:
  typical  : straight line on monthly anomalies, months treated as independent (p < 0.05)
  verdict  : our test - Hamed-Rao Mann-Kendall AND OLS with effective sample size
             (strong / some = proven, mixed, none)
  fdr      : survives the Benjamini-Hochberg false-discovery check across all cells (q = 0.10)
  luck     : the typical test on the same cell with its years shuffled (no trend can exist),
             i.e. how many "trends" a simple test finds in pure luck
  luck_ours: our test on the shuffled years (should be ~5%)

Output: data/globe_<VAR>.json (compact rows), served by /api/globe?var=.
Raw monthly grids are cached in data/cache/globe_raw/ (gitignored, ~28 MB per variable).
Needs EARTHDATA_TOKEN in backend/.env (GES DISC app approved).

    uv run python scripts/globe_grid.py T2M PRECTOTCORR

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import pymannkendall as mk
from scipy import stats as sps

from trend_detective import creds, stats

warnings.filterwarnings("ignore")
DATA = Path(__file__).resolve().parents[1] / "data"
RAW = DATA / "cache" / "globe_raw"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
STEP = 4  # every 4th point of 361 x 576 -> 2° x 2.5°
VARS = {  # our id -> (MERRA-2 collection, field, scale to POWER units, units)
    "T2M": ("M2TMNXSLV", "T2M", lambda x: x - 273.15, "°C"),
    "PRECTOTCORR": ("M2TMNXFLX", "PRECTOTCORR", lambda x: x * 86400.0, "mm/day"),
}
MONTHS = [f"{y}-{m:02d}" for y in range(1981, 2026) for m in range(1, 13)]


def granules(short_name: str) -> dict[str, str]:
    out, page = {}, 1
    while True:
        r = httpx.get(CMR, params={"short_name": short_name, "version": "5.12.4", "page_size": 500,
                                   "page_num": page, "sort_key": "start_date"}, timeout=60)
        r.raise_for_status()
        es = r.json()["feed"]["entry"]
        for e in es:
            od = next((l["href"] for l in e["links"] if "opendap.earthdata.nasa.gov" in l["href"]), None)
            if od:
                out[e["time_start"][:7]] = od
        if len(es) < 500:
            return out
        page += 1


def _get(client, url, field, t_index=True):
    ce = f"/{field}" + ("[0]" if t_index else "") + f"[0:{STEP}:360][0:{STEP}:575]"
    last = None
    for attempt in range(5):
        try:
            r = client.get(url + ".dap.csv", params={"dap4.ce": ce})
            if r.status_code == 200:
                rows = [[float(x) for x in line.split(",")[1:]] for line in r.text.splitlines()
                        if line.startswith(f"/{field}[")]
                a = np.array(rows, dtype=np.float32)
                if a.shape == (91, 144):
                    return a
                last = f"shape {a.shape}"
            else:
                last = f"HTTP {r.status_code}"
                if r.status_code in (401, 403):
                    break
        except httpx.HTTPError as e:
            last = str(e)[:120]
        time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"{field}: {last}")


def fetch(var: str) -> np.ndarray:
    coll, field, scale, _ = VARS[var]
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{var}.npy"
    if path.exists():
        return np.load(path)
    urls = granules(coll)
    t0 = time.time()
    with httpx.Client(headers=creds.earthdata_headers(), follow_redirects=True, timeout=120) as c, \
            ThreadPoolExecutor(8) as ex:
        grids = list(ex.map(lambda m: _get(c, urls[m], field), MONTHS))
    a = scale(np.stack(grids)).astype(np.float32)  # (540, 91, 144)
    a[np.abs(a) > 1e6] = np.nan
    np.save(path, a)
    print(f"{var}: read {len(MONTHS)} months in {time.time() - t0:.0f} s", flush=True)
    return a


def land_mask() -> np.ndarray:
    path = RAW / "land.npy"
    if path.exists():
        return np.load(path)
    RAW.mkdir(parents=True, exist_ok=True)
    url = granules("M2C0NXASM")["1980-01"]
    with httpx.Client(headers=creds.earthdata_headers(), follow_redirects=True, timeout=120) as c:
        land = _get(c, url, "FRLAND") + _get(c, url, "FRLANDICE")
    np.save(path, land)
    return land


T = stats.to_decimal_year(__import__("pandas").date_range("1981-01-01", periods=len(MONTHS), freq="MS"))


def _ours(y):
    p_mk = mk.hamed_rao_modification_test(y, lag=stats.HR_LAG).p
    p_ols = stats.ols_neff(T, y)["p"]
    if p_mk < stats.ALPHA and p_ols < stats.ALPHA:
        return ("strong" if p_mk < stats.STRONG_ALPHA and p_ols < stats.STRONG_ALPHA else "some"), p_mk
    return ("mixed" if (p_mk < stats.ALPHA) != (p_ols < stats.ALPHA) else "none"), p_mk


def one_cell(args):
    k, y = args
    if not np.all(np.isfinite(y)) or np.std(y) == 0:
        return None
    clim = y.reshape(-1, 12).mean(axis=0)
    a = (y.reshape(-1, 12) - clim).ravel()  # monthly anomalies
    lr = sps.linregress(T, a)
    label, p_mk = _ours(a)
    slope = float(mk.sens_slope(a).slope * 120)  # per decade
    rng = np.random.default_rng(1000 + k)
    sh = a.reshape(-1, 12)[rng.permutation(len(a) // 12)].ravel()  # same years, shuffled order
    luck = sps.linregress(T, sh).pvalue < 0.05
    luck_ours = _ours(sh)[0] in ("strong", "some")
    return {"slope": slope, "label": label, "p_mk": float(p_mk), "typical": bool(lr.pvalue < 0.05),
            "luck": bool(luck), "luck_ours": bool(luck_ours)}


def build(var: str):
    grid = fetch(var)
    land = land_mask() >= 0.3
    lat = -90 + 2.0 * np.arange(91)
    lon = -180 + 2.5 * np.arange(144)
    flat = grid.reshape(len(MONTHS), -1).T  # (13104, 540)
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(one_cell, enumerate(flat), chunksize=64))
    fdr = stats.fdr([r["p_mk"] if r else np.nan for r in res])
    code = {"strong": "S", "some": "s", "mixed": "m", "none": "n"}
    rows, cnt = [], {"all": {}, "land": {}}
    for i, r in enumerate(res):
        if r is None:
            continue
        j, k = divmod(i, 144)
        if abs(lat[j]) == 90:  # the pole row is one point repeated 144 times
            continue
        is_land = bool(land[j, k])
        proven = r["label"] in ("strong", "some")
        flags = (code[r["label"]] + ("t" if r["typical"] else "") + ("f" if fdr[i] and proven else "")
                 + ("l" if r["luck"] else "") + ("o" if r["luck_ours"] else "") + ("L" if is_land else ""))
        rows.append([float(lat[j]), float(lon[k]), round(r["slope"], 4), flags])
        for scope in (["all", "land"] if is_land else ["all"]):
            c = cnt[scope]
            c["cells"] = c.get("cells", 0) + 1
            c["typical"] = c.get("typical", 0) + r["typical"]
            c["proven"] = c.get("proven", 0) + proven
            c["proven_fdr"] = c.get("proven_fdr", 0) + bool(fdr[i] and proven)
            c["luck_typical"] = c.get("luck_typical", 0) + r["luck"]
            c["luck_ours"] = c.get("luck_ours", 0) + r["luck_ours"]
            c["rising"] = c.get("rising", 0) + (proven and r["slope"] > 0)
            c["falling"] = c.get("falling", 0) + (proven and r["slope"] < 0)
    L = cnt["land"]
    pct = lambda a, b: round(100 * a / b) if b else 0  # noqa: E731
    out = {
        "variable": var, "units": VARS[var][3] + " per decade", "source": "NASA MERRA-2 monthly (M2TMNX), GES DISC",
        "period": "1981-01 to 2025-12", "grid": "2° lat x 2.5° lon (every 4th MERRA-2 point)",
        "columns": ["lat", "lon", "slope_per_decade", "flags"],
        "flags_key": {"S": "strong (proven)", "s": "some evidence (proven)", "m": "mixed", "n": "no proven trend",
                      "t": "typical test says significant", "f": "proven and survives the FDR check",
                      "l": "typical test fooled by shuffled years (luck)", "o": "our test fooled by shuffled years",
                      "L": "land cell"},
        "counts": cnt,
        "headline": (f"Land: a typical test calls {pct(L['typical'], L['cells'])}% of {L['cells']:,} places significant; "
                     f"{pct(L['proven'], L['cells'])}% are proven by our test and {pct(L['proven_fdr'], L['cells'])}% "
                     f"survive the false-discovery check. With the years shuffled (pure luck), the typical test still "
                     f"finds {pct(L['luck_typical'], L['cells'])}%, ours {pct(L['luck_ours'], L['cells'])}%."),
        "cells": rows,
    }
    p = DATA / f"globe_{var}.json"
    p.write_text(json.dumps(out, separators=(",", ":")))
    print(var, out["headline"], f"({p.stat().st_size / 1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    for v in sys.argv[1:] or list(VARS):
        build(v)
