"""Help people start an investigation:

  profile(box)        What kind of place is this (from its own NASA data, not
                      guesswork), and which variables are worth a look here?
  HUNCHES / hunch()   Common beliefs ("summers are getting hotter") tested at a
                      place, with a four-way verdict.
  parse_csv()         Your own data (a weather station, a school logger): run the
                      same Detective on it.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pymannkendall as mk

from . import places, power, stats

PROVEN = {"strong", "some"}


# --------------------------------------------------------------------------- place profile
def profile(box: list[float]) -> dict:
    lat_c, lon_c = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2
    t, _ = power.fetch_area_series("T2M", *box)
    r, _ = power.fetch_area_series("PRECTOTCORR", *box)
    snow, _ = power.fetch_area_series("SNODP", *box)
    t_mean, r_mean = float(t.mean()), float(r.mean())
    t_cold = float(t.groupby(t.index.month).mean().min())
    snow_months = float((snow.groupby(snow.index.month).mean() > 5).sum())
    # sea cells: soil wetness is missing over water
    try:
        la0, la1 = power._widen(box[0], box[1], 90)
        lo0, lo1 = power._widen(box[2], box[3], 180)
        df, cells = power.fetch_region("GWETTOP", la0, la1, lo0, lo1)
        inside = [c for c in cells if box[0] <= c["lat"] <= box[1] and box[2] <= c["lon"] <= box[3]] or cells
        sea = sum(df[c["id"]].isna().mean() > 0.9 for c in inside) / max(len(inside), 1)
    except Exception:
        sea = 0.0
    big = [p for p in places.search_box(box) if p["population"] >= 1_000_000]
    types = []
    if t_mean >= 18 and r_mean < 0.8:
        types.append(("desert", "Hot desert", f"warm ({t_mean:.0f} °C average) and dry ({r_mean:.1f} mm of rain a day)"))
    if t_mean >= 22 and r_mean >= 4:
        types.append(("rainforest", "Wet tropics", f"hot ({t_mean:.0f} °C) and wet ({r_mean:.1f} mm a day)"))
    if t_mean >= 22 and not any(k in ("desert", "rainforest") for k, *_ in types):
        types.append(("hot", "Hot climate", f"hot all year ({t_mean:.0f} °C average)"))
    if t_mean < 3 or snow_months >= 3 or abs(lat_c) >= 60:
        types.append(("arctic", "Cold / snowy", f"{snow_months:.0f} months a year with snow on the ground; coldest month {t_cold:.0f} °C"))
    if sea >= 0.2:
        types.append(("coast", "Coast", f"{sea:.0%} of the NASA grid cells here are sea"))
    if big:
        types.append(("city", "Big city", f"{big[0]['name']} ({big[0]['population'] / 1e6:.1f} million people) is inside"))
    if not any(k in ("desert", "rainforest", "arctic", "hot") for k, *_ in types):
        types.append(("farm", "Temperate / farmland", f"mild ({t_mean:.0f} °C) with {r_mean:.1f} mm of rain a day"))
    from .catalogue import CATALOGUE
    keys = {k for k, *_ in types} | ({"desert", "city"} if any(k == "hot" for k, *_ in types) else set())
    suggest = [{"id": v["id"], "name": v["name"], "why": v["plain"]} for v in CATALOGUE
               if keys & set(v["tags"])]
    reasons = {"desert": "Deserts: watch daytime highs, dust and haze, and whether rare rain is changing.",
               "rainforest": "Wet tropics: watch rainfall, soil water and evaporation (drying forests), and humid heat.",
               "arctic": "Cold places warm fastest: watch winter temperature, snow depth and frost days.",
               "coast": "Coasts: watch the sea's surface temperature (skin temperature), wind and humidity.",
               "city": "Cities: watch night-time lows (the urban heat island), haze, and mugginess.",
               "hot": "Hot places: watch daytime highs, night-time lows (no relief at night) and mugginess (dew point).",
               "farm": "Farmland: watch the growing season — rain, root-zone soil wetness, frost and summer highs."}
    return {"types": [{"id": k, "name": n, "evidence": e, "tip": reasons[k]} for k, n, e in types],
            "facts": {"mean_temperature": t_mean, "rain_mm_per_day": r_mean, "coldest_month": t_cold,
                      "snow_months": snow_months, "sea_fraction": sea},
            "suggested_variables": suggest,
            "headline": "This looks like: " + ", ".join(n.lower() for _, n, _ in types) + ". "
                        + " ".join(reasons[k] for k, *_ in types[:2])}


# --------------------------------------------------------------------------- hunches
# season names are for the northern hemisphere; flipped south of the equator
HUNCHES = [
    {"id": "hotter_summers", "text": "Summers are getting hotter", "var": "T2M_MAX", "season": "summer", "dir": 1},
    {"id": "milder_winters", "text": "Winters are getting milder", "var": "T2M_MIN", "season": "winter", "dir": 1},
    {"id": "warmer_nights", "text": "Nights are warmer than they used to be", "var": "T2M_MIN", "season": None, "dir": 1},
    {"id": "fewer_frosts", "text": "We hardly get frosts any more", "var": "FROST_DAYS", "season": None, "dir": -1},
    {"id": "less_snow", "text": "There's less snow than there used to be", "var": "SNODP", "season": None, "dir": -1},
    {"id": "wetter", "text": "It rains more than it used to", "var": "PRECTOTCORR", "season": None, "dir": 1},
    {"id": "drier", "text": "It's getting drier", "var": "PRECTOTCORR", "season": None, "dir": -1},
    {"id": "drier_summers", "text": "Summers are drier", "var": "PRECTOTCORR", "season": "summer", "dir": -1},
    {"id": "wetter_winters", "text": "Winters are wetter", "var": "PRECTOTCORR", "season": "winter", "dir": 1},
    {"id": "soil_drying", "text": "The soil is drying out", "var": "GWETROOT", "season": None, "dir": -1},
    {"id": "muggier", "text": "It's getting more muggy", "var": "T2MDEW", "season": None, "dir": 1},
    {"id": "less_windy", "text": "It's less windy than it used to be", "var": "WS2M", "season": None, "dir": -1},
    {"id": "sunnier", "text": "It's sunnier than it used to be", "var": "ALLSKY_SFC_SW_DWN", "season": None, "dir": 1},
    {"id": "cleaner_air", "text": "The air is getting clearer (less haze)", "var": "AOD_55", "season": None, "dir": -1},
    {"id": "hotter", "text": "It's getting hotter", "var": "T2M", "season": None, "dir": 1},
    {"id": "greener", "text": "It's getting greener (more plant growth)", "var": "NDVI", "season": None, "dir": 1},
    {"id": "browner", "text": "The land is drying up and turning brown", "var": "NDVI", "season": "summer", "dir": -1},
]
BY_HUNCH = {h["id"]: h for h in HUNCHES}
_SEASON = {"summer": [6, 7, 8], "winter": [12, 1, 2]}


def _season_months(season: str, lat: float) -> list[int]:
    if lat < 0:
        season = {"summer": "winter", "winter": "summer"}[season]
    return _SEASON[season]


def hunch(h: dict, series: pd.Series, units: str, lat: float) -> dict:
    s = series.dropna()
    if h["season"]:
        months = _season_months(h["season"], lat)
        sub = s[s.index.month.isin(months)]
        yr = np.where(sub.index.month == 12, sub.index.year + 1, sub.index.year)
        g = sub.groupby(yr)
        ys = g.mean()[g.count() == 3]
        r = mk.hamed_rao_modification_test(ys.to_numpy(), lag=3)
        slope, p = float(r.slope * 10), float(r.p)
        proven = p < stats.ALPHA
        what = f"{h['season']} ({'Jun–Aug' if months == [6, 7, 8] else 'Dec–Feb'}) means, {int(ys.index[0])}–{int(ys.index[-1])}"
    else:
        a = stats.analyse(s, units)
        slope, p = a["sen_slope_per_decade"], a["mk_hamed_rao"]["p"]
        proven = a["verdict"]["label"] in PROVEN
        what = f"monthly record, {a['start'][:4]}–{a['end'][:4]}"
    right_way = np.sign(slope) == h["dir"]
    if proven and right_way:
        v, msg = "real", f"Real trend: the data back this up ({slope:+.3g} {units} per decade)."
    elif proven:
        v, msg = "opposite", f"The opposite: there is a real trend, but the other way ({slope:+.3g} {units} per decade)."
    elif right_way and p < 0.2:
        v, msg = "leaning", f"Leaning, not proven: the right direction ({slope:+.3g} {units} per decade), but luck can't be ruled out yet."
    else:
        v, msg = "not_backed", "Not backed up: the data show no real change in that direction."
    return {"hunch": h["text"], "verdict": v, "headline": msg, "slope_per_decade": slope, "p": p, "tested_on": what,
            "variable": h["var"]}


# --------------------------------------------------------------------------- your own data
def parse_csv(text: str) -> pd.Series:
    """Two columns: a date (YYYY-MM or YYYY-MM-DD; daily values become monthly means) and a number."""
    df = pd.read_csv(io.StringIO(text.strip()), header=None, comment="#", skip_blank_lines=True)
    if df.shape[1] < 2:
        raise ValueError("Need two columns: date, value")
    first = str(df.iloc[0, 0])
    if not any(ch.isdigit() for ch in first[:4]):  # header row
        df = df.iloc[1:]
    d = pd.to_datetime(df.iloc[:, 0].astype(str).str.strip(), errors="coerce", format="mixed")
    v = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s = pd.Series(v.to_numpy(), index=d).dropna()
    s = s[s.index.notna()].sort_index()
    if s.empty:
        raise ValueError("No readable rows. Use: 2001-01,4.2")
    m = s.resample("MS").mean().dropna()
    if len(m) < 120:
        raise ValueError(f"Need at least 10 years of monthly data; got {len(m)} months.")
    return m
