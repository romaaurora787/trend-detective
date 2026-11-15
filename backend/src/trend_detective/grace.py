"""NASA/JPL GRACE and GRACE-FO water storage (2002 onward) as a witness for soil wetness.

GRACE weighs the water on land from space: two satellites measure tiny changes in Earth's
gravity, so a drying region shows up as lost mass. It measures ALL stored water (soil,
groundwater, snow, lakes), not just the soil layer MERRA-2 models, so it supports or
questions the DIRECTION of a soil trend; it is not proof of the soil number itself.

Data: JPL GRACE/GRACE-FO mascon RL06.3Mv04 CRI (PO.DAAC, file dated 10 Nov 2026), land cells
averaged to 1° and committed as data/external/grace_jpl_mascon_land_1deg.nc (3.7 MB). The native
mascons are ~3° wide, so boxes smaller than that share one value. Gap: Jul 2017 – May 2018
between the two missions (left empty, never filled in). Units: cm of water.

Reference: Watkins, M. M. et al. (2015), Improved methods for observing Earth's time variable
mass distribution with GRACE using spherical cap mascons, J. Geophys. Res. Solid Earth 120,
2648–2671, doi:10.1002/2014JB011547. Data: doi:10.5067/TEMSC-3JC634.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

FILE = Path(__file__).resolve().parents[2] / "data" / "external" / "grace_jpl_mascon_land_1deg.nc"
NAME = "NASA GRACE / GRACE-FO satellites: all water stored on land (since 2002)"
CREDIT = ("Watkins et al. (2015), doi:10.1002/2014JB011547; JPL GRACE/GRACE-FO mascon RL06.3Mv04 CRI, "
          "NASA PO.DAAC, doi:10.5067/TEMSC-3JC634")
INDEPENDENCE = ("Independent measurement (gravity satellites), but of all stored water including groundwater, "
                "not just the soil layer: supporting evidence, not fully independent proof of a soil trend")
UNITS_NOTE = ("GRACE reports cm of water for ALL storage (soil + groundwater + snow); NASA POWER a 0–1 soil "
              "wetness fraction. Compare direction only. GRACE has a gap from mid-2017 to mid-2018.")
VARS = ("GWETTOP", "GWETROOT")


@lru_cache(maxsize=1)
def _grid():
    import xarray as xr

    return xr.open_dataset(FILE)["lwe_thickness"].load()  # (time, lat -89.5..89.5, lon -179.5..179.5)


def monthly(box) -> pd.Series:
    """Area-weighted box mean (cm of water), one value per month the satellites flew; the 2017-18 gap stays empty."""
    la0, la1, lo0, lo1 = (float(v) for v in box)
    da = _grid()
    lat, lon = da["lat"].values, da["lon"].values
    jm = (lat + 0.5 > la0) & (lat - 0.5 < la1)
    im = (lon + 0.5 > lo0) & (lon - 0.5 < lo1)
    if not jm.any() or not im.any():
        return pd.Series(dtype=float, name="GRACE")
    sub = da.values[:, jm][:, :, im]
    w = np.cos(np.radians(lat[jm]))[None, :, None] * np.ones_like(sub)
    ok = np.isfinite(sub)
    den = np.where(ok, w, 0).sum(axis=(1, 2))
    vals = np.where(den > 0, np.where(ok, sub * w, 0).sum(axis=(1, 2)) / np.where(den > 0, den, 1), np.nan)
    idx = pd.to_datetime(da["time"].values).to_period("M").to_timestamp()
    return pd.Series(vals, index=idx, name="GRACE").dropna()
