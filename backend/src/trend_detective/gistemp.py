"""NASA GISTEMP v4 (land, 250 km smoothing, 2° grid) as a worldwide thermometer witness for air temperature.

GISTEMP is NASA GISS's analysis of thousands of weather-station thermometers (NOAA GHCN v4).
MERRA-2 does not assimilate 2 m air temperature over land, so a GISTEMP trend that matches
the NASA POWER trend is independent evidence from real thermometers.

Data: NASA GISS gistemp250_GHCNv4.nc (downloaded 15 Nov 2026, file dated 10 Nov 2026), cut to
Jan 1981 onward and stored as data/external/gistemp250_GHCNv4_1981.nc (4.6 MB, 0.01 °C
precision), so the witness works offline and never waits on another server. Values are monthly
anomalies (°C) against 1951–1980, so compare direction and slope, not the level. Cells with no
station within 250 km are empty (oceans, deserts, parts of Africa).

Reference: Lenssen, N. et al. (2019). Improvements in the GISTEMP uncertainty model.
J. Geophys. Res. Atmos., 124, 6307–6326, doi:10.1029/2018JD029522. GISTEMP Team (2026):
GISS Surface Temperature Analysis (GISTEMP), version 4. NASA GISS, data.giss.nasa.gov/gistemp/.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

FILE = Path(__file__).resolve().parents[2] / "data" / "external" / "gistemp250_GHCNv4_1981.nc"
NAME = "NASA GISTEMP v4 station thermometers (250 km grid)"
CREDIT = ("GISTEMP Team (2026), GISS Surface Temperature Analysis v4, NASA GISS, data.giss.nasa.gov/gistemp/; "
          "Lenssen et al. (2019), doi:10.1029/2018JD029522")
INDEPENDENCE = ("Independent: real thermometers (NASA GISS analysis of NOAA GHCN stations). MERRA-2 does not "
                "use 2 m land air temperature, so agreement is separate evidence")


@lru_cache(maxsize=1)
def _grid():
    import xarray as xr

    return xr.open_dataset(FILE)["tempanomaly"].load()  # (time, lat -89..89, lon -179..179), ~36 MB in memory


def _overlap(centres: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """2° cells (centre ± 1°) that overlap [lo, hi]."""
    return (centres + 1 > lo) & (centres - 1 < hi)


def monthly(box) -> pd.Series:
    """Box-mean GISTEMP anomaly (°C), area-weighted over the overlapping 2° cells, one value per month from 1981."""
    la0, la1, lo0, lo1 = (float(v) for v in box)
    da = _grid()
    lat, lon = da["lat"].values, da["lon"].values
    jm = _overlap(lat, la0, la1)
    im = _overlap(lon, lo0, lo1) | _overlap(lon + 360, lo0, lo1) | _overlap(lon - 360, lo0, lo1)
    if not jm.any() or not im.any():
        return pd.Series(dtype=float, name="GISTEMP")
    sub = da.values[:, jm][:, :, im]  # (time, nlat, nlon)
    w = np.cos(np.radians(lat[jm]))[None, :, None] * np.ones_like(sub)
    ok = np.isfinite(sub)
    num = np.where(ok, sub * w, 0).sum(axis=(1, 2))
    den = np.where(ok, w, 0).sum(axis=(1, 2))
    vals = np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)
    idx = pd.to_datetime(da["time"].values).to_period("M").to_timestamp()
    return pd.Series(vals, index=idx, name="GISTEMP").dropna()
