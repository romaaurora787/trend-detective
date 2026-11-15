"""NASA GISTEMP v4 (land, 250 km smoothing, 2° grid) as a worldwide thermometer witness for air temperature.

GISTEMP is NASA GISS's analysis of thousands of weather-station thermometers (NOAA GHCN v4).
MERRA-2 does not assimilate 2 m air temperature over land, so a GISTEMP trend that matches
the NASA POWER trend is independent evidence from real thermometers.

Only the box is read: NOAA PSL serves the gridded file over OPeNDAP, and we ask for the
2° cells that overlap the box from Jan 1981 onward (a few kB, no login). Values are monthly
anomalies (°C) against 1951–1980, so compare direction and slope, not the level.

Reference: Lenssen, N. et al. (2019). Improvements in the GISTEMP uncertainty model.
J. Geophys. Res. Atmos., 124, 6307–6326, doi:10.1029/2018JD029522. GISTEMP Team (2025):
GISS Surface Temperature Analysis (GISTEMP), version 4. NASA GISS. Gridded copy: NOAA PSL.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/gistemp/landonly/250km/air.2x2.250.mon.anom.land.nc"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
NAME = "NASA GISTEMP v4 station thermometers (250 km grid)"
CREDIT = ("GISTEMP Team (2025), GISS Surface Temperature Analysis v4, NASA GISS; Lenssen et al. (2019), "
          "doi:10.1029/2018JD029522. Gridded file served by NOAA PSL.")
INDEPENDENCE = ("Independent: real thermometers (NASA GISS analysis of NOAA GHCN stations). MERRA-2 does not "
                "use 2 m land air temperature, so agreement is separate evidence")
START = 1212  # index of Jan 1981 (the file starts Jan 1880)
_lock = threading.Lock()


def _ranges(box):
    """Index ranges of the 2° cells overlapping the box. lat 89..-89 (descending), lon 1..359."""
    la0, la1, lo0, lo1 = box
    j0 = max(0, int(np.floor((89 - min(la1 + 1, 89)) / 2)))
    j1 = min(89, int(np.ceil((89 - max(la0 - 1, -89)) / 2)))
    # cell centres c = 1 + 2i (0..360). A cell overlaps [lo0, lo1] when |c - x| <= 1 for some x in the box.
    a, b = lo0 % 360, lo1 % 360
    def idx(x0, x1):
        return max(0, int(np.ceil((x0 - 2) / 2))), min(179, int(np.floor(x1 / 2)))
    lons = [idx(a, b)] if a <= b else [idx(a, 360), idx(0, b)]  # the box crosses 0° (e.g. Lincolnshire)
    return j0, j1, lons


def _n_time(client) -> int:
    dds = client.get(URL + ".dds").text
    return int(re.search(r"time\[time = (\d+)\]", dds).group(1))


def _read(client, t1, j0, j1, i0, i1):
    ce = f"air[{START}:{t1}][{j0}:{j1}][{i0}:{i1}],lat[{j0}:{j1}]"
    r = client.get(URL + ".ascii?" + ce.replace("[", "%5B").replace("]", "%5D"))
    r.raise_for_status()
    body = r.text.split("---------------------------------------------", 1)[1]
    vals, lat = {}, None
    block = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("air.air["):
            block = "air"
        elif line.startswith("lat[") or line.startswith("air.lat["):
            block = "lat"
        elif block == "air" and line.startswith("["):
            k, v = line.split(",", 1)  # "[t][j], v_lon0, v_lon1, ..."
            t, j = (int(x) for x in re.findall(r"\d+", k))
            vals.setdefault(t, {}).setdefault(j, []).extend(float(x) for x in v.split(","))
        elif block == "lat" and line and line[0] in "-0123456789":
            lat = np.array([float(x) for x in line.split(",")])
            block = None
    return vals, lat


def _cache_path(box) -> Path:
    return CACHE / ("gistemp_" + "_".join(f"{v:+.2f}" for v in box) + ".json")


def monthly(box) -> pd.Series:
    """Box-mean GISTEMP anomaly (°C), one value per month from Jan 1981 (cached per box)."""
    box = [float(v) for v in box]
    path = _cache_path(box)
    if path.exists():
        d = json.loads(path.read_text())
    else:
        j0, j1, lons = _ranges(box)
        with httpx.Client(timeout=90, follow_redirects=True) as c:
            t1 = _n_time(c) - 1
            parts = [_read(c, t1, j0, j1, i0, i1) for i0, i1 in lons]
        d = {}
        for t in range(t1 - START + 1):
            num = den = 0.0
            for vals, lat in parts:
                for j, row in vals.get(t, {}).items():
                    w = float(np.cos(np.radians(lat[j])))
                    for v in row:
                        if abs(v) < 100:  # missing value is 9999
                            num, den = num + w * v, den + w
            y, m = divmod(START + t, 12)
            d[f"{1880 + y}-{m + 1:02d}"] = num / den if den else None
        with _lock:
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(d))
    s = pd.Series({pd.Timestamp(k + "-01"): v for k, v in d.items()}, dtype=float).sort_index()
    return s.dropna().rename("GISTEMP")
