"""Did climate models see it coming? Observed trend vs CMIP6 HighResMIP models.

Seven high-resolution CMIP6 HighResMIP models (Haarsma et al. 2016), daily,
1981–2050, at the place's centre, served by the Open-Meteo Climate API (no key).
For the observed period we compare our NASA trend with each model's trend over
the same years; then we show where the models go next (2026–2050).

Honest caveats, shown on screen:
  * These runs were given the real ocean surface temperatures up to 2014, so
    some agreement before then is built in; from 2015 they follow a
    high-emissions path (SSP5-8.5-like).
  * Models are a grid cell around the point, not the whole box.
  * A projection is not a forecast for any one year.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
URL = "https://climate-api.open-meteo.com/v1/climate"
MODELS = ["CMCC_CM2_VHR4", "FGOALS_f3_H", "HiRAM_SIT_HR", "MRI_AGCM3_2_S", "EC_Earth3P_HR", "MPI_ESM1_2_XR", "NICAM16_8S"]
# NASA variable -> (Open-Meteo field, units note)
MAP = {
    "T2M": ("temperature_2m_mean", ""),
    "T2M_MAX": ("temperature_2m_max", ""),
    "T2M_MIN": ("temperature_2m_min", ""),
    "PRECTOTCORR": ("precipitation_sum", ""),
    "RH2M": ("relative_humidity_2m_mean", ""),
    "WS2M": ("wind_speed_10m_mean", "Models give wind at 10 m in km/h; compare direction, not size."),
    "ALLSKY_SFC_SW_DWN": ("shortwave_radiation_sum", ""),
}
_LOCK = threading.Lock()


class ModelsError(RuntimeError):
    pass


def _fetch(var: str, lat: float, lon: float) -> pd.DataFrame:
    field = MAP[var][0]
    lat, lon = round(lat * 2) / 2, round(lon * 2) / 2
    f = CACHE / f"cmip6_{field}_{lat:+.1f}_{lon:+.1f}.json"
    if f.exists():
        d = json.loads(f.read_text())
    else:
        from .era5 import open_meteo_get
        with _LOCK:
            try:
                r = open_meteo_get(URL, {"latitude": lat, "longitude": lon, "start_date": "1981-01-01",
                                         "end_date": "2050-12-31", "models": ",".join(MODELS), "daily": field})
            except RuntimeError as e:
                raise ModelsError(str(e)) from e
            d = r.json()
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(d))
    df = pd.DataFrame(d["daily"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    cols = {m: f"{field}_{m}" for m in MODELS if f"{field}_{m}" in df}
    if not cols:
        raise ModelsError("No model data here.")
    return pd.DataFrame({m: df[c].astype(float) for m, c in cols.items()})


def _slope(monthly: pd.Series, y0: int, y1: int) -> float | None:
    s = monthly[(monthly.index.year >= y0) & (monthly.index.year <= y1)].dropna()
    if len(s) < 120:
        return None
    ann = (s - s.groupby(s.index.month).transform("mean")).groupby(s.index.year).mean()
    return float(mk.sens_slope(ann.to_numpy()).slope * 10)


def compare(var: str, lat: float, lon: float, observed_slope: float, y0: int, y1: int, units: str) -> dict:
    if var not in MAP:
        return {"available": False, "headline": "No climate-model comparison for this variable."}
    daily = _fetch(var, lat, lon)
    monthly = daily.resample("MS").mean()
    rows = []
    for m in monthly.columns:
        past, future = _slope(monthly[m], y0, y1), _slope(monthly[m], 2026, 2050)
        if past is not None:
            rows.append({"model": m, "slope_observed_period": past, "slope_2026_2050": future})
    if not rows:
        return {"available": False, "headline": "Model data too short here."}
    past = np.array([r["slope_observed_period"] for r in rows])
    fut = np.array([r["slope_2026_2050"] for r in rows if r["slope_2026_2050"] is not None])
    lo, hi, med = float(past.min()), float(past.max()), float(np.median(past))
    u = units
    if lo <= observed_slope <= hi:
        verdict, msg = "inside", (f"The models saw it coming: the observed {observed_slope:+.3g} {u}/decade sits inside the "
                                  f"range of {len(rows)} climate models for the same years ({lo:+.3g} to {hi:+.3g}).")
    else:
        verdict = "above" if observed_slope > hi else "below"
        # "stronger" = further from zero in the observed direction than every model
        stronger = (observed_slope > hi and observed_slope > 0) or (observed_slope < lo and observed_slope < 0)
        if stronger:
            word = "rising faster" if observed_slope > 0 else "falling faster"
            head = f"Stronger than every model: {word} than all {len(rows)} climate models"
        else:
            head = f"Weaker than every model: the {len(rows)} climate models expected more change"
        msg = f"{head} (observed {observed_slope:+.3g} {u}/decade, models {lo:+.3g} to {hi:+.3g} for the same years)."
    nxt = None
    if len(fut):
        same = int((np.sign(fut) == np.sign(np.median(fut))).sum())
        nxt = (f"Next: for 2026–2050 the models give {float(fut.min()):+.3g} to {float(fut.max()):+.3g} {u}/decade "
               f"(middle {float(np.median(fut)):+.3g}; {same} of {len(fut)} agree on the direction).")
    return {"available": True, "verdict": verdict, "headline": msg, "next": nxt, "models": rows,
            "observed_slope": observed_slope, "model_range": [lo, hi], "model_median": med,
            "period": f"{y0}–{y1}", "units_note": MAP[var][1],
            "caveat": ("These model runs were given the real ocean temperatures up to 2014, so some agreement before then is "
                       "built in; from 2015 they follow a high-emissions path. Models describe a grid cell around the centre "
                       "of your area, and a projection is not a forecast for any single year."),
            "credit": "CMIP6 HighResMIP (Haarsma et al. 2016), served by the Open-Meteo Climate API (CC BY 4.0)"}
