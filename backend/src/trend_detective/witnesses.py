"""Feature C: "second witness" checks against records independent of MERRA-2.

For a variable and box, find an independent dataset that covers it, run the
same stats engine on both over the same period, and report whether the second
witness agrees.

Witnesses available:
- Met Office HadCET (thermometers): air temperature, Central England.
- NASA GPCP v3.3 (satellite + gauges): rainfall, global (when the global file
  is present), else the Lincoln box only.
- ESA CCI Soil Moisture COMBINED v09.2 (satellite microwave): soil wetness,
  Europe and East Africa, 1992 onwards.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import stats

EXT = Path(__file__).resolve().parents[2] / "data" / "external"
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ------------------------------------------------------------- loaders
@lru_cache(maxsize=1)
def _hadcet() -> pd.Series:
    rows = []
    for line in open(EXT / "hadcet_meantemp_monthly.txt"):
        p = line.split()
        if len(p) == 14 and p[0].isdigit():
            for m, v in enumerate(p[1:13], 1):
                if float(v) > -99:
                    rows.append((pd.Timestamp(int(p[0]), m, 1), float(v)))
    return pd.Series(dict(rows)).sort_index()


@lru_cache(maxsize=4)
def _open_nc(name: str):
    import xarray as xr

    p = EXT / name
    return xr.open_dataset(p) if p.exists() else None


def _box_mean(da, lat_min, lat_max, lon_min, lon_max) -> pd.Series | None:
    lat = da["lat"].values
    lat_slice = slice(lat_max, lat_min) if lat[0] > lat[-1] else slice(lat_min, lat_max)
    b = da.sel(lat=lat_slice, lon=slice(lon_min, lon_max))
    if b.sizes["lat"] == 0 or b.sizes["lon"] == 0:  # box smaller than a cell: nearest cell
        b = da.sel(lat=(lat_min + lat_max) / 2, lon=(lon_min + lon_max) / 2, method="nearest")
        s = b.to_series()
    else:
        w = np.cos(np.radians(b["lat"]))
        s = b.weighted(w).mean(("lat", "lon")).to_series()
    s = s.dropna()
    return s if len(s) >= 120 else None


def _inside(box, region) -> bool:
    la0, la1, lo0, lo1 = box
    ra0, ra1, ro0, ro1 = region
    return la0 >= ra0 and la1 <= ra1 and lo0 >= ro0 and lo1 <= ro1


# ------------------------------------------------------------- witnesses
def _hadcet_witness(box):
    # HadCET represents the Lancashire-London-Bristol triangle; use it only for
    # boxes in central/southern England.
    if not _inside(box, (50.5, 54.5, -4.0, 1.8)):
        return None
    return ("Met Office Central England Temperature (HadCET)", "thermometers", "independent", _hadcet())


def _gpcp_witness(box):
    ds = _open_nc("gpcp_v33_monthly_global_1deg.nc")
    if ds is not None:
        da = ds["sat_gauge_precip"]
        if float(da["lon"].max()) > 180:  # 0..360 grid -> -180..180
            da = da.assign_coords(lon=((da["lon"] + 180) % 360) - 180).sortby("lon")
        s = _box_mean(da, *box)
    elif _inside(box, (52.0, 54.2, -2.4, 1.2)):
        g = pd.read_csv(EXT / "gpcp_v33.csv")
        g = g[g.variable == "sat_gauge_precip"]
        s = pd.Series(g.box_mean.to_numpy(), index=pd.to_datetime(g.month + "-01")).sort_index()
    else:
        s = None
    if s is None:
        return None
    s.index = pd.to_datetime(s.index).to_period("M").to_timestamp()
    return ("NASA GPCP v3.3 rainfall", "satellites + rain gauges", "partly independent", s)


def _esa_witness(box):
    for name, region in [("esa_sm_europe_05deg.nc", (35.0, 72.0, -12.0, 40.0)),
                         ("esa_sm_east_africa_05deg.nc", (-5.0, 5.0, 33.0, 43.0))]:
        if _inside(box, region):
            ds = _open_nc(name)
            if ds is None:
                return None
            s = _box_mean(ds["sm"], *box)
            if s is None:
                return None
            s.index = pd.to_datetime(s.index)
            return ("ESA CCI Soil Moisture (European Space Agency)", "satellite microwave", "independent", s)
    return None


WITNESSES = {
    "T2M": _hadcet_witness,
    "PRECTOTCORR": _gpcp_witness,
    "GWETTOP": _esa_witness,
    "GWETROOT": _esa_witness,
}


def _proven(label: str) -> bool:
    return label in {"strong", "some"}


def second_witness(var: str, box, nasa: pd.Series, units: str) -> dict:
    """Compare the NASA series with an independent witness over the shared period."""
    finder = WITNESSES.get(var)
    found = finder(tuple(box)) if finder else None
    if not found:
        return {"available": False, "note": "No independent second witness for this variable and place yet."}
    name, kind, independence, other = found
    nasa = nasa.dropna()
    nasa.index = pd.to_datetime(nasa.index)
    start = max(nasa.index[0], other.index[0])
    end = min(nasa.index[-1], other.index[-1])
    a, b = nasa[start:end], other[start:end]
    if len(a) < 120 or len(b) < 120:
        return {"available": False, "note": f"{name} overlaps too briefly with the NASA record."}
    ra = stats.analyse(a, units)
    rb = stats.analyse(b, "")
    an, _ = stats.deseasonalise(a)
    bn, _ = stats.deseasonalise(b)
    corr = float(pd.concat([an, bn], axis=1, join="inner").corr().iloc[0, 1])
    pa, pb = _proven(ra["verdict"]["label"]), _proven(rb["verdict"]["label"])
    same_dir = np.sign(ra["sen_slope_per_decade"]) == np.sign(rb["sen_slope_per_decade"])
    if pa and pb and same_dir:
        agrees, note = True, f"Confirmed: {name} also shows a real {ra['verdict']['direction']} trend."
    elif not pa and not pb:
        agrees, note = True, f"Confirmed: {name} also finds no proven trend."
    elif pa and not pb:
        agrees, note = False, f"Caution: {name} does not confirm this trend. Treat it as unproven."
    elif pb and not pa:
        agrees, note = False, f"Caution: {name} shows a {rb['verdict']['direction']} trend that NASA's record does not."
    else:
        agrees, note = False, f"Caution: {name} shows the opposite direction."
    return {
        "available": True,
        "name": name,
        "kind": kind,
        "independence": independence,
        "period": f"{max(ra['start'], rb['start'])} to {min(ra['end'], rb['end'])}",
        "nasa_verdict": ra["verdict"]["label"],
        "nasa_slope_per_decade": ra["sen_slope_per_decade"],
        "witness_verdict": rb["verdict"]["label"],
        "witness_slope_per_decade": rb["sen_slope_per_decade"],
        "witness_units_note": "" if var in ("T2M", "PRECTOTCORR") else "ESA reports m³/m³; NASA a 0–1 wetness fraction, so compare direction, not size.",
        "monthly_correlation": corr,
        "agrees": bool(agrees),
        "note": note,
    }
