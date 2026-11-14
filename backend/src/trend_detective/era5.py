"""ERA5 (ECMWF reanalysis) as a worldwide second witness, via the Open-Meteo
historical weather API (CC BY 4.0, no key). Daily values -> monthly means.

ERA5 and MERRA-2 are made by different centres with different models, but both
assimilate many of the same observations, so agreement is *supporting* evidence,
not fully independent. We say so on screen.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import httpx
import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY = ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
         "wind_speed_10m_mean", "relative_humidity_2m_mean", "shortwave_radiation_sum",
         "soil_moisture_0_to_7cm_mean", "soil_moisture_28_to_100cm_mean", "cloud_cover_mean"]
# NASA variable -> (ERA5 daily field, how to make a month, units note)
MAP = {
    "T2M": ("temperature_2m_mean", "mean", ""),
    "T2M_MAX": ("temperature_2m_max", "mean", ""),
    "T2M_MIN": ("temperature_2m_min", "mean", ""),
    "TS": ("temperature_2m_mean", "mean", "ERA5 air temperature compared with NASA ground-skin temperature: compare direction."),
    "PRECTOTCORR": ("precipitation_sum", "mean", ""),
    "WS2M": ("wind_speed_10m_mean", "mean", "ERA5 wind at 10 m (km/h), NASA at 2 m (m/s): compare direction, not size."),
    "RH2M": ("relative_humidity_2m_mean", "mean", ""),
    "ALLSKY_SFC_SW_DWN": ("shortwave_radiation_sum", "mean", ""),
    "CLOUD_AMT": ("cloud_cover_mean", "mean", ""),
    "GWETTOP": ("soil_moisture_0_to_7cm_mean", "mean", "ERA5 reports m³/m³ (0–7 cm); NASA a 0–1 wetness fraction: compare direction."),
    "GWETROOT": ("soil_moisture_28_to_100cm_mean", "mean", "ERA5 reports m³/m³ (28–100 cm); NASA a 0–1 wetness fraction: compare direction."),
    "FROST_DAYS": ("temperature_2m_min", "frost", "ERA5 days with a minimum below 0 °C."),
}
_LOCK = threading.Lock()


def _fetch(lat: float, lon: float) -> pd.DataFrame:
    lat, lon = round(lat * 4) / 4, round(lon * 4) / 4
    f = CACHE / f"era5_{lat:+.2f}_{lon:+.2f}.json"
    if f.exists():
        d = json.loads(f.read_text())
    else:
        with _LOCK:  # one at a time: Open-Meteo weighs long requests heavily
            for wait in (0, 62, 62):
                time.sleep(wait)
                r = httpx.get(URL, params={"latitude": lat, "longitude": lon, "start_date": "1981-01-01",
                                           "end_date": "2025-12-31", "daily": ",".join(DAILY), "timezone": "UTC"},
                              timeout=90)
                if r.status_code == 200:
                    break
            r.raise_for_status()
            d = r.json()
            f.write_text(json.dumps(d))
    df = pd.DataFrame(d["daily"])
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time")


def monthly(var: str, lat: float, lon: float) -> pd.Series | None:
    if var not in MAP:
        return None
    field, how, _ = MAP[var]
    s = _fetch(lat, lon)[field].astype(float)
    if how == "frost":
        m = (s < 0).resample("MS").sum().where(s.resample("MS").count() > 25)
    else:
        m = s.resample("MS").mean().where(s.resample("MS").count() > 25)
    return m.dropna()
